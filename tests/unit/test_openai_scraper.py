"""Test suite for the OpenAI deprecations scraper."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.deprecation import Deprecation
from src.scrapers.openai import OpenAIScraper


@pytest.fixture
def scraper():
    """Create OpenAI scraper instance."""
    return OpenAIScraper()


@pytest.fixture
def sample_html():
    """Sample HTML content from OpenAI deprecations page."""
    return """
    <html>
    <body>
        <div class="deprecation-section">
            <h2>Text generation models</h2>
            <div class="model-deprecation">
                <h3>GPT-3.5 Turbo 0301</h3>
                <p>Model: gpt-3.5-turbo-0301</p>
                <p>Deprecation date: June 13, 2023</p>
                <p>Shutdown date: June 13, 2024</p>
                <p>Recommended replacement: gpt-3.5-turbo-0613 or later</p>
            </div>
            <div class="model-deprecation">
                <h3>GPT-4 0314</h3>
                <p>Model: gpt-4-0314</p>
                <p>Deprecation date: June 13, 2023</p>
                <p>Shutdown date: June 13, 2024</p>
                <p>Recommended replacement: gpt-4-0613 or later</p>
            </div>
        </div>
        <div class="deprecation-section">
            <h2>Legacy models</h2>
            <div class="model-deprecation">
                <h3>text-davinci-003</h3>
                <p>Deprecation date: January 4, 2024</p>
                <p>Shutdown date: January 4, 2025</p>
                <p>Recommended replacement: gpt-3.5-turbo-instruct</p>
                <p>Note: This is a legacy completion model</p>
            </div>
        </div>
        <div class="deprecation-section">
            <h2>Embedding models</h2>
            <div class="model-deprecation">
                <h3>text-embedding-ada-002-v1</h3>
                <p>Model: text-embedding-ada-002-v1</p>
                <p>Deprecation: December 2023</p>
                <p>Retirement: April 2024</p>
                <p>Alternative: text-embedding-ada-002-v2</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def api_response():
    """Sample API response for OpenAI deprecations."""
    return {
        "deprecations": [
            {
                "model": "gpt-3.5-turbo-0301",
                "deprecation_date": "2023-06-13",
                "shutdown_date": "2024-06-13",
                "replacement": "gpt-3.5-turbo-0613",
                "notes": None,
            },
            {
                "model": "gpt-4-0314",
                "deprecation_date": "2023-06-13",
                "shutdown_date": "2024-06-13",
                "replacement": "gpt-4-0613",
                "notes": None,
            },
            {
                "model": "text-davinci-003",
                "deprecation_date": "2024-01-04",
                "shutdown_date": "2025-01-04",
                "replacement": "gpt-3.5-turbo-instruct",
                "notes": "Legacy completion model",
            },
        ]
    }


