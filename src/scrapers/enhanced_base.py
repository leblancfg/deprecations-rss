"""Base scraper class with comprehensive error handling."""

import asyncio
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any

import httpx


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class URLValidationError(ScraperError):
    """Raised when a URL doesn't match expected patterns."""
    pass


@dataclass
class ErrorContext:
    """Detailed error context for debugging and monitoring."""

    url: str
    timestamp: datetime
    provider: str
    error_type: str
    status_code: int | None = None
    headers: dict[str, str] | None = None
    retry_count: int = 0
    response_body: str | None = None
    traceback: str | None = None


@dataclass
class ScraperResult:
    """Result from a scraping operation."""

    success: bool
    provider: str
    timestamp: datetime
    data: list[dict[str, Any]] | None = None
    error: ErrorContext | None = None
    from_cache: bool = False
    cache_timestamp: datetime | None = None


def retry_with_backoff(
    retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (httpx.HTTPError,)
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for retry logic with exponential backoff."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries - 1:
                        delay = backoff_factor * (2 ** attempt)
                        await asyncio.sleep(delay)
                    continue

            if last_exception:
                raise last_exception
            raise ScraperError("Retry failed with no exception")

        return wrapper
    return decorator


class BaseScraper(ABC):
    """Abstract base class for all provider scrapers."""

    provider_name: str = ""
    base_url: str = ""
    expected_url_patterns: list[str] = []
    timeout: float = 30.0
    retry_delay: float = 1.0
    max_retries: int = 3

    def __init__(self) -> None:
        """Initialize the scraper."""
        if not self.provider_name:
            raise ValueError("provider_name must be set")
        if not self.base_url:
            raise ValueError("base_url must be set")

    @abstractmethod
    async def extract_deprecations(self, content: str) -> list[dict[str, Any]]:
        """Extract deprecation data from scraped content.
        
        Args:
            content: Raw HTML/JSON content from the provider
            
        Returns:
            List of deprecation dictionaries with keys:
                - model: str
                - deprecation_date: str (ISO format)
                - retirement_date: Optional[str] (ISO format)
                - replacement: Optional[str]
                - notes: Optional[str]
        """
        pass

    async def scrape(self, url: str | None = None) -> ScraperResult:
        """Main scraping method with error handling.
        
        Args:
            url: Optional custom URL to scrape (defaults to base_url)
            
        Returns:
            ScraperResult with data or error information
        """
        url = url or self.base_url
        timestamp = datetime.now()

        try:
            # Validate URL if patterns are defined
            if self.expected_url_patterns:
                self.validate_url(url)

            # Fetch content with retries
            content = await self.fetch_content(url)

            # Extract deprecations
            data = await self.extract_deprecations(content)

            return ScraperResult(
                success=True,
                provider=self.provider_name,
                data=data,
                timestamp=timestamp,
                from_cache=False,
            )

        except httpx.HTTPStatusError as e:
            return ScraperResult(
                success=False,
                provider=self.provider_name,
                error=self.create_error_context(e, url),
                timestamp=timestamp,
            )

        except httpx.HTTPError as e:
            return ScraperResult(
                success=False,
                provider=self.provider_name,
                error=self.create_error_context(e, url),
                timestamp=timestamp,
            )

        except Exception as e:
            return ScraperResult(
                success=False,
                provider=self.provider_name,
                error=self.create_error_context(e, url),
                timestamp=timestamp,
            )

    @retry_with_backoff(retries=3, backoff_factor=1.0)
    async def fetch_content(self, url: str) -> str:
        """Fetch content from URL with retries.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response content as string
            
        Raises:
            httpx.HTTPError: On network or HTTP errors
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": "deprecations-rss/1.0 (https://github.com/leblancfg/deprecations-rss)"
                }
            )
            response.raise_for_status()
            return response.text

    def validate_url(self, url: str) -> None:
        """Validate URL against expected patterns.
        
        Args:
            url: URL to validate
            
        Raises:
            URLValidationError: If URL doesn't match any pattern
        """
        if not self.expected_url_patterns:
            return

        for pattern in self.expected_url_patterns:
            if re.match(pattern, url):
                return

        raise URLValidationError(
            f"URL {url} doesn't match expected patterns for {self.provider_name}"
        )

    def create_error_context(
        self,
        exception: Exception,
        url: str,
        retry_count: int = 0
    ) -> ErrorContext:
        """Create detailed error context from exception.
        
        Args:
            exception: The exception that occurred
            url: URL that was being accessed
            retry_count: Number of retries attempted
            
        Returns:
            ErrorContext with detailed information
        """
        context = ErrorContext(
            url=url,
            timestamp=datetime.now(),
            provider=self.provider_name,
            error_type=type(exception).__name__,
            retry_count=retry_count,
        )

        # Extract HTTP-specific information if available
        if isinstance(exception, httpx.HTTPStatusError):
            context.status_code = exception.response.status_code
            context.headers = dict(exception.response.headers)
            # Limit response body size for storage
            context.response_body = exception.response.text[:1000] if exception.response.text else None
        elif isinstance(exception, httpx.HTTPError) and hasattr(exception, "response"):
            if exception.response:
                context.status_code = exception.response.status_code
                context.headers = dict(exception.response.headers)

        return context

    async def scrape_with_fallback(
        self,
        urls: list[str],
        cache_fallback: Callable[[], ScraperResult] | None = None
    ) -> ScraperResult:
        """Try multiple URLs with cache fallback.
        
        Args:
            urls: List of URLs to try in order
            cache_fallback: Optional function to get cached data
            
        Returns:
            ScraperResult with data from first successful source
        """
        errors: list[ErrorContext] = []

        for url in urls:
            result = await self.scrape(url)
            if result.success:
                return result
            if result.error:
                errors.append(result.error)

        # Try cache fallback if all URLs failed
        if cache_fallback:
            cached_result = cache_fallback()
            if cached_result and cached_result.data:
                return cached_result

        # Return failure with all error contexts
        return ScraperResult(
            success=False,
            provider=self.provider_name,
            error=errors[0] if errors else None,
            timestamp=datetime.now(),
        )
