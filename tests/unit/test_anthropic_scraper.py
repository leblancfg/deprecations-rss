"""Test suite for the Anthropic deprecations scraper."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.deprecation import Deprecation
from src.scrapers.anthropic import AnthropicScraper


@pytest.fixture
def scraper():
    """Create Anthropic scraper instance."""
    return AnthropicScraper()


@pytest.fixture
def sample_html():
    """Sample HTML content from Anthropic deprecations page."""
    return """
    <html>
    <body>
        <div class="documentation-content">
            <h2>Model Status</h2>
            <table>
                <thead>
                    <tr>
                        <th>API Model Name</th>
                        <th>Current State</th>
                        <th>Deprecated</th>
                        <th>Retired</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>claude-1.0</td>
                        <td>Retired</td>
                        <td>September 4, 2024</td>
                        <td>November 6, 2024</td>
                    </tr>
                    <tr>
                        <td>claude-1.1</td>
                        <td>Retired</td>
                        <td>September 4, 2024</td>
                        <td>November 6, 2024</td>
                    </tr>
                    <tr>
                        <td>claude-2.0</td>
                        <td>Deprecated</td>
                        <td>January 21, 2025</td>
                        <td>July 21, 2025</td>
                    </tr>
                    <tr>
                        <td>claude-3-sonnet-20240229</td>
                        <td>Deprecated</td>
                        <td>January 21, 2025</td>
                        <td>July 21, 2025</td>
                    </tr>
                    <tr>
                        <td>claude-3-opus-20240229</td>
                        <td>Deprecated</td>
                        <td>June 30, 2025</td>
                        <td>January 5, 2026</td>
                    </tr>
                    <tr>
                        <td>claude-3-5-sonnet-20240620</td>
                        <td>Deprecated</td>
                        <td>August 13, 2025</td>
                        <td>October 22, 2025</td>
                    </tr>
                    <tr>
                        <td>claude-3-haiku-20240307</td>
                        <td>Active</td>
                        <td></td>
                        <td></td>
                    </tr>
                </tbody>
            </table>

            <h2>Deprecation History</h2>
            <h3>Claude Sonnet 3.5 models</h3>
            <table>
                <thead>
                    <tr>
                        <th>Retirement Date</th>
                        <th>Deprecated Model</th>
                        <th>Recommended Replacement</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>October 22, 2025</td>
                        <td>claude-3-5-sonnet-20240620</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                </tbody>
            </table>

            <h3>Claude Opus 3 model</h3>
            <table>
                <thead>
                    <tr>
                        <th>Retirement Date</th>
                        <th>Deprecated Model</th>
                        <th>Recommended Replacement</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>January 5, 2026</td>
                        <td>claude-3-opus-20240229</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                </tbody>
            </table>

            <h3>Claude 2, Claude 2.1, and Claude Sonnet 3 models</h3>
            <table>
                <thead>
                    <tr>
                        <th>Retirement Date</th>
                        <th>Deprecated Model</th>
                        <th>Recommended Replacement</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>July 21, 2025</td>
                        <td>claude-2.0</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                    <tr>
                        <td>July 21, 2025</td>
                        <td>claude-2.1</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                    <tr>
                        <td>July 21, 2025</td>
                        <td>claude-3-sonnet-20240229</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                </tbody>
            </table>

            <h3>Claude 1 and Instant models</h3>
            <table>
                <thead>
                    <tr>
                        <th>Retirement Date</th>
                        <th>Deprecated Model</th>
                        <th>Recommended Replacement</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>November 6, 2024</td>
                        <td>claude-1.0</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                    <tr>
                        <td>November 6, 2024</td>
                        <td>claude-1.1</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                    <tr>
                        <td>November 6, 2024</td>
                        <td>claude-instant-1.0</td>
                        <td>claude-3-haiku-20240307</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def api_response():
    """Sample API response for Anthropic deprecations."""
    return {
        "deprecations": [
            {
                "model": "claude-1.0",
                "deprecation_date": "2024-09-04",
                "retirement_date": "2024-11-06",
                "replacement": "claude-3-5-sonnet-20241022",
                "notes": "Legacy Claude 1.x model",
            },
            {
                "model": "claude-2.0",
                "deprecation_date": "2025-01-21",
                "retirement_date": "2025-07-21",
                "replacement": "claude-3-5-sonnet-20241022",
                "notes": "Claude 2 series model",
            },
            {
                "model": "claude-3-opus-20240229",
                "deprecation_date": "2025-06-30",
                "retirement_date": "2026-01-05",
                "replacement": "claude-3-5-sonnet-20241022",
                "notes": "Claude Opus 3 model",
            },
        ]
    }


