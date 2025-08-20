"""Tests for OpenAI deprecations scraper."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.scrapers.openai import OpenAIScraper


def describe_OpenAIScraper():
    """Test the OpenAI deprecations scraper."""

    @pytest.fixture
    def scraper(self):
        """Create an OpenAI scraper instance."""
        return OpenAIScraper()

    @pytest.fixture
    def sample_deprecations_html(self):
        """Sample HTML content from OpenAI deprecations page."""
        return """
        <html>
        <body>
            <div class="deprecations">
                <h2>Deprecations</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>Deprecation Date</th>
                            <th>Shutdown Date</th>
                            <th>Replacement</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>gpt-3.5-turbo-0301</td>
                            <td>June 13, 2023</td>
                            <td>June 13, 2024</td>
                            <td>gpt-3.5-turbo-0125</td>
                        </tr>
                        <tr>
                            <td>text-davinci-003</td>
                            <td>January 4, 2024</td>
                            <td>January 4, 2025</td>
                            <td>gpt-3.5-turbo-instruct</td>
                        </tr>
                    </tbody>
                </table>
                
                <div class="deprecation-notice">
                    <h3>Legacy Models</h3>
                    <p>The following models will be deprecated on March 1, 2024:</p>
                    <ul>
                        <li>text-curie-001 - Use gpt-3.5-turbo instead</li>
                        <li>text-babbage-001 - Use gpt-3.5-turbo instead</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_api_deprecations_json(self):
        """Sample JSON response for API deprecations."""
        return {
            "deprecations": [
                {
                    "model": "gpt-4-0314",
                    "deprecation_date": "2023-06-13",
                    "shutdown_date": "2024-06-13",
                    "replacement": "gpt-4-0613",
                    "notes": "Improved function calling"
                },
                {
                    "endpoint": "/v1/engines",
                    "deprecation_date": "2023-11-06",
                    "shutdown_date": "2024-11-06",
                    "replacement": "/v1/models",
                    "type": "api_endpoint"
                }
            ]
        }

    async def it_initializes_with_correct_settings(self, scraper):
        """Should initialize with OpenAI-specific settings."""
        assert scraper.provider_name == "openai"
        assert scraper.base_url == "https://platform.openai.com/docs/deprecations"
        assert len(scraper.expected_url_patterns) > 0

    async def it_extracts_deprecations_from_html(self, scraper, sample_deprecations_html):
        """Should extract deprecations from HTML content."""
        deprecations = await scraper.extract_deprecations(sample_deprecations_html)

        assert len(deprecations) >= 2

        # Check first deprecation
        gpt35_deprecation = next(
            d for d in deprecations if d["model"] == "gpt-3.5-turbo-0301"
        )
        assert gpt35_deprecation["deprecation_date"] == "2023-06-13"
        assert gpt35_deprecation["retirement_date"] == "2024-06-13"
        assert gpt35_deprecation["replacement"] == "gpt-3.5-turbo-0125"

    async def it_extracts_legacy_models(self, scraper, sample_deprecations_html):
        """Should extract legacy model deprecations from notices."""
        deprecations = await scraper.extract_deprecations(sample_deprecations_html)

        # Check for legacy models
        curie_deprecation = next(
            (d for d in deprecations if d["model"] == "text-curie-001"), None
        )
        assert curie_deprecation is not None
        assert curie_deprecation["replacement"] == "gpt-3.5-turbo"

    async def it_handles_api_deprecations_json(self, scraper, sample_api_deprecations_json):
        """Should handle JSON API deprecations."""
        import json
        json_content = json.dumps(sample_api_deprecations_json)

        deprecations = await scraper.extract_api_deprecations(json_content)

        assert len(deprecations) == 2

        # Check model deprecation
        model_dep = next(d for d in deprecations if "model" in d)
        assert model_dep["model"] == "gpt-4-0314"
        assert model_dep["notes"] == "Improved function calling"

        # Check API endpoint deprecation
        api_dep = next(d for d in deprecations if d.get("type") == "api_endpoint")
        assert api_dep["endpoint"] == "/v1/engines"
        assert api_dep["replacement"] == "/v1/models"

    async def it_fetches_from_multiple_sources(self, scraper):
        """Should attempt to fetch from multiple sources."""
        with patch.object(scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = [
                scraper.sample_deprecations_html,
                '{"deprecations": []}',
            ]

            with patch.object(scraper, "extract_deprecations") as mock_extract:
                mock_extract.return_value = [{"model": "test"}]

                result = await scraper.scrape()

                assert result.success is True
                assert mock_fetch.call_count >= 1

    async def it_handles_parsing_errors_gracefully(self, scraper):
        """Should handle malformed HTML gracefully."""
        malformed_html = "<html><body>Invalid content</invalid></body>"

        deprecations = await scraper.extract_deprecations(malformed_html)

        # Should return empty list or handle gracefully
        assert isinstance(deprecations, list)

    async def it_validates_openai_urls(self, scraper):
        """Should validate OpenAI-specific URLs."""
        valid_urls = [
            "https://platform.openai.com/docs/deprecations",
            "https://api.openai.com/v1/deprecations",
            "https://platform.openai.com/docs/api-reference/deprecations",
        ]

        for url in valid_urls:
            scraper.validate_url(url)  # Should not raise

    async def it_normalizes_date_formats(self, scraper):
        """Should normalize various date formats to ISO."""
        dates = [
            ("June 13, 2023", "2023-06-13"),
            ("2023-06-13", "2023-06-13"),
            ("13/06/2023", "2023-06-13"),
            ("Jun 13, 2023", "2023-06-13"),
        ]

        for input_date, expected in dates:
            normalized = scraper.normalize_date(input_date)
            assert normalized == expected

    async def it_scrapes_with_cache_fallback(self, scraper):
        """Should use cache as fallback on failure."""
        from src.scrapers.cache import CacheEntry

        cache_manager = MagicMock()
        cached_data = [{"model": "cached-model", "deprecation_date": "2024-01-01"}]
        cache_entry = CacheEntry(
            provider="openai",
            data=cached_data,
            timestamp=datetime.now(),
            expires_at=datetime.now(),
        )
        cache_manager.load.return_value = cache_entry

        with patch.object(scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPError("Connection failed")

            result = await scraper.scrape_with_cache(cache_manager)

            # Should fall back to cache
            assert result.from_cache is True
            assert result.data == cached_data

    async def it_detects_url_changes(self, scraper):
        """Should detect when OpenAI changes their URL structure."""
        with patch.object(scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Moved",
                request=MagicMock(),
                response=MagicMock(
                    status_code=301,
                    headers={"Location": "https://platform.openai.com/new-deprecations"},
                ),
            )

            result = await scraper.scrape()

            assert result.success is False
            assert result.error.status_code == 301
            assert "Location" in result.error.headers

    async def it_extracts_model_families(self, scraper):
        """Should group deprecations by model family."""
        html = """
        <div>
            <h3>GPT-3.5 Turbo Deprecations</h3>
            <p>gpt-3.5-turbo-0301 deprecated on June 13, 2024</p>
            <p>gpt-3.5-turbo-0613 deprecated on June 13, 2025</p>
            
            <h3>GPT-4 Deprecations</h3>
            <p>gpt-4-0314 deprecated on June 13, 2024</p>
            <p>gpt-4-32k-0314 deprecated on June 13, 2024</p>
        </div>
        """

        deprecations = await scraper.extract_deprecations(html)

        # Should extract all models
        model_names = [d.get("model") for d in deprecations if "model" in d]
        assert "gpt-3.5-turbo-0301" in model_names
        assert "gpt-4-0314" in model_names
