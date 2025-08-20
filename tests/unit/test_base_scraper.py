"""Test suite for the base scraper class."""

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.scraper import CacheEntry, ScraperConfig
from src.scrapers.base import BaseScraper


class _TestScraper(BaseScraper):
    """Test implementation of BaseScraper."""

    async def scrape_api(self) -> dict:
        """Mock API scraping."""
        return {"source": "api", "data": "test"}

    async def scrape_html(self) -> dict:
        """Mock HTML scraping."""
        return {"source": "html", "data": "test"}

    async def scrape_playwright(self) -> dict:
        """Mock Playwright scraping."""
        return {"source": "playwright", "data": "test"}


def describe_scraper_config():
    """Test scraper configuration."""

    def it_creates_with_defaults():
        """Creates config with default values."""
        config = ScraperConfig()
        assert config.rate_limit_delay == 1.0
        assert config.max_retries == 3
        assert config.retry_delays == [1, 2, 4]
        assert config.cache_ttl_hours == 23
        assert config.timeout == 30.0
        assert config.cache_dir == Path(".cache")
        assert config.user_agent.startswith("deprecations-rss/")

    def it_accepts_custom_values():
        """Accepts custom configuration values."""
        config = ScraperConfig(
            rate_limit_delay=2.0,
            max_retries=5,
            cache_ttl_hours=12,
            timeout=60.0,
            cache_dir=Path("custom_cache"),
        )
        assert config.rate_limit_delay == 2.0
        assert config.max_retries == 5
        assert config.cache_ttl_hours == 12
        assert config.timeout == 60.0
        assert config.cache_dir == Path("custom_cache")


def describe_cache_entry():
    """Test cache entry model."""

    def it_creates_from_data():
        """Creates cache entry with current timestamp."""
        data = {"key": "value"}
        entry = CacheEntry.from_data(data)
        assert entry.data == data
        assert isinstance(entry.timestamp, datetime)
        assert entry.timestamp.tzinfo == UTC

    def it_checks_if_expired():
        """Checks if cache entry is expired."""
        old_time = datetime.now(UTC) - timedelta(hours=24)
        entry = CacheEntry(data={"test": "data"}, timestamp=old_time)
        assert entry.is_expired(ttl_hours=23)

        recent_time = datetime.now(UTC) - timedelta(hours=1)
        entry = CacheEntry(data={"test": "data"}, timestamp=recent_time)
        assert not entry.is_expired(ttl_hours=23)


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def config(temp_cache_dir):
    """Create test configuration."""
    return ScraperConfig(
        cache_dir=temp_cache_dir,
        rate_limit_delay=0.1,  # Speed up tests
        max_retries=2,
        retry_delays=[0.1, 0.2],
    )


@pytest.fixture
def scraper(config):
    """Create test scraper instance."""
    return _TestScraper("https://test.com", config)


