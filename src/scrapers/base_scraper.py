"""Base scraper class with common functionality."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from src.scrapers.utils import clean_text, parse_date


@dataclass
class ScraperConfig:
    """Configuration for scraper behavior."""

    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = field(
        default="DeprecationsRSS/1.0 (+https://github.com/leblancfg/deprecations-rss)"
    )


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class ExtractionError(ScraperError):
    """Raised when data extraction fails."""

    pass


class BaseScraper(ABC):
    """
    Abstract base class for all deprecation scrapers.
    Provides common functionality:
    - HTTP client with retry logic
    - HTML parsing utilities
    - Text extraction helpers
    - Error handling
    """

    def __init__(
        self,
        url: str,
        config: ScraperConfig | None = None,
    ) -> None:
        """
        Initialize scraper with target URL.
        Args:
            url: Base URL to scrape
            config: Scraper configuration
        """
        self.url = url
        self.config = config or ScraperConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def fetch(self, url: str) -> str:
        """
        Fetch content from URL with retry logic.
        Args:
            url: URL to fetch
        Returns:
            Response text content
        Raises:
            ScraperError: If fetch fails after retries
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                last_error = e

                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    delay = self.config.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

        raise ScraperError(
            f"Failed after {self.config.max_retries} retries: {last_error}"
        ) from last_error

    async def parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML content into BeautifulSoup object.
        Args:
            html: HTML string to parse
        Returns:
            Parsed BeautifulSoup object
        """
        return BeautifulSoup(html, "html.parser")

    def extract_text(
        self,
        element: Tag | None,
        default: str = "",
    ) -> str:
        """
        Safely extract and clean text from element.
        Args:
            element: BeautifulSoup element
            default: Default value if element is None
        Returns:
            Cleaned text content
        """
        if element is None:
            return default

        text = element.get_text() if hasattr(element, "get_text") else str(element)
        return clean_text(text)

    def extract_date(
        self,
        element: Tag | None,
    ) -> datetime | None:
        """
        Extract and parse date from element.
        Args:
            element: Element containing date text
        Returns:
            Parsed datetime or None
        """
        if element is None:
            return None

        date_text = self.extract_text(element)
        return parse_date(date_text, raise_on_error=False)

    @abstractmethod
    async def extract_deprecations(self) -> list[dict[str, Any]]:
        """
        Extract deprecation data from source.

        Must be implemented by subclasses.
        Returns:
            List of deprecation dictionaries with keys:
            - provider: Provider name
            - model: Model name
            - announcement_date: When deprecation was announced
            - retirement_date: When model will be retired
            - replacement_model: Suggested replacement (optional)
            - notes: Additional context (optional)
        """
        pass

    async def run(self) -> list[dict[str, Any]]:
        """
        Run the scraper and return results.
        Returns:
            List of extracted deprecation data
        Raises:
            ExtractionError: If extraction fails
        """
        try:
            return await self.extract_deprecations()
        except Exception as e:
            raise ExtractionError(f"Extraction failed: {e}") from e

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