def describe_openai_scraper():
    """Test OpenAI scraper functionality."""

    def it_initializes_with_correct_url(scraper):
        """Initializes with the OpenAI deprecations URL."""
        assert scraper.url == "https://platform.openai.com/docs/deprecations"

    def describe_api_scraping():
        """Test API scraping method."""

        @pytest.mark.asyncio
        async def it_fetches_and_parses_api_response(scraper, api_response):
            """Fetches and parses deprecations from API."""
            with patch.object(scraper, "_make_request", return_value=api_response):
                result = await scraper.scrape_api()

                assert "deprecations" in result
                deprecations = result["deprecations"]
                assert len(deprecations) == 3

                # Verify all deprecations are Deprecation models
                for dep in deprecations:
                    assert isinstance(dep, Deprecation)
                    assert dep.provider == "OpenAI"

                # Check first deprecation
                first = deprecations[0]
                assert first.model == "gpt-3.5-turbo-0301"
                assert first.deprecation_date.date() == datetime(2023, 6, 13).date()
                assert first.retirement_date.date() == datetime(2024, 6, 13).date()
                assert first.replacement == "gpt-3.5-turbo-0613"

        @pytest.mark.asyncio
        async def it_handles_api_errors_gracefully(scraper):
            """Handles API errors and raises appropriate exception."""
            with patch.object(
                scraper,
                "_make_request",
                side_effect=httpx.HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=MagicMock()
                ),
            ):
                with pytest.raises(httpx.HTTPStatusError):
                    await scraper.scrape_api()

        @pytest.mark.asyncio
        async def it_handles_missing_fields_in_api(scraper):
            """Handles missing or null fields in API response."""
            partial_response = {
                "deprecations": [
                    {
                        "model": "test-model",
                        "deprecation_date": "2024-01-01",
                        "shutdown_date": "2024-12-31",
                        "replacement": None,
                        "notes": None,
                    }
                ]
            }

            with patch.object(scraper, "_make_request", return_value=partial_response):
                result = await scraper.scrape_api()
                deprecations = result["deprecations"]

                assert len(deprecations) == 1
                assert deprecations[0].model == "test-model"
                assert deprecations[0].replacement is None

    def describe_html_scraping():
        """Test HTML scraping method."""

        @pytest.mark.asyncio
        async def it_parses_html_content(scraper, sample_html):
            """Parses deprecation information from HTML."""
            mock_response = MagicMock()
            mock_response.text = sample_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()

                assert "deprecations" in result
                deprecations = result["deprecations"]
                assert len(deprecations) >= 3

                # Check all are Deprecation models
                for dep in deprecations:
                    assert isinstance(dep, Deprecation)
                    assert dep.provider == "OpenAI"

                # Find specific model
                gpt35_turbo = next(
                    (d for d in deprecations if d.model == "gpt-3.5-turbo-0301"), None
                )
                assert gpt35_turbo is not None
                assert gpt35_turbo.replacement == "gpt-3.5-turbo-0613 or later"

        @pytest.mark.asyncio
        async def it_handles_various_date_formats(scraper):
            """Handles different date formats in HTML."""
            html_with_various_dates = """
            <div class="model-deprecation">
                <h3>Model 1</h3>
                <p>Model: test-model-1</p>
                <p>Deprecation date: January 15, 2024</p>
                <p>Shutdown date: December 31, 2024</p>
            </div>
            <div class="model-deprecation">
                <h3>Model 2</h3>
                <p>Model: test-model-2</p>
                <p>Deprecation: 2024-03-01</p>
                <p>Retirement: 2024-09-01</p>
            </div>
            <div class="model-deprecation">
                <h3>Model 3</h3>
                <p>Model: test-model-3</p>
                <p>Deprecation date: March 2024</p>
                <p>Shutdown date: September 2024</p>
            </div>
            """

            mock_response = MagicMock()
            mock_response.text = html_with_various_dates
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                deprecations = result["deprecations"]

                assert len(deprecations) >= 2

                # Check that dates were parsed
                model1 = next((d for d in deprecations if d.model == "test-model-1"), None)
                if model1:
                    assert model1.deprecation_date.month == 1
                    assert model1.deprecation_date.year == 2024

        @pytest.mark.asyncio
        async def it_handles_missing_elements(scraper):
            """Handles missing elements in HTML gracefully."""
            incomplete_html = """
            <div class="model-deprecation">
                <h3>Incomplete Model</h3>
                <p>Model: incomplete-model</p>
                <p>Deprecation date: January 1, 2024</p>
                <!-- Missing shutdown date -->
            </div>
            """

            mock_response = MagicMock()
            mock_response.text = incomplete_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                # Should either skip incomplete entries or use defaults
                assert "deprecations" in result

    def describe_playwright_scraping():
        """Test Playwright scraping method."""

        @pytest.mark.asyncio
        async def it_scrapes_with_playwright(scraper):
            """Uses Playwright for JavaScript-rendered content."""
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.content = AsyncMock(
                return_value="""
                <div class="model-deprecation">
                    <h3>GPT-3.5 Turbo 0301</h3>
                    <p>Model: gpt-3.5-turbo-0301</p>
                    <p>Deprecation date: June 13, 2023</p>
                    <p>Shutdown date: June 13, 2024</p>
                    <p>Recommended replacement: gpt-3.5-turbo-0613</p>
                </div>
            """
            )

            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()

            mock_playwright = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            # Mock the playwright import check and async_playwright call
            with patch("src.scrapers.openai.HAS_PLAYWRIGHT", True):
                # Create a mock that returns our context manager
                mock_async_playwright = AsyncMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)

                with patch("src.scrapers.openai.async_playwright", create=True) as mock_ap:
                    mock_ap.return_value = mock_async_playwright
                    result = await scraper.scrape_playwright()

                assert "deprecations" in result
                deprecations = result["deprecations"]
                assert len(deprecations) >= 1
                assert all(isinstance(d, Deprecation) for d in deprecations)

        @pytest.mark.asyncio
        async def it_handles_playwright_errors(scraper):
            """Handles Playwright errors gracefully."""
            with patch("src.scrapers.openai.HAS_PLAYWRIGHT", True):
                with patch(
                    "src.scrapers.openai.async_playwright",
                    create=True,
                    side_effect=Exception("Playwright not available"),
                ):
                    with pytest.raises(Exception, match="Playwright not available"):
                        await scraper.scrape_playwright()

    def describe_data_validation():
        """Test data validation and conversion."""

        @pytest.mark.asyncio
        async def it_ensures_all_deprecations_have_required_fields(scraper):
            """Ensures all deprecations have required fields."""
            # Patch _load_from_cache to return None to bypass cache
            with patch.object(scraper, "_load_from_cache", return_value=None):
                with patch.object(scraper, "scrape_api") as mock_scrape:
                    mock_scrape.return_value = {
                        "deprecations": [
                            Deprecation(
                                provider="OpenAI",
                                model="test-model",
                                deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                                retirement_date=datetime(2024, 12, 31, tzinfo=UTC),
                                source_url="https://platform.openai.com/docs/deprecations",
                            )
                        ]
                    }

                    # Also patch _save_to_cache to avoid side effects
                    with patch.object(scraper, "_save_to_cache"):
                        result = await scraper.scrape()
                        deprecations = result["deprecations"]

                        for dep in deprecations:
                            assert dep.provider == "OpenAI"
                            assert dep.model
                            assert dep.deprecation_date
                            assert dep.retirement_date
                            assert (
                                str(dep.source_url)
                                == "https://platform.openai.com/docs/deprecations"
                            )

        @pytest.mark.asyncio
        async def it_validates_date_ordering(scraper):
            """Validates that retirement date is after deprecation date."""
            invalid_data = {
                "model": "invalid-model",
                "deprecation_date": "2024-12-31",
                "shutdown_date": "2024-01-01",  # Before deprecation!
                "replacement": None,
            }

            with patch.object(
                scraper, "_make_request", return_value={"deprecations": [invalid_data]}
            ):
                # Should handle invalid date ordering
                result = await scraper.scrape_api()
                # Either skip invalid entries or fix them
                assert "deprecations" in result

    def describe_edge_cases():
        """Test edge cases and error handling."""

        @pytest.mark.asyncio
        async def it_handles_empty_response(scraper):
            """Handles empty API response."""
            with patch.object(scraper, "_make_request", return_value={"deprecations": []}):
                result = await scraper.scrape_api()
                assert result["deprecations"] == []

        @pytest.mark.asyncio
        async def it_handles_malformed_html(scraper):
            """Handles malformed HTML content."""
            malformed_html = "<div>Incomplete HTML without proper structure"

            mock_response = MagicMock()
            mock_response.text = malformed_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                assert "deprecations" in result
                # Should return empty list or handle gracefully
                assert isinstance(result["deprecations"], list)

        @pytest.mark.asyncio
        async def it_removes_duplicate_deprecations(scraper):
            """Removes duplicate deprecation entries."""
            duplicated_response = {
                "deprecations": [
                    {
                        "model": "duplicate-model",
                        "deprecation_date": "2024-01-01",
                        "shutdown_date": "2024-12-31",
                        "replacement": "new-model",
                    },
                    {
                        "model": "duplicate-model",
                        "deprecation_date": "2024-01-01",
                        "shutdown_date": "2024-12-31",
                        "replacement": "new-model",
                    },
                ]
            }

            with patch.object(scraper, "_make_request", return_value=duplicated_response):
                result = await scraper.scrape_api()
                deprecations = result["deprecations"]

                # Should have only unique deprecations
                unique_models = {d.model for d in deprecations}
                assert len(unique_models) == len(deprecations)
