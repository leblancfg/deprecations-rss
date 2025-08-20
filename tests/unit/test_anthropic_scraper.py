"""Tests for Anthropic deprecations scraper."""

import re
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.scrapers.anthropic import AnthropicScraper


def describe_AnthropicScraper():
    """Test the Anthropic deprecations scraper."""

    @pytest.fixture
    def scraper(self):
        """Create an Anthropic scraper instance."""
        return AnthropicScraper()

    @pytest.fixture
    def sample_deprecations_html(self):
        """Sample HTML content from Anthropic deprecations page."""
        return """
        <html>
        <body>
            <div class="docs-content">
                <h1>Model Deprecations</h1>
                
                <div class="deprecation-section">
                    <h2>Claude 2.0 Deprecation</h2>
                    <p>Claude 2.0 will be deprecated on March 1, 2024.</p>
                    <p>Please migrate to Claude 2.1 or Claude 3 for improved performance.</p>
                </div>
                
                <div class="model-lifecycle">
                    <h3>Model Lifecycle</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Model</th>
                                <th>Status</th>
                                <th>End of Life</th>
                                <th>Suggested Alternative</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>claude-instant-1.0</td>
                                <td>Deprecated</td>
                                <td>January 15, 2024</td>
                                <td>claude-instant-1.2</td>
                            </tr>
                            <tr>
                                <td>claude-1.3</td>
                                <td>Legacy</td>
                                <td>February 1, 2024</td>
                                <td>claude-2.1</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="api-changes">
                    <h2>API Version Changes</h2>
                    <ul>
                        <li>API v1 will be sunset on April 1, 2024. Migrate to v2.</li>
                        <li>The /complete endpoint is deprecated. Use /messages instead.</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_api_response(self):
        """Sample API response with deprecation info."""
        return {
            "models": [
                {
                    "id": "claude-2.0",
                    "status": "deprecated",
                    "deprecation_date": "2024-01-01",
                    "end_of_life": "2024-03-01",
                    "replacement": "claude-2.1"
                },
                {
                    "id": "claude-instant-1.1",
                    "status": "active",
                    "deprecation_date": null,
                    "end_of_life": null,
                    "replacement": null
                }
            ],
            "api_versions": {
                "v1": {
                    "status": "deprecated",
                    "sunset_date": "2024-04-01",
                    "replacement": "v2"
                }
            }
        }

    async def it_initializes_with_correct_settings(self, scraper):
        """Should initialize with Anthropic-specific settings."""
        assert scraper.provider_name == "anthropic"
        assert "anthropic.com" in scraper.base_url
        assert len(scraper.expected_url_patterns) > 0

    async def it_extracts_deprecations_from_html(self, scraper, sample_deprecations_html):
        """Should extract deprecations from HTML content."""
        deprecations = await scraper.extract_deprecations(sample_deprecations_html)

        assert len(deprecations) >= 2

        # Check Claude 2.0 deprecation
        claude2_dep = next(
            d for d in deprecations if d["model"] == "claude-2.0"
        )
        assert claude2_dep["retirement_date"] == "2024-03-01"
        assert "claude-2.1" in claude2_dep.get("replacement", "") or "claude-3" in claude2_dep.get("replacement", "")

    async def it_extracts_from_lifecycle_table(self, scraper, sample_deprecations_html):
        """Should extract from model lifecycle table."""
        deprecations = await scraper.extract_deprecations(sample_deprecations_html)

        # Check instant model
        instant_dep = next(
            d for d in deprecations if d["model"] == "claude-instant-1.0"
        )
        assert instant_dep["retirement_date"] == "2024-01-15"
        assert instant_dep["replacement"] == "claude-instant-1.2"

    async def it_handles_api_deprecations(self, scraper, sample_api_response):
        """Should handle API response format."""
        import json
        json_content = json.dumps(sample_api_response)

        deprecations = await scraper.extract_api_deprecations(json_content)

        # Should extract deprecated models
        model_deps = [d for d in deprecations if "model" in d]
        assert len(model_deps) >= 1

        claude2 = next(d for d in model_deps if d["model"] == "claude-2.0")
        assert claude2["deprecation_date"] == "2024-01-01"
        assert claude2["retirement_date"] == "2024-03-01"

    async def it_extracts_api_version_changes(self, scraper, sample_deprecations_html):
        """Should extract API version deprecations."""
        deprecations = await scraper.extract_deprecations(sample_deprecations_html)

        # Check for API deprecations
        api_deps = [d for d in deprecations if d.get("type") == "api_version"]
        assert len(api_deps) >= 1

        v1_dep = next((d for d in api_deps if "v1" in str(d.get("version", ""))), None)
        assert v1_dep is not None

    async def it_normalizes_model_names(self, scraper):
        """Should normalize various Claude model name formats."""
        names = [
            ("Claude 2.0", "claude-2.0"),
            ("claude-instant-1.2", "claude-instant-1.2"),
            ("Claude Instant 1.0", "claude-instant-1.0"),
            ("CLAUDE-2.1", "claude-2.1"),
        ]

        for input_name, expected in names:
            normalized = scraper.normalize_model_name(input_name)
            assert normalized == expected

    async def it_validates_anthropic_urls(self, scraper):
        """Should validate Anthropic-specific URLs."""
        valid_urls = [
            "https://docs.anthropic.com/deprecations",
            "https://docs.anthropic.com/en/api/deprecations",
            "https://api.anthropic.com/v1/models",
        ]

        for url in valid_urls:
            scraper.validate_url(url)  # Should not raise

    async def it_handles_multiple_date_formats(self, scraper):
        """Should handle Anthropic's date formats."""
        html = """
        <div>
            <p>claude-1.0: EOL on 2024-01-15</p>
            <p>claude-1.1: Retiring January 20, 2024</p>
            <p>claude-1.2: Deprecated 15/02/2024</p>
            <p>claude-1.3: End of support Feb 28, 2024</p>
        </div>
        """

        deprecations = await scraper.extract_deprecations(html)

        # All dates should be normalized to ISO format
        for dep in deprecations:
            if "retirement_date" in dep:
                assert re.match(r"\d{4}-\d{2}-\d{2}", dep["retirement_date"])

    async def it_detects_url_changes(self, scraper):
        """Should detect when Anthropic changes their documentation structure."""
        with patch.object(scraper, "fetch_content") as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(
                    status_code=404,
                    headers={},
                ),
            )

            result = await scraper.scrape()

            assert result.success is False
            assert result.error.status_code == 404

    async def it_extracts_claude_3_models(self, scraper):
        """Should handle Claude 3 family models."""
        html = """
        <div>
            <h2>Claude 3 Models</h2>
            <p>claude-3-opus-20240229 will be deprecated on March 1, 2025</p>
            <p>claude-3-sonnet-20240229 will be deprecated on March 1, 2025</p>
            <p>claude-3-haiku-20240307 will be deprecated on March 7, 2025</p>
            <p>Please migrate to the latest Claude 3.5 versions.</p>
        </div>
        """

        deprecations = await scraper.extract_deprecations(html)

        # Should extract all Claude 3 models
        claude3_models = [d for d in deprecations if "claude-3" in d.get("model", "")]
        assert len(claude3_models) >= 3

        # Check specific model
        opus = next(d for d in claude3_models if "opus" in d["model"])
        assert opus["retirement_date"] == "2025-03-01"

    async def it_handles_legacy_model_notices(self, scraper):
        """Should extract legacy model deprecations."""
        html = """
        <div class="legacy-notice">
            <h3>Legacy Models</h3>
            <p>The following models are now considered legacy and will be removed:</p>
            <ul>
                <li>claude-v1: End of life December 31, 2023</li>
                <li>claude-v1.2: Sunset January 15, 2024</li>
                <li>claude-v1.3-100k: Retiring February 1, 2024</li>
            </ul>
            <p>Recommended: Upgrade to Claude 2.1 or newer.</p>
        </div>
        """

        deprecations = await scraper.extract_deprecations(html)

        # Should extract legacy models
        legacy_models = [d for d in deprecations if "claude-v1" in d.get("model", "")]
        assert len(legacy_models) >= 3

        # Check replacement is extracted
        for model in legacy_models:
            assert "claude-2.1" in model.get("replacement", "").lower() or model.get("replacement") is None

    async def it_scrapes_with_fallback_urls(self, scraper):
        """Should try multiple URLs if primary fails."""
        with patch.object(scraper, "fetch_content") as mock_fetch:
            # First URL fails, second succeeds
            mock_fetch.side_effect = [
                httpx.HTTPError("Connection failed"),
                "<html><body>Fallback content</body></html>",
            ]

            with patch.object(scraper, "extract_deprecations") as mock_extract:
                mock_extract.return_value = [{"model": "test"}]

                result = await scraper.scrape_all_sources()

                assert result.success is True
                assert mock_fetch.call_count >= 2
