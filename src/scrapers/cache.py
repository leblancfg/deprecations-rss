"""Cache management for scraper results."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.scrapers.base import ScraperResult


@dataclass
class CacheEntry:
    """Represents a cached scraper result."""

    provider: str
    data: list[dict[str, Any]]
    timestamp: datetime
    expires_at: datetime
    url: str | None = None
    etag: str | None = None

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.expires_at

    def to_scraper_result(self) -> ScraperResult:
        """Convert cache entry to ScraperResult."""
        return ScraperResult(
            success=True,
            provider=self.provider,
            data=self.data,
            timestamp=datetime.now(),
            from_cache=True,
            cache_timestamp=self.timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider": self.provider,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "url": self.url,
            "etag": self.etag,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create CacheEntry from dictionary."""
        return cls(
            provider=data["provider"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            url=data.get("url"),
            etag=data.get("etag"),
        )


class CacheManager:
    """Manages cache storage and retrieval for scraper results."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        default_ttl_hours: float = 23.0
    ) -> None:
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache files (defaults to .cache/scrapers)
            default_ttl_hours: Default time-to-live in hours
        """
        self.cache_dir = cache_dir or Path(".cache/scrapers")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl_hours = default_ttl_hours

    def get_cache_path(self, provider: str) -> Path:
        """Get the cache file path for a provider."""
        return self.cache_dir / f"{provider}.json"

    def save(self, entry: CacheEntry) -> None:
        """Save a cache entry to disk.
        
        Args:
            entry: CacheEntry to save
        """
        cache_path = self.get_cache_path(entry.provider)

        with open(cache_path, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)

    def load(self, provider: str) -> CacheEntry | None:
        """Load cache entry for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            CacheEntry if valid cache exists, None otherwise
        """
        cache_path = self.get_cache_path(provider)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)

            entry = CacheEntry.from_dict(data)

            # Check if expired
            if entry.is_expired():
                return None

            return entry

        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache file is corrupted, remove it
            cache_path.unlink(missing_ok=True)
            return None

    def save_if_newer(self, entry: CacheEntry) -> bool:
        """Save cache entry only if it's newer than existing.
        
        Args:
            entry: CacheEntry to potentially save
            
        Returns:
            True if saved, False if existing cache is newer
        """
        existing = self.load(entry.provider)

        if existing is None or entry.timestamp > existing.timestamp:
            self.save(entry)
            return True

        return False

    def invalidate(self, provider: str) -> None:
        """Remove cache for a specific provider.
        
        Args:
            provider: Provider name
        """
        cache_path = self.get_cache_path(provider)
        cache_path.unlink(missing_ok=True)

    def clear_all(self) -> None:
        """Remove all cache files."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def get_all_cached_providers(self) -> list[str]:
        """Get list of all providers with valid cache.
        
        Returns:
            List of provider names with valid cache
        """
        providers = []

        for cache_file in self.cache_dir.glob("*.json"):
            provider = cache_file.stem
            if self.load(provider) is not None:
                providers.append(provider)

        return providers

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total = 0
        valid = 0
        expired = 0
        providers = []
        total_size = 0

        for cache_file in self.cache_dir.glob("*.json"):
            total += 1
            total_size += cache_file.stat().st_size

            provider = cache_file.stem
            entry = self.load(provider)

            if entry is not None:
                valid += 1
                providers.append(provider)
            else:
                expired += 1

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired,
            "providers": providers,
            "total_size_bytes": total_size,
            "cache_directory": str(self.cache_dir),
        }

    def create_from_result(
        self,
        result: ScraperResult,
        url: str | None = None,
        etag: str | None = None,
        ttl_hours: float | None = None
    ) -> CacheEntry:
        """Create a cache entry from a scraper result.
        
        Args:
            result: ScraperResult to cache
            url: Optional URL that was scraped
            etag: Optional ETag for conditional requests
            ttl_hours: Optional TTL override
            
        Returns:
            CacheEntry ready to be saved
        """
        ttl_hours = ttl_hours or self.default_ttl_hours

        return CacheEntry(
            provider=result.provider,
            data=result.data or [],
            timestamp=result.timestamp,
            expires_at=result.timestamp + timedelta(hours=ttl_hours),
            url=url,
            etag=etag,
        )

    def get_or_fetch(
        self,
        provider: str,
        fetch_func: Any,
        force_refresh: bool = False
    ) -> ScraperResult:
        """Get from cache or fetch if needed.
        
        Args:
            provider: Provider name
            fetch_func: Async function to fetch data if cache miss
            force_refresh: Force fetching even if cache exists
            
        Returns:
            ScraperResult from cache or fresh fetch
        """
        if not force_refresh:
            entry = self.load(provider)
            if entry is not None:
                return entry.to_scraper_result()

        # Cache miss or forced refresh - need to fetch
        import asyncio
        result = asyncio.run(fetch_func())

        if result.success and result.data:
            entry = self.create_from_result(result)
            self.save(entry)

        return result  # type: ignore[no-any-return]
