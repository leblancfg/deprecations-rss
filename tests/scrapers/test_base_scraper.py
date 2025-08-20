"""Tests for base scraper functionality."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.scrapers.base_scraper import (
    BaseScraper,
    ExtractionError,
    ScraperConfig,
    ScraperError,
)


class MockScraper(BaseScraper):
    """Test implementation of BaseScraper."""

    async def extract_deprecations(self) -> list[dict]:
        """Test extraction method."""
        return [
            {
                "provider": "test",
                "model": "test-model",
                "announcement_date": datetime.now(UTC),
                "retirement_date": datetime.now(UTC),
            }
        ]


class DescribeScraperConfig:
    """Test ScraperConfig functionality."""

    def it_has_sensible_defaults(self):
        config = ScraperConfig()
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.user_agent.startswith("DeprecationsRSS")

    def it_accepts_custom_values(self):
        config = ScraperConfig(
            timeout=60,
            max_retries=5,
            retry_delay=2.0,
            user_agent="CustomAgent/1.0",
        )
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.user_agent == "CustomAgent/1.0"


class DescribeBaseScraper:
    """Test BaseScraper functionality."""

    @pytest.fixture
    def scraper(self):
        return MockScraper("https://example.com")

    def it_initializes_with_url(self, scraper):
        assert scraper.url == "https://example.com"
        assert isinstance(scraper.config, ScraperConfig)
        assert scraper._client is None

    def it_initializes_with_custom_config(self):
        config = ScraperConfig(timeout=60)
        scraper = MockScraper("https://example.com", config=config)
        assert scraper.config.timeout == 60

    @pytest.mark.asyncio
    async def it_creates_client_on_demand(self, scraper):
        client = await scraper._get_client()
        assert isinstance(client, httpx.AsyncClient)
        assert str(client.timeout) == "Timeout(timeout=30)"  # Default timeout

    @pytest.mark.asyncio
    async def it_fetches_content_successfully(self, scraper):
        mock_response = Mock(
            status_code=200,
            text="<html><body>Test content</body></html>",
            raise_for_status=Mock(),
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            content = await scraper.fetch("https://example.com/page")

            assert content == "<html><body>Test content</body></html>"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def it_retries_on_failure(self, scraper):
        scraper.config.max_retries = 2
        scraper.config.retry_delay = 0.1

        mock_response_fail = Mock(
            status_code=500,
            raise_for_status=Mock(side_effect=httpx.HTTPStatusError("Server error", request=Mock(), response=Mock())),
        )
        mock_response_success = Mock(
            status_code=200,
            text="Success",
            raise_for_status=Mock(),
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [mock_response_fail, mock_response_success]
            content = await scraper.fetch("https://example.com/page")

            assert content == "Success"
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def it_raises_after_max_retries(self, scraper):
        scraper.config.max_retries = 2
        scraper.config.retry_delay = 0.1

        mock_response = Mock(
            status_code=500,
            raise_for_status=Mock(side_effect=httpx.HTTPStatusError("Server error", request=Mock(), response=Mock())),
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(ScraperError, match="Failed after 2 retries"):
                await scraper.fetch("https://example.com/page")

            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def it_implements_exponential_backoff(self, scraper):
        scraper.config.max_retries = 3
        scraper.config.retry_delay = 0.1

        mock_response = Mock(
            status_code=500,
            raise_for_status=Mock(side_effect=httpx.HTTPStatusError("Server error", request=Mock(), response=Mock())),
        )

        delays = []
        original_sleep = asyncio.sleep

        async def track_sleep(delay):
            delays.append(delay)
            await original_sleep(0.01)  # Speed up test

        with (
            patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get,
            patch("asyncio.sleep", side_effect=track_sleep),
            pytest.raises(ScraperError)
        ):
            mock_get.return_value = mock_response
            await scraper.fetch("https://example.com/page")

        # Check exponential backoff: 0.1, 0.2, 0.4
        assert len(delays) == 2  # max_retries - 1
        assert delays[0] == pytest.approx(0.1, rel=0.1)
        assert delays[1] == pytest.approx(0.2, rel=0.1)

    @pytest.mark.asyncio
    async def it_parses_html_content(self, scraper):
        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        soup = await scraper.parse_html(html)

        assert soup.find("h1").text == "Title"
        assert soup.find("p").text == "Content"

    @pytest.mark.asyncio
    async def it_extracts_text_from_elements(self, scraper):
        html = "<div><p>Test content</p></div>"
        soup = await scraper.parse_html(html)
        elem = soup.find("p")

        text = scraper.extract_text(elem)
        assert text == "Test content"

    @pytest.mark.asyncio
    async def it_handles_none_elements_safely(self, scraper):
        text = scraper.extract_text(None)
        assert text == ""

        text = scraper.extract_text(None, default="default")
        assert text == "default"

    @pytest.mark.asyncio
    async def it_extracts_dates_from_text(self, scraper):
        html = "<div><time>2024-03-15</time></div>"
        soup = await scraper.parse_html(html)
        elem = soup.find("time")

        date = scraper.extract_date(elem)
        assert date.date() == datetime(2024, 3, 15).date()

    @pytest.mark.asyncio
    async def it_returns_none_for_invalid_dates(self, scraper):
        html = "<div>not a date</div>"
        soup = await scraper.parse_html(html)
        elem = soup.find("div")

        date = scraper.extract_date(elem)
        assert date is None

    @pytest.mark.asyncio
    async def it_runs_scraping_workflow(self, scraper):
        with patch.object(scraper, "extract_deprecations", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = [{"test": "data"}]

            results = await scraper.run()

            assert results == [{"test": "data"}]
            mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def it_closes_client_on_cleanup(self, scraper):
        client = await scraper._get_client()
        mock_close = AsyncMock()
        client.aclose = mock_close

        await scraper.close()

        mock_close.assert_called_once()
        assert scraper._client is None

    @pytest.mark.asyncio
    async def it_handles_extraction_errors(self, scraper):
        with patch.object(scraper, "extract_deprecations", new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = Exception("Extraction failed")

            with pytest.raises(ExtractionError, match="Extraction failed"):
                await scraper.run()

