"""HTTP cache implementation with support for ETags and conditional requests."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import HttpUrl

from src.cache.models import CacheEntry


class HTTPCache:
    """HTTP cache with support for ETags, Last-Modified, and Cache-Control headers."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize HTTP cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to .cache/http
        """
        self.cache_dir = cache_dir or Path(".cache/http")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "deprecations-rss/1.0"},
            follow_redirects=True,
            timeout=30.0,
        )

    async def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Get content from URL, using cache when possible.

        Args:
            url: URL to fetch
            headers: Additional headers to send with request

        Returns:
            Response content as bytes
        """
        headers = headers or {}
        cache_key = self._get_cache_key(url)
        cache_file = self.cache_dir / cache_key

        # Try to load from cache
        cached_entry = self._load_cache_entry(cache_file)

        if cached_entry:
            if not cached_entry.is_expired():
                # Cache is still fresh, return it
                return cached_entry.content

            # Cache is expired, try conditional request
            conditional_headers = cached_entry.get_conditional_headers()
            headers.update(conditional_headers)

        # Fetch from network
        try:
            response = await self._fetch(url, headers)

            if response.status_code == 304 and cached_entry:
                # Not modified, update timestamp and return cached content
                cached_entry.timestamp = datetime.now(UTC)
                self._save_cache_entry(cache_file, cached_entry)
                return cached_entry.content

            if response.status_code == 200:
                # Got new content, cache it
                entry = self._create_cache_entry(url, response)
                self._save_cache_entry(cache_file, entry)
                return entry.content

            # Non-200/304 response
            response.raise_for_status()

        except (httpx.NetworkError, httpx.TimeoutException) as e:
            # Network error - return stale cache if available
            if cached_entry:
                return cached_entry.content
            raise e

        return b""  # Should not reach here

    async def _fetch(self, url: str, headers: dict[str, str]) -> httpx.Response:
        """Fetch URL with given headers."""
        return await self.client.get(url, headers=headers)

    def _create_cache_entry(self, url: str, response: httpx.Response) -> CacheEntry:
        """Create cache entry from HTTP response."""
        headers = dict(response.headers)

        # Extract caching-related headers
        etag = headers.get("ETag")
        last_modified = headers.get("Last-Modified")
        cache_control = headers.get("Cache-Control", "")
        max_age = self._parse_max_age(cache_control)

        return CacheEntry(
            url=HttpUrl(url),
            content=response.content,
            headers=headers,
            timestamp=datetime.now(UTC),
            etag=etag,
            last_modified=last_modified,
            max_age=max_age,
        )

    def _parse_max_age(self, cache_control: str) -> int | None:
        """Parse max-age from Cache-Control header."""
        if not cache_control:
            return None

        # Look for max-age directive
        match = re.search(r"max-age=(\d+)", cache_control)
        if match:
            return int(match.group(1))

        return None

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return f"{url_hash}.json"

    def _load_cache_entry(self, cache_file: Path) -> CacheEntry | None:
        """Load cache entry from file."""
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text())
            # Convert timestamp string back to datetime
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            # Convert content from base64-encoded string back to bytes
            import base64

            data["content"] = base64.b64decode(data["content"])
            return CacheEntry(**data)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Invalid cache file, remove it
            cache_file.unlink(missing_ok=True)
            return None

    def _save_cache_entry(self, cache_file: Path, entry: CacheEntry) -> None:
        """Save cache entry to file."""
        # Convert to dict for JSON serialization
        data = entry.model_dump()
        # Convert datetime to ISO format string
        data["timestamp"] = data["timestamp"].isoformat()
        # Convert URL object to string
        data["url"] = str(data["url"])
        # Convert bytes to base64-encoded string for JSON
        import base64

        data["content"] = base64.b64encode(data["content"]).decode("ascii")

        cache_file.write_text(json.dumps(data, indent=2))

    def clear(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def invalidate(self, url: str) -> None:
        """Invalidate cache for specific URL."""
        cache_key = self._get_cache_key(url)
        cache_file = self.cache_dir / cache_key
        cache_file.unlink(missing_ok=True)

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
