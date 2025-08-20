"""File system based storage backend for local development."""

import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.cache.storage.base import StorageBackend


class FileSystemStorage(StorageBackend):
    """File system based cache storage for local development."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize filesystem storage.

        Args:
            cache_dir: Directory for cache storage. Defaults to .cache/deprecations
        """
        self.cache_dir = cache_dir or Path.cwd() / ".cache" / "deprecations"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.cache_dir / ".metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        safe_key = key.replace(":", "_").replace("/", "_")
        return self.cache_dir / f"{safe_key}.cache"

    def _get_metadata_path(self, key: str) -> Path:
        """Get the metadata file path for a cache key."""
        safe_key = key.replace(":", "_").replace("/", "_")
        return self.metadata_dir / f"{safe_key}.json"

    async def get(self, key: str) -> bytes | None:
        """Retrieve cached data by key."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        metadata = await self.get_metadata(key)
        if metadata and metadata.get("expires_at"):
            expires_at = datetime.fromisoformat(metadata["expires_at"])
            if datetime.now(UTC) > expires_at:
                await self.delete(key)
                return None

        try:
            return await asyncio.to_thread(file_path.read_bytes)
        except Exception:
            return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Store data in cache."""
        file_path = self._get_file_path(key)
        metadata_path = self._get_metadata_path(key)

        try:
            await asyncio.to_thread(file_path.write_bytes, value)

            metadata = {
                "created_at": datetime.now(UTC).isoformat(),
                "size": len(value),
                "key": key,
            }

            if ttl:
                expires_at = datetime.now(UTC).timestamp() + ttl
                metadata["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()

            await asyncio.to_thread(metadata_path.write_text, json.dumps(metadata, indent=2))

            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete cached data by key."""
        file_path = self._get_file_path(key)
        metadata_path = self._get_metadata_path(key)

        deleted = False
        try:
            if file_path.exists():
                await asyncio.to_thread(file_path.unlink)
                deleted = True

            if metadata_path.exists():
                await asyncio.to_thread(metadata_path.unlink)

            return deleted
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return False

        metadata = await self.get_metadata(key)
        if metadata and metadata.get("expires_at"):
            expires_at = datetime.fromisoformat(metadata["expires_at"])
            if datetime.now(UTC) > expires_at:
                await self.delete(key)
                return False

        return True

    async def clear(self) -> bool:
        """Clear all cached data."""
        try:
            if self.cache_dir.exists():
                await asyncio.to_thread(shutil.rmtree, self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self.metadata_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    async def get_metadata(self, key: str) -> dict[str, Any] | None:
        """Get metadata about a cached entry."""
        metadata_path = self._get_metadata_path(key)

        if not metadata_path.exists():
            return None

        try:
            content = await asyncio.to_thread(metadata_path.read_text)
            return json.loads(content)  # type: ignore[no-any-return]
        except Exception:
            return None

    async def list_keys(self, pattern: str | None = None) -> list[str]:
        """List all cache keys, optionally filtered by pattern.

        Args:
            pattern: Optional prefix pattern to filter keys

        Returns:
            List of cache keys
        """
        keys = []
        for file_path in self.cache_dir.glob("*.cache"):
            key = file_path.stem.replace("_", ":")
            if (pattern is None or key.startswith(pattern)) and await self.exists(key):
                keys.append(key)
        return sorted(keys)
