"""Abstract base scraper with retry logic, rate limiting, and caching."""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from src.models.scraper import CacheEntry, ScraperConfig

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base scraper with common functionality."""

    def __init__(self, url: str, config: ScraperConfig | None = None) -> None:
        """Initialize scraper with URL and configuration."""
        self.url = url
        self.config = config or ScraperConfig()
        self._last_request_time = 0.0

        # Ensure cache directory exists
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def scrape_api(self) -> dict[str, Any]:
        """Scrape using API endpoint. Must be implemented by subclasses."""
        raise NotImplementedError

    @abstractmethod
    async def scrape_html(self) -> dict[str, Any]:
        """Scrape using HTML parsing. Must be implemented by subclasses."""
        raise NotImplementedError

    @abstractmethod
    async def scrape_playwright(self) -> dict[str, Any]:
        """Scrape using Playwright for JS rendering. Must be implemented by subclasses."""
        raise NotImplementedError

    async def scrape(self) -> dict[str, Any]:
        """Main scraping method with fallback pattern and caching."""
        # Check cache first
        cached_data = await self._load_from_cache()
        if cached_data is not None:
            logger.info("Returning cached data")
            return cached_data

        # Try scraping methods in order with fallback pattern
        methods = [
            ("API", self.scrape_api),
            ("HTML", self.scrape_html),
            ("Playwright", self.scrape_playwright),
        ]

        last_error = None
        for method_name, method in methods:
            try:
                logger.info(f"Attempting {method_name} scraping")
                data = await method()
                logger.info(f"Successfully scraped data using {method_name}")

                # Cache successful result
                await self._save_to_cache(data)
                return data

            except Exception as e:
                logger.warning(f"{method_name} scraping failed: {e}")
                last_error = e
                continue

        # All methods failed
        error_msg = f"All scraping methods failed. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg) from last_error

    def scrape_sync(self) -> dict[str, Any]:
        """Synchronous wrapper for async scrape method."""
        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # If we get here, there's a running loop, so we can't use asyncio.run()
            raise RuntimeError(
                "Cannot use scrape_sync() from within an async context. Use await scrape() instead."
            )
        except RuntimeError as e:
            # Check if the error is specifically about no running loop
            if (
                "no running event loop" in str(e).lower()
                or "no current event loop" in str(e).lower()
            ):
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(self.scrape())
            else:
                # Some other RuntimeError, re-raise it
                raise

    async def _make_request(self, url: str) -> dict[str, Any]:
        """Make HTTP request with retry logic and rate limiting."""
        await self._enforce_rate_limit()

        headers = {"User-Agent": self.config.user_agent}
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, timeout=self.config.timeout)
                    response.raise_for_status()
                    json_data: dict[str, Any] = response.json()
                    return json_data

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delays[attempt]
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {self.config.max_retries + 1} attempts")
                    break

        # Re-raise the last error if all retries failed
        if last_error:
            raise last_error
        raise Exception("Request failed for unknown reason")

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.config.rate_limit_delay:
            sleep_time = self.config.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self._last_request_time = asyncio.get_event_loop().time()

    def _get_cache_key(self) -> str:
        """Generate cache key from URL."""
        return hashlib.sha256(self.url.encode()).hexdigest()

    async def _load_from_cache(self) -> dict[str, Any] | None:
        """Load data from cache if available and not expired."""
        cache_key = self._get_cache_key()
        cache_file = self.config.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cache_data = json.load(f)

            entry = CacheEntry(**cache_data)

            if entry.is_expired(self.config.cache_ttl_hours):
                logger.info("Cache expired, removing file")
                cache_file.unlink(missing_ok=True)
                return None

            logger.info("Loaded data from cache")
            return entry.data

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load cache file: {e}")
            # Remove corrupted cache file
            cache_file.unlink(missing_ok=True)
            return None

    async def _save_to_cache(self, data: dict[str, Any]) -> None:
        """Save data to cache with timestamp."""
        cache_key = self._get_cache_key()
        cache_file = self.config.cache_dir / f"{cache_key}.json"

        entry = CacheEntry.from_data(data)

        try:
            with open(cache_file, "w") as f:
                json.dump(entry.model_dump(), f, default=str)
            logger.info("Saved data to cache")
        except (OSError, TypeError) as e:
            logger.warning(f"Failed to save cache file: {e}")
