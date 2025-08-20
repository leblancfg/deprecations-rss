"""Cache manager with fallback support."""

import json
import os
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from src.cache.storage.base import StorageBackend
from src.cache.storage.filesystem import FileSystemStorage
from src.cache.storage.github_actions import GitHubActionsStorage


class CacheEntry(BaseModel):
    """Represents a cached entry with metadata."""

    key: str
    data: Any
    created_at: datetime
    expires_at: datetime | None = None
    source: str = "scraper"  # 'scraper' or 'fallback'

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class CacheManager:
    """Manages caching with fallback support."""

    def __init__(self, storage: StorageBackend | None = None):
        """Initialize cache manager.

        Args:
            storage: Storage backend to use. Defaults to appropriate backend based on environment.
        """
        if storage is None:
            storage = self._get_default_storage()
        self.storage = storage

    def _get_default_storage(self) -> StorageBackend:
        """Get the default storage backend based on environment."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            return GitHubActionsStorage()
        return FileSystemStorage()

    async def get_with_fallback(
        self,
        key: str,
        fetch_func: Any | None = None,
        ttl: int = 86400,  # 24 hours default
        use_stale_on_error: bool = True,
    ) -> Any | None:
        """Get data from cache with fallback support.

        Args:
            key: Cache key
            fetch_func: Async function to fetch fresh data if cache miss
            ttl: Time to live in seconds
            use_stale_on_error: Use stale cache if fetch fails

        Returns:
            Cached or fetched data, or None if both fail
        """
        cached_data = await self._get_from_cache(key)

        if cached_data and not self._is_stale(cached_data, ttl):
            return cached_data.get("data")

        if fetch_func:
            try:
                fresh_data = await fetch_func()
                if fresh_data:
                    await self._save_to_cache(key, fresh_data, ttl)
                    return fresh_data
            except Exception as e:
                print(f"Failed to fetch fresh data: {e}")

                if use_stale_on_error and cached_data:
                    print(f"Using stale cache for {key}")
                    return cached_data.get("data")

        if cached_data:
            return cached_data.get("data")

        return None

    async def _get_from_cache(self, key: str) -> dict[str, Any] | None:
        """Get data from cache storage."""
        cached_bytes = await self.storage.get(key)
        if cached_bytes:
            try:
                return json.loads(cached_bytes.decode("utf-8"))  # type: ignore[no-any-return]
            except Exception:
                return None
        return None

    async def _save_to_cache(self, key: str, data: Any, ttl: int) -> bool:
        """Save data to cache storage."""
        cache_entry = {"data": data, "created_at": datetime.now(UTC).isoformat(), "ttl": ttl}

        try:
            json_data = json.dumps(cache_entry, default=str)
            return await self.storage.set(key, json_data.encode("utf-8"), ttl)
        except Exception:
            return False

    def _is_stale(self, cached_data: dict[str, Any], ttl: int) -> bool:
        """Check if cached data is stale."""
        created_at_str = cached_data.get("created_at")
        if not created_at_str:
            return True

        try:
            created_at = datetime.fromisoformat(created_at_str)
            age = (datetime.now(UTC) - created_at).total_seconds()
            return age > ttl
        except Exception:
            return True

    async def save_deprecation_data(
        self, provider: str, data: Any, date: datetime | None = None
    ) -> bool:
        """Save deprecation data for a specific provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            data: Deprecation data to save
            date: Optional date for the data

        Returns:
            True if saved successfully
        """
        if date is None:
            date = datetime.now(UTC)

        key = self.storage.generate_key("deprecations", provider, date)

        cache_data = {
            "provider": provider,
            "date": date.isoformat(),
            "data": data,
            "scraped_at": datetime.now(UTC).isoformat(),
        }

        try:
            json_data = json.dumps(cache_data, default=str)
            return await self.storage.set(key, json_data.encode("utf-8"), ttl=172800)  # 48 hours
        except Exception:
            return False

    async def get_deprecation_data(
        self, provider: str, date: datetime | None = None, max_age_days: int = 7
    ) -> Any | None:
        """Get deprecation data for a specific provider.

        Args:
            provider: Provider name
            date: Optional specific date to retrieve
            max_age_days: Maximum age of data to consider valid

        Returns:
            Deprecation data or None
        """
        if date is None:
            date = datetime.now(UTC)

        for days_back in range(max_age_days):
            check_date = datetime.fromtimestamp(date.timestamp() - (days_back * 86400), UTC)
            key = self.storage.generate_key("deprecations", provider, check_date)

            cached_data = await self._get_from_cache(key)
            if cached_data:
                return cached_data.get("data")

        return None

    async def get_all_providers_data(self, date: datetime | None = None) -> dict[str, Any]:
        """Get deprecation data for all providers.

        Args:
            date: Optional specific date to retrieve

        Returns:
            Dictionary mapping provider names to their data
        """
        providers = ["openai", "anthropic", "google", "mistral", "cohere"]
        result = {}

        for provider in providers:
            data = await self.get_deprecation_data(provider, date)
            if data:
                result[provider] = data

        return result
