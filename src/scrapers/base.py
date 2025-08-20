"""Base scraper class with caching support."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, field_validator


class DeprecationEntry(BaseModel):
    """Model for deprecation entries."""

    title: str
    description: str
    deprecation_date: datetime
    link: str
    provider: str

    @field_validator("deprecation_date")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure deprecation date is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Deprecation date must be timezone-aware")
        return v


class BaseScraper(ABC):
    """Base class for deprecation scrapers with caching support."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize scraper with cache.

        Args:
            cache_dir: Directory to store cache files
        """
        from src.cache.http_cache import HTTPCache

        self.cache = HTTPCache(cache_dir=cache_dir)

    async def fetch_page(
        self, url: str, headers: dict[str, str] | None = None
    ) -> BeautifulSoup | None:
        """Fetch and parse HTML page.

        Args:
            url: URL to fetch
            headers: Additional headers to send

        Returns:
            BeautifulSoup object or None if fetch fails
        """
        try:
            content = await self.cache.get(url, headers=headers)
            return BeautifulSoup(content, "html.parser")
        except (httpx.NetworkError, httpx.TimeoutException):
            return None

    async def scrape(self, url: str) -> list[DeprecationEntry] | None:
        """Scrape deprecation information from URL.

        Args:
            url: URL to scrape

        Returns:
            List of deprecation entries or None if scraping fails
        """
        soup = await self.fetch_page(url)
        if soup is None:
            return None

        return self.parse_deprecations(soup, url)

    @abstractmethod
    def parse_deprecations(self, soup: BeautifulSoup, base_url: str) -> list[DeprecationEntry]:
        """Parse deprecation entries from HTML.

        Args:
            soup: BeautifulSoup object containing the HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of deprecation entries
        """
        pass

    async def close(self) -> None:
        """Clean up resources."""
        await self.cache.close()
