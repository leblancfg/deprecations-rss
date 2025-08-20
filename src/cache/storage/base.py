"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class StorageBackend(ABC):
    """Abstract base class for cache storage backends."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Retrieve cached data by key.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached data as bytes, or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Store data in cache.

        Args:
            key: The cache key
            value: The data to cache as bytes
            ttl: Time to live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cached data by key.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache.

        Args:
            key: The cache key to check

        Returns:
            True if key exists, False otherwise
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cached data.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_metadata(self, key: str) -> dict[str, Any] | None:
        """Get metadata about a cached entry.

        Args:
            key: The cache key

        Returns:
            Metadata dict with 'created_at', 'expires_at', 'size' etc., or None
        """
        pass

    def generate_key(self, prefix: str, identifier: str, date: datetime | None = None) -> str:
        """Generate a cache key with optional date component.

        Args:
            prefix: Key prefix (e.g., 'deprecations', 'models')
            identifier: Unique identifier (e.g., provider name)
            date: Optional date for date-based keys

        Returns:
            Generated cache key
        """
        if date:
            return f"{prefix}:{identifier}:{date.strftime('%Y-%m-%d')}"
        return f"{prefix}:{identifier}"
