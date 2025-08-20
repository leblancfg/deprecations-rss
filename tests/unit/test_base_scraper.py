"""Tests for base scraper with caching functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, DeprecationEntry


class MockScraper(BaseScraper):
    """Concrete implementation of BaseScraper for testing."""

    def parse_deprecations(self, soup: BeautifulSoup, base_url: str) -> list[DeprecationEntry]:
        """Simple implementation for testing."""
        return []


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def base_scraper(temp_cache_dir):
    """Create a MockScraper instance with temporary cache."""
    return MockScraper(cache_dir=temp_cache_dir)


class DescribeBaseScraper:
    """Tests for BaseScraper functionality."""

    @pytest.mark.asyncio
    async def it_fetches_and_parses_html(self, base_scraper):
        """Should fetch HTML and return BeautifulSoup object."""
        url = "https://example.com/deprecations"
        html_content = b"""
        <html>
            <body>
                <h1>Deprecations</h1>
                <div class="deprecation">API v1 deprecated</div>
            </body>
        </html>
        """

        with patch.object(base_scraper.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html_content

            soup = await base_scraper.fetch_page(url)

            assert isinstance(soup, BeautifulSoup)
            assert soup.find("h1").text == "Deprecations"
            assert soup.find("div", class_="deprecation").text == "API v1 deprecated"
            mock_get.assert_called_once_with(url, headers=None)

    @pytest.mark.asyncio
    async def it_uses_cached_responses(self, base_scraper):
        """Should use cached responses when available."""
        url = "https://example.com/deprecations"
        html_content = b"<html><body>Cached content</body></html>"

        # Mock the cache to return cached content
        with patch.object(base_scraper.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html_content

            # First fetch
            soup1 = await base_scraper.fetch_page(url)
            # Second fetch
            soup2 = await base_scraper.fetch_page(url)

            # Both should return same content
            assert soup1.get_text(strip=True) == soup2.get_text(strip=True)
            # Cache.get should be called twice (caching is handled inside HTTPCache)
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def it_handles_network_errors_gracefully(self, base_scraper):
        """Should handle network errors and return None or cached data."""
        url = "https://example.com/deprecations"

        with patch.object(base_scraper.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.NetworkError("Connection failed")

            soup = await base_scraper.fetch_page(url)

            assert soup is None

    @pytest.mark.asyncio
    async def it_extracts_deprecation_entries(self, base_scraper):
        """Should extract deprecation entries from HTML."""
        html = b"""
        <html>
            <body>
                <div class="deprecation">
                    <h3>Model GPT-3</h3>
                    <p>Deprecated on 2024-12-31</p>
                    <p>Use GPT-4 instead</p>
                    <a href="/docs/gpt3">Documentation</a>
                </div>
                <div class="deprecation">
                    <h3>API v1</h3>
                    <p>Deprecated on 2024-06-30</p>
                    <p>Migrate to API v2</p>
                    <a href="/docs/api-v1">Learn more</a>
                </div>
            </body>
        </html>
        """

        # Mock the cache.get to return the HTML
        with patch.object(base_scraper.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html

            # Mock the parse_deprecations method to test base functionality
            with patch.object(base_scraper, "parse_deprecations") as mock_parse:
                mock_parse.return_value = [
                    DeprecationEntry(
                        title="Model GPT-3",
                        description="Deprecated on 2024-12-31. Use GPT-4 instead",
                        deprecation_date=datetime(2024, 12, 31, tzinfo=UTC),
                        link="https://example.com/docs/gpt3",
                        provider="Example",
                    ),
                    DeprecationEntry(
                        title="API v1",
                        description="Deprecated on 2024-06-30. Migrate to API v2",
                        deprecation_date=datetime(2024, 6, 30, tzinfo=UTC),
                        link="https://example.com/docs/api-v1",
                        provider="Example",
                    ),
                ]

                entries = await base_scraper.scrape("https://example.com/deprecations")

                # Should return the mocked list of entries
                assert len(entries) == 2
                assert entries[0].title == "Model GPT-3"
                assert entries[1].title == "API v1"

    def it_creates_deprecation_entry(self, base_scraper):
        """Should create DeprecationEntry objects correctly."""
        entry = DeprecationEntry(
            title="Legacy API",
            description="This API will be deprecated",
            deprecation_date=datetime(2024, 12, 31, tzinfo=UTC),
            link="https://example.com/api",
            provider="Example Provider",
        )

        assert entry.title == "Legacy API"
        assert entry.description == "This API will be deprecated"
        assert entry.deprecation_date == datetime(2024, 12, 31, tzinfo=UTC)
        assert entry.link == "https://example.com/api"
        assert entry.provider == "Example Provider"

    @pytest.mark.asyncio
    async def it_cleans_up_resources(self, base_scraper):
        """Should properly clean up resources when closed."""
        with patch.object(base_scraper.cache, "close", new_callable=AsyncMock) as mock_close:
            await base_scraper.close()
            mock_close.assert_called_once()

    def it_validates_deprecation_entry_dates(self):
        """Should validate that deprecation dates are timezone-aware."""
        # Valid entry with timezone-aware date
        entry = DeprecationEntry(
            title="Test",
            description="Test deprecation",
            deprecation_date=datetime(2024, 12, 31, tzinfo=UTC),
            link="https://example.com",
            provider="Test",
        )
        assert entry.deprecation_date.tzinfo is not None

        # Should raise error for naive datetime
        with pytest.raises(ValueError):
            DeprecationEntry(
                title="Test",
                description="Test deprecation",
                deprecation_date=datetime(2024, 12, 31),  # Naive datetime
                link="https://example.com",
                provider="Test",
            )