def describe_base_scraper():
    """Test base scraper functionality."""

    def it_initializes_correctly(scraper, config):
        """Initializes with URL and config."""
        assert scraper.url == "https://test.com"
        assert scraper.config == config
        assert scraper._last_request_time == 0

    def it_creates_cache_directory(temp_cache_dir):
        """Creates cache directory if it doesn't exist."""
        cache_dir = temp_cache_dir / "nested" / "cache"
        config = ScraperConfig(cache_dir=cache_dir)
        _TestScraper("https://test.com", config)
        assert cache_dir.exists()

    def describe_rate_limiting():
        """Test rate limiting functionality."""

        @pytest.mark.asyncio
        async def it_enforces_rate_limit(scraper):
            """Enforces minimum delay between requests."""
            # First request should proceed immediately
            start_time = asyncio.get_event_loop().time()
            await scraper._enforce_rate_limit()
            first_duration = asyncio.get_event_loop().time() - start_time
            assert first_duration < 0.05  # Should be nearly instant

            # Second request should be delayed
            start_time = asyncio.get_event_loop().time()
            await scraper._enforce_rate_limit()
            second_duration = asyncio.get_event_loop().time() - start_time
            assert second_duration >= 0.09  # Should wait for rate limit

    def describe_caching():
        """Test caching functionality."""

        def it_generates_cache_key(scraper):
            """Generates consistent cache key from URL."""
            key = scraper._get_cache_key()
            assert isinstance(key, str)
            assert len(key) == 64  # SHA-256 hex digest length

            # Same URL should generate same key
            key2 = scraper._get_cache_key()
            assert key == key2

        @pytest.mark.asyncio
        async def it_saves_and_loads_cache(scraper):
            """Saves and loads data from cache."""
            test_data = {"result": "cached_data"}

            # Save to cache
            await scraper._save_to_cache(test_data)

            # Load from cache
            cached_data = await scraper._load_from_cache()
            assert cached_data == test_data

        @pytest.mark.asyncio
        async def it_returns_none_for_missing_cache(scraper):
            """Returns None when cache file doesn't exist."""
            cached_data = await scraper._load_from_cache()
            assert cached_data is None

        @pytest.mark.asyncio
        async def it_returns_none_for_expired_cache(scraper, temp_cache_dir):
            """Returns None when cache is expired."""
            # Create expired cache entry
            cache_key = scraper._get_cache_key()
            cache_file = temp_cache_dir / f"{cache_key}.json"

            expired_time = datetime.now(UTC) - timedelta(hours=25)
            expired_entry = CacheEntry(data={"old": "data"}, timestamp=expired_time)

            with open(cache_file, "w") as f:
                json.dump(expired_entry.model_dump(), f, default=str)

            cached_data = await scraper._load_from_cache()
            assert cached_data is None

        @pytest.mark.asyncio
        async def it_handles_corrupted_cache(scraper, temp_cache_dir):
            """Returns None when cache file is corrupted."""
            cache_key = scraper._get_cache_key()
            cache_file = temp_cache_dir / f"{cache_key}.json"

            # Write invalid JSON
            with open(cache_file, "w") as f:
                f.write("invalid json content")

            cached_data = await scraper._load_from_cache()
            assert cached_data is None

    def describe_http_requests():
        """Test HTTP request functionality."""

        @pytest.mark.asyncio
        async def it_makes_http_request_with_retries(scraper):
            """Makes HTTP requests with proper headers and retries."""
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
                response = await scraper._make_request("https://test.com/api")

                assert response == {"success": True}
                mock_get.assert_called_once_with(
                    "https://test.com/api",
                    headers={"User-Agent": scraper.config.user_agent},
                    timeout=scraper.config.timeout,
                )

        @pytest.mark.asyncio
        async def it_retries_on_http_errors(scraper):
            """Retries requests on HTTP errors with exponential backoff."""
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = [
                httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()),
                httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()),
                None,  # Success on third try
            ]
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
                with patch("asyncio.sleep") as mock_sleep:
                    response = await scraper._make_request("https://test.com/api")

                    assert response == {"success": True}
                    assert mock_get.call_count == 3
                    # Check exponential backoff delays
                    mock_sleep.assert_any_call(0.1)  # First retry delay
                    mock_sleep.assert_any_call(0.2)  # Second retry delay

        @pytest.mark.asyncio
        async def it_gives_up_after_max_retries(scraper):
            """Gives up after maximum retries and raises exception."""
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=MagicMock()
            )

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                with patch("asyncio.sleep"):
                    with pytest.raises(httpx.HTTPStatusError):
                        await scraper._make_request("https://test.com/api")

    def describe_fallback_pattern():
        """Test fallback scraping pattern."""

        @pytest.mark.asyncio
        async def it_tries_api_first(scraper):
            """Tries API scraping first and returns result."""
            with patch.object(scraper, "scrape_api", return_value={"source": "api"}):
                result = await scraper.scrape()
                assert result == {"source": "api"}

        @pytest.mark.asyncio
        async def it_falls_back_to_html_when_api_fails(scraper):
            """Falls back to HTML scraping when API fails."""
            with patch.object(scraper, "scrape_api", side_effect=Exception("API failed")):
                with patch.object(scraper, "scrape_html", return_value={"source": "html"}):
                    result = await scraper.scrape()
                    assert result == {"source": "html"}

        @pytest.mark.asyncio
        async def it_falls_back_to_playwright_when_html_fails(scraper):
            """Falls back to Playwright when HTML fails."""
            with patch.object(scraper, "scrape_api", side_effect=Exception("API failed")):
                with patch.object(scraper, "scrape_html", side_effect=Exception("HTML failed")):
                    with patch.object(
                        scraper, "scrape_playwright", return_value={"source": "playwright"}
                    ):
                        result = await scraper.scrape()
                        assert result == {"source": "playwright"}

        @pytest.mark.asyncio
        async def it_raises_exception_when_all_methods_fail(scraper):
            """Raises exception when all scraping methods fail."""
            with patch.object(scraper, "scrape_api", side_effect=Exception("API failed")):
                with patch.object(scraper, "scrape_html", side_effect=Exception("HTML failed")):
                    with patch.object(
                        scraper, "scrape_playwright", side_effect=Exception("Playwright failed")
                    ):
                        with pytest.raises(Exception, match="All scraping methods failed"):
                            await scraper.scrape()

    def describe_caching_integration():
        """Test caching integration with scraping."""

        @pytest.mark.asyncio
        async def it_returns_cached_data_when_available(scraper):
            """Returns cached data when available and not expired."""
            cached_data = {"cached": True}

            with patch.object(scraper, "_load_from_cache", return_value=cached_data):
                result = await scraper.scrape()
                assert result == cached_data

        @pytest.mark.asyncio
        async def it_caches_scraped_data(scraper):
            """Caches data after successful scraping."""
            scraped_data = {"source": "api", "fresh": True}

            with patch.object(scraper, "_load_from_cache", return_value=None):
                with patch.object(scraper, "scrape_api", return_value=scraped_data):
                    with patch.object(scraper, "_save_to_cache") as mock_save:
                        result = await scraper.scrape()

                        assert result == scraped_data
                        mock_save.assert_called_once_with(scraped_data)

    def describe_sync_wrapper():
        """Test synchronous wrapper functionality."""

        def it_provides_sync_interface():
            """Provides synchronous interface to async scraping when not in async context."""
            # Create a new scraper in a non-async context
            config = ScraperConfig()
            scraper = _TestScraper("https://test.com", config)

            with patch.object(
                scraper, "scrape", new_callable=AsyncMock, return_value={"sync": True}
            ):
                with patch("asyncio.run", return_value={"sync": True}) as mock_run:
                    result = scraper.scrape_sync()
                    assert result == {"sync": True}
                    mock_run.assert_called_once()

        def it_raises_error_in_async_context():
            """Raises error when called from async context."""
            config = ScraperConfig()
            scraper = _TestScraper("https://test.com", config)

            # Mock get_running_loop to simulate being in an async context
            with patch("asyncio.get_running_loop", return_value=MagicMock()):
                with pytest.raises(
                    RuntimeError, match="Cannot use scrape_sync.*from within an async context"
                ):
                    scraper.scrape_sync()
