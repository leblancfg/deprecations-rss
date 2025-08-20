"""Tests for the base scraper class with error handling."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.scrapers.base import (
    BaseScraper,
    ErrorContext,
    ScraperResult,
    URLValidationError,
    retry_with_backoff,
)


def describe_retry_with_backoff():
    """Test the retry decorator with exponential backoff."""

    async def it_retries_on_failure():
        """Should retry the specified number of times."""
        call_count = 0

        @retry_with_backoff(retries=3, backoff_factor=0.01)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPError("Connection failed")
            return "success"

        result = await failing_function()
        assert result == "success"
        assert call_count == 3

    async def it_raises_after_max_retries():
        """Should raise the exception after max retries."""

        @retry_with_backoff(retries=2, backoff_factor=0.01)
        async def always_failing():
            raise httpx.HTTPError("Connection failed")

        with pytest.raises(httpx.HTTPError):
            await always_failing()

    async def it_returns_immediately_on_success():
        """Should not retry if the function succeeds."""
        call_count = 0

        @retry_with_backoff(retries=3, backoff_factor=0.01)
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()
        assert result == "success"
        assert call_count == 1


def describe_ErrorContext():
    """Test the ErrorContext data class."""

    def it_creates_with_all_fields():
        """Should create ErrorContext with all fields."""
        context = ErrorContext(
            url="https://example.com",
            status_code=404,
            headers={"content-type": "text/html"},
            timestamp=datetime.now(),
            provider="test_provider",
            error_type="NotFound",
            retry_count=2,
            response_body="Not Found",
        )
        assert context.url == "https://example.com"
        assert context.status_code == 404
        assert context.provider == "test_provider"

    def it_creates_with_minimal_fields():
        """Should create ErrorContext with minimal required fields."""
        context = ErrorContext(
            url="https://example.com",
            timestamp=datetime.now(),
            provider="test_provider",
            error_type="Unknown",
        )
        assert context.url == "https://example.com"
        assert context.status_code is None
        assert context.headers is None


def describe_ScraperResult():
    """Test the ScraperResult data class."""

    def it_creates_successful_result():
        """Should create a successful result."""
        data = [{"model": "gpt-4", "deprecation_date": "2024-01-01"}]
        result = ScraperResult(
            success=True,
            provider="openai",
            data=data,
            timestamp=datetime.now(),
        )
        assert result.success is True
        assert result.data == data
        assert result.error is None

    def it_creates_failed_result():
        """Should create a failed result with error context."""
        error = ErrorContext(
            url="https://example.com",
            status_code=500,
            timestamp=datetime.now(),
            provider="openai",
            error_type="ServerError",
        )
        result = ScraperResult(
            success=False,
            provider="openai",
            error=error,
            timestamp=datetime.now(),
        )
        assert result.success is False
        assert result.data is None
        assert result.error == error

    def it_allows_partial_results():
        """Should allow partial data with error."""
        data = [{"model": "gpt-3.5", "deprecation_date": "2024-01-01"}]
        error = ErrorContext(
            url="https://example.com/page2",
            status_code=404,
            timestamp=datetime.now(),
            provider="openai",
            error_type="PartialFailure",
        )
        result = ScraperResult(
            success=False,
            provider="openai",
            data=data,
            error=error,
            timestamp=datetime.now(),
            from_cache=False,
        )
        assert result.success is False
        assert result.data == data
        assert result.error == error


class TestBaseScraper:
    """Test the BaseScraper abstract class."""

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper implementation."""

        class MockScraper(BaseScraper):
            provider_name = "mock_provider"
            base_url = "https://mock.example.com"
            expected_url_patterns = [
                r"https://mock\.example\.com/deprecations",
                r"https://mock\.example\.com/api/.*",
            ]

            async def extract_deprecations(self, content: str) -> list[dict[str, Any]]:
                return [{"model": "mock-model", "deprecation_date": "2024-01-01"}]

        return MockScraper()

    @pytest.mark.asyncio
    async def test_scrape_success(self, mock_scraper):
        """Should successfully scrape and return data."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = "<html>Mock content</html>"

            result = await mock_scraper.scrape()

            assert result.success is True
            assert result.provider == "mock_provider"
            assert len(result.data) == 1
            assert result.data[0]["model"] == "mock-model"

    @pytest.mark.asyncio
    async def test_scrape_with_http_error(self, mock_scraper):
        """Should handle HTTP errors gracefully."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404, headers={}),
            )

            result = await mock_scraper.scrape()

            assert result.success is False
            assert result.error is not None
            assert result.error.status_code == 404
            assert result.error.error_type == "HTTPStatusError"

    @pytest.mark.asyncio
    async def test_scrape_with_connection_error(self, mock_scraper):
        """Should handle connection errors."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.ConnectError("Connection refused")

            result = await mock_scraper.scrape()

            assert result.success is False
            assert result.error is not None
            assert result.error.error_type == "ConnectError"

    @pytest.mark.asyncio
    async def test_validate_url_success(self, mock_scraper):
        """Should validate URLs matching expected patterns."""
        valid_urls = [
            "https://mock.example.com/deprecations",
            "https://mock.example.com/api/v1/models",
        ]

        for url in valid_urls:
            mock_scraper.validate_url(url)  # Should not raise

    def test_validate_url_failure(self, mock_scraper):
        """Should raise error for URLs not matching patterns."""
        invalid_urls = [
            "https://wrong.example.com/deprecations",
            "http://mock.example.com/deprecations",  # Wrong protocol
            "https://mock.example.com",  # No path
        ]

        for url in invalid_urls:
            with pytest.raises(URLValidationError):
                mock_scraper.validate_url(url)

    @pytest.mark.asyncio
    async def test_fetch_content_with_retries(self, mock_scraper):
        """Should retry fetching content on failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Fail twice, then succeed
            mock_response = MagicMock()
            mock_response.text = "Success content"
            mock_response.raise_for_status = MagicMock()

            mock_client.get.side_effect = [
                httpx.ConnectError("Failed"),
                httpx.ConnectError("Failed again"),
                mock_response,
            ]

            with patch.object(mock_scraper, "retry_delay", 0.01):
                content = await mock_scraper.fetch_content("https://mock.example.com/test")

            assert content == "Success content"
            assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_handle_url_change(self, mock_scraper):
        """Should detect and handle URL changes."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            # Simulate a redirect
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Moved",
                request=MagicMock(),
                response=MagicMock(
                    status_code=301,
                    headers={"Location": "https://new.example.com/deprecations"},
                ),
            )

            result = await mock_scraper.scrape()

            assert result.success is False
            assert result.error is not None
            assert result.error.status_code == 301
            assert "Location" in result.error.headers

    @pytest.mark.asyncio
    async def test_scrape_with_timeout(self, mock_scraper):
        """Should handle timeout errors."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Request timed out")

            result = await mock_scraper.scrape()

            assert result.success is False
            assert result.error is not None
            assert result.error.error_type == "TimeoutException"

    @pytest.mark.asyncio
    async def test_extract_deprecations_error(self, mock_scraper):
        """Should handle extraction errors."""
        with patch.object(mock_scraper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = "<html>Valid content</html>"

            with patch.object(mock_scraper, "extract_deprecations") as mock_extract:
                mock_extract.side_effect = ValueError("Parsing error")

                result = await mock_scraper.scrape()

                assert result.success is False
                assert result.error is not None
                assert result.error.error_type == "ValueError"

    def test_create_error_context(self, mock_scraper):
        """Should create proper error context from exception."""
        error = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(
                status_code=404,
                headers={"content-type": "text/html"},
            ),
        )

        context = mock_scraper.create_error_context(
            error, "https://example.com", retry_count=2
        )

        assert context.url == "https://example.com"
        assert context.status_code == 404
        assert context.headers == {"content-type": "text/html"}
        assert context.retry_count == 2
        assert context.provider == "mock_provider"
        assert context.error_type == "HTTPStatusError"