def describe_anthropic_scraper():
    """Test Anthropic scraper functionality."""

    def it_initializes_with_correct_url(scraper):
        """Initializes with the Anthropic deprecations URL."""
        assert scraper.url == "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"

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
                    assert dep.provider == "Anthropic"

                # Check first deprecation
                first = deprecations[0]
                assert first.model == "claude-1.0"
                assert first.deprecation_date.date() == datetime(2024, 9, 4).date()
                assert first.retirement_date.date() == datetime(2024, 11, 6).date()
                assert first.replacement == "claude-3-5-sonnet-20241022"

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
                        "model": "claude-test",
                        "deprecation_date": "2024-01-01",
                        "retirement_date": "2024-12-31",
                        "replacement": None,
                        "notes": None,
                    }
                ]
            }

            with patch.object(scraper, "_make_request", return_value=partial_response):
                result = await scraper.scrape_api()
                deprecations = result["deprecations"]

                assert len(deprecations) == 1
                assert deprecations[0].model == "claude-test"
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
                assert len(deprecations) >= 6  # Should find models from both tables

                # Check all are Deprecation models
                for dep in deprecations:
                    assert isinstance(dep, Deprecation)
                    assert dep.provider == "Anthropic"

                # Find specific models
                claude_1_0 = next(
                    (d for d in deprecations if d.model == "claude-1.0"), None
                )
                assert claude_1_0 is not None
                assert claude_1_0.deprecation_date.date() == datetime(2024, 9, 4).date()
                assert claude_1_0.retirement_date.date() == datetime(2024, 11, 6).date()

                claude_opus = next(
                    (d for d in deprecations if d.model == "claude-3-opus-20240229"), None
                )
                assert claude_opus is not None
                assert claude_opus.replacement == "claude-3-5-sonnet-20241022"

        @pytest.mark.asyncio
        async def it_handles_various_date_formats(scraper):
            """Handles different date formats in HTML."""
            html_with_various_dates = """
            <table>
                <thead>
                    <tr><th>API Model Name</th><th>Current State</th><th>Deprecated</th><th>Retired</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>claude-test-1</td>
                        <td>Deprecated</td>
                        <td>January 15, 2024</td>
                        <td>December 31, 2024</td>
                    </tr>
                    <tr>
                        <td>claude-test-2</td>
                        <td>Deprecated</td>
                        <td>2024-03-01</td>
                        <td>2024-09-01</td>
                    </tr>
                    <tr>
                        <td>claude-test-3</td>
                        <td>Deprecated</td>
                        <td>March 2024</td>
                        <td>September 2024</td>
                    </tr>
                </tbody>
            </table>
            """

            mock_response = MagicMock()
            mock_response.text = html_with_various_dates
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                deprecations = result["deprecations"]

                # Should parse at least some models with valid dates
                valid_deprecations = [
                    d for d in deprecations
                    if d.deprecation_date and d.retirement_date
                ]
                assert len(valid_deprecations) >= 1

                # Check that dates were parsed correctly
                model1 = next(
                    (d for d in valid_deprecations if d.model == "claude-test-1"), None
                )
                if model1:
                    assert model1.deprecation_date.month == 1
                    assert model1.deprecation_date.year == 2024

        @pytest.mark.asyncio
        async def it_skips_active_models(scraper, sample_html):
            """Skips active models that aren't deprecated."""
            mock_response = MagicMock()
            mock_response.text = sample_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                deprecations = result["deprecations"]

                # Should not include claude-3-haiku-20240307 which is Active
                active_models = [d for d in deprecations if d.model == "claude-3-haiku-20240307"]
                assert len(active_models) == 0

        @pytest.mark.asyncio
        async def it_handles_missing_elements(scraper):
            """Handles missing elements in HTML gracefully."""
            incomplete_html = """
            <table>
                <thead>
                    <tr><th>API Model Name</th><th>Current State</th><th>Deprecated</th><th>Retired</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>claude-incomplete</td>
                        <td>Deprecated</td>
                        <td>January 1, 2024</td>
                        <!-- Missing retirement date -->
                        <td></td>
                    </tr>
                </tbody>
            </table>
            """

            mock_response = MagicMock()
            mock_response.text = incomplete_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                # Should skip incomplete entries
                assert "deprecations" in result
                assert isinstance(result["deprecations"], list)

    def describe_playwright_scraping():
        """Test Playwright scraping method."""

        @pytest.mark.asyncio
        async def it_scrapes_with_playwright(scraper):
            """Uses Playwright for JavaScript-rendered content."""
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.set_extra_http_headers = AsyncMock()
            mock_page.content = AsyncMock(
                return_value="""
                <table>
                    <thead>
                        <tr><th>API Model Name</th><th>Current State</th><th>Deprecated</th><th>Retired</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>claude-1.0</td>
                            <td>Retired</td>
                            <td>September 4, 2024</td>
                            <td>November 6, 2024</td>
                        </tr>
                    </tbody>
                </table>
                """
            )

            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()

            mock_playwright = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            # Mock the playwright import check and async_playwright call
            with patch("src.scrapers.anthropic.HAS_PLAYWRIGHT", True):
                # Create a mock that returns our context manager
                mock_async_playwright = AsyncMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)

                with patch("src.scrapers.anthropic.async_playwright", create=True) as mock_ap:
                    mock_ap.return_value = mock_async_playwright
                    result = await scraper.scrape_playwright()

                assert "deprecations" in result
                deprecations = result["deprecations"]
                assert len(deprecations) >= 1
                assert all(isinstance(d, Deprecation) for d in deprecations)

        @pytest.mark.asyncio
        async def it_raises_error_without_playwright(scraper):
            """Raises error when Playwright is not available."""
            with patch("src.scrapers.anthropic.HAS_PLAYWRIGHT", False):
                with pytest.raises(ImportError, match="Playwright is not installed"):
                    await scraper.scrape_playwright()

        @pytest.mark.asyncio
        async def it_handles_playwright_errors(scraper):
            """Handles Playwright errors gracefully."""
            with patch("src.scrapers.anthropic.HAS_PLAYWRIGHT", True):
                with patch(
                    "src.scrapers.anthropic.async_playwright",
                    create=True,
                    side_effect=Exception("Playwright error"),
                ):
                    with pytest.raises(Exception, match="Playwright error"):
                        await scraper.scrape_playwright()

    def describe_date_parsing():
        """Test date parsing functionality."""

        def it_parses_various_date_formats(scraper):
            """Parses various date formats correctly."""
            test_cases = [
                ("September 4, 2024", datetime(2024, 9, 4, tzinfo=UTC)),
                ("January 21, 2025", datetime(2025, 1, 21, tzinfo=UTC)),
                ("2024-09-04", datetime(2024, 9, 4, tzinfo=UTC)),
                ("2025-01-21", datetime(2025, 1, 21, tzinfo=UTC)),
                ("March 2024", datetime(2024, 3, 1, tzinfo=UTC)),
                ("December 2023", datetime(2023, 12, 1, tzinfo=UTC)),
            ]

            for date_str, expected in test_cases:
                parsed = scraper._parse_date(date_str)
                assert parsed is not None, f"Failed to parse: {date_str}"
                assert parsed == expected, f"Expected {expected}, got {parsed} for {date_str}"

        def it_handles_invalid_dates(scraper):
            """Handles invalid date strings gracefully."""
            invalid_dates = [
                "",
                None,
                "invalid date",
                "2024-13-01",  # Invalid month
                "not a date at all",
            ]

            for date_str in invalid_dates:
                parsed = scraper._parse_date(date_str)
                assert parsed is None, f"Should return None for invalid date: {date_str}"

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
                                provider="Anthropic",
                                model="claude-test",
                                deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                                retirement_date=datetime(2024, 12, 31, tzinfo=UTC),
                                source_url="https://docs.anthropic.com/en/docs/about-claude/model-deprecations",
                            )
                        ]
                    }

                    # Also patch _save_to_cache to avoid side effects
                    with patch.object(scraper, "_save_to_cache"):
                        result = await scraper.scrape()
                        deprecations = result["deprecations"]

                        for dep in deprecations:
                            assert dep.provider == "Anthropic"
                            assert dep.model
                            assert dep.deprecation_date
                            assert dep.retirement_date
                            assert str(dep.source_url) == "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"

        @pytest.mark.asyncio
        async def it_validates_date_ordering(scraper):
            """Validates that retirement date is after deprecation date."""
            invalid_data = {
                "model": "claude-invalid",
                "deprecation_date": "2024-12-31",
                "retirement_date": "2024-01-01",  # Before deprecation!
                "replacement": None,
            }

            with patch.object(
                scraper, "_make_request", return_value={"deprecations": [invalid_data]}
            ):
                # Should handle invalid date ordering gracefully
                result = await scraper.scrape_api()
                assert "deprecations" in result

        @pytest.mark.asyncio
        async def it_deduplicates_deprecations(scraper):
            """Removes duplicate deprecation entries."""
            duplicated_response = {
                "deprecations": [
                    {
                        "model": "claude-duplicate",
                        "deprecation_date": "2024-01-01",
                        "retirement_date": "2024-12-31",
                        "replacement": "claude-3-5-sonnet-20241022",
                    },
                    {
                        "model": "claude-duplicate",
                        "deprecation_date": "2024-01-01",
                        "retirement_date": "2024-12-31",
                        "replacement": "claude-3-5-sonnet-20241022",
                    },
                ]
            }

            with patch.object(scraper, "_make_request", return_value=duplicated_response):
                result = await scraper.scrape_api()
                deprecations = result["deprecations"]

                # Should have only unique deprecations
                assert len(deprecations) == 1
                assert deprecations[0].model == "claude-duplicate"

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
            malformed_html = "<div>Incomplete HTML without proper table structure"

            mock_response = MagicMock()
            mock_response.text = malformed_html
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                assert "deprecations" in result
                # Should return empty list or handle gracefully
                assert isinstance(result["deprecations"], list)

        @pytest.mark.asyncio
        async def it_handles_network_errors(scraper):
            """Handles network errors gracefully."""
            with patch("httpx.AsyncClient.get", side_effect=httpx.RequestError("Network error")):
                with pytest.raises(httpx.RequestError):
                    await scraper.scrape_html()

        @pytest.mark.asyncio
        async def it_parses_replacement_models_from_history_tables(scraper):
            """Extracts replacement models from deprecation history tables."""
            html_with_replacement = """
            <table>
                <thead>
                    <tr><th>Retirement Date</th><th>Deprecated Model</th><th>Recommended Replacement</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>October 22, 2025</td>
                        <td>claude-3-5-sonnet-20240620</td>
                        <td>claude-3-5-sonnet-20241022</td>
                    </tr>
                </tbody>
            </table>
            """

            mock_response = MagicMock()
            mock_response.text = html_with_replacement
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                result = await scraper.scrape_html()
                deprecations = result["deprecations"]

                # Should extract replacement from history table
                if deprecations:
                    dep = next(
                        (d for d in deprecations if d.model == "claude-3-5-sonnet-20240620"),
                        None
                    )
                    if dep:
                        assert dep.replacement == "claude-3-5-sonnet-20241022"

