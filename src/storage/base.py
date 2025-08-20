"""Abstract base storage interface for deprecation data."""

from abc import ABC, abstractmethod
from datetime import datetime

from src.models.deprecation import Deprecation


class BaseStorage(ABC):
    """Abstract base class for deprecation data storage."""

    @abstractmethod
    async def store(self, deprecations: list[Deprecation]) -> int:
        """
        Store deprecations, avoiding duplicates.

        Args:
            deprecations: List of deprecation objects to store

        Returns:
            Number of new deprecations stored (excludes duplicates)
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all(self) -> list[Deprecation]:
        """
        Retrieve all stored deprecations.

        Returns:
            List of all deprecation objects
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_provider(self, provider: str) -> list[Deprecation]:
        """
        Retrieve deprecations for a specific provider.

        Args:
            provider: Provider name to filter by

        Returns:
            List of deprecations from the specified provider
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Deprecation]:
        """
        Retrieve deprecations within a date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of deprecations within the specified date range
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_by_provider(self, provider: str) -> int:
        """
        Delete all deprecations for a specific provider.

        Args:
            provider: Provider name to delete deprecations for

        Returns:
            Number of deprecations deleted
        """
        raise NotImplementedError

    @abstractmethod
    async def clear_all(self) -> int:
        """
        Clear all stored deprecations.

        Returns:
            Number of deprecations cleared
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, deprecation: Deprecation) -> bool:
        """
        Update an existing deprecation.

        Args:
            deprecation: Updated deprecation object

        Returns:
            True if deprecation was found and updated, False otherwise
        """
        raise NotImplementedError
