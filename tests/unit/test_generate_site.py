"""Tests for the generate_site script."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.site.generate_site import (
    generate_site_from_real_data,
    load_data_from_json,
    save_data_to_json,
    scrape_real_data,
)


class TestScrapeRealData:
    """Tests for scraping real data."""

    @pytest.mark.asyncio
    async def test_successful_scrape(self):
        """Test successful scraping returns deprecations and healthy status."""
        mock_deprecations = [
            DeprecationEntry(
                provider="Anthropic",
                model="claude-2",
                deprecation_date=datetime(2024, 7, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 10, 1, tzinfo=UTC),
                replacement="claude-3",
                notes="Upgrading to Claude 3",
                source_url="https://anthropic.com/deprecations",
            )
        ]

        with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
            mock_scraper = MockScraper.return_value
            mock_scraper.scrape = AsyncMock(return_value={"deprecations": mock_deprecations})

            deprecations, status = await scrape_real_data()

            assert len(deprecations) == 1
            assert deprecations[0].model == "claude-2"
            assert status.name == "Anthropic"
            assert status.is_healthy is True
            assert status.error_message is None

    @pytest.mark.asyncio
    async def test_failed_scrape(self):
        """Test failed scraping returns empty list and unhealthy status."""
        with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
            mock_scraper = MockScraper.return_value
            mock_scraper.scrape = AsyncMock(side_effect=Exception("Connection failed"))

            deprecations, status = await scrape_real_data()

            assert len(deprecations) == 0
            assert status.name == "Anthropic"
            assert status.is_healthy is False
            assert "Connection failed" in status.error_message

    @pytest.mark.asyncio
    async def test_empty_scrape_result(self):
        """Test scraping with no deprecations returns empty list."""
        with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
            mock_scraper = MockScraper.return_value
            mock_scraper.scrape = AsyncMock(return_value={"deprecations": []})

            deprecations, status = await scrape_real_data()

            assert len(deprecations) == 0
            assert status.is_healthy is True


class TestDataPersistence:
    """Tests for data persistence to/from JSON."""

    def test_save_and_load_data(self):
        """Test saving and loading FeedData to/from JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Create test data
            deprecations = [
                DeprecationEntry(
                    provider="TestProvider",
                    model="test-model-1",
                    deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                    retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
                    replacement="new-model",
                    notes="Test notes",
                    source_url="https://example.com",
                )
            ]
            provider_statuses = [
                ProviderStatus(
                    name="TestProvider",
                    last_checked=datetime(2024, 3, 1, tzinfo=UTC),
                    is_healthy=True,
                    error_message=None,
                )
            ]
            feed_data = FeedData(
                deprecations=deprecations,
                provider_statuses=provider_statuses,
                last_updated=datetime(2024, 3, 1, tzinfo=UTC),
            )

            # Save data
            save_data_to_json(feed_data, tmp_path)
            assert tmp_path.exists()

            # Load data
            loaded_data = load_data_from_json(tmp_path)
            assert loaded_data is not None
            assert len(loaded_data.deprecations) == 1
            assert loaded_data.deprecations[0].model == "test-model-1"
            assert len(loaded_data.provider_statuses) == 1
            assert loaded_data.provider_statuses[0].name == "TestProvider"

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading from a non-existent file returns None."""
        result = load_data_from_json(Path("/nonexistent/file.json"))
        assert result is None

    def test_load_invalid_json(self):
        """Test loading invalid JSON returns None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("invalid json content")
            tmp_path = Path(tmp.name)

        try:
            result = load_data_from_json(tmp_path)
            assert result is None
        finally:
            tmp_path.unlink()


class TestGenerateSiteFromRealData:
    """Tests for the main site generation function."""

    @pytest.mark.asyncio
    async def test_uses_real_data_when_available(self):
        """Test that real data is used when scraping succeeds."""
        mock_deprecations = [
            DeprecationEntry(
                provider="Anthropic",
                model="claude-instant",
                deprecation_date=datetime(2024, 8, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 11, 1, tzinfo=UTC),
                replacement="claude-3-haiku",
                notes="Upgrade available",
                source_url="https://anthropic.com/deprecations",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": mock_deprecations})

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir)

                    # Check that generator was called with real data
                    MockGenerator.assert_called_once()
                    feed_data = MockGenerator.call_args[0][0]
                    assert len(feed_data.deprecations) == 1
                    assert feed_data.deprecations[0].model == "claude-instant"
                    assert feed_data.provider_statuses[0].is_healthy is True

    @pytest.mark.asyncio
    async def test_loads_from_data_json_when_scraping_fails(self):
        """Test that data.json is used when scraping fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            data_file = Path(tmpdir) / "data.json"

            # Create test data.json
            test_data = {
                "deprecations": [
                    {
                        "provider": "TestProvider",
                        "model": "cached-model",
                        "deprecation_date": "2024-01-01T00:00:00+00:00",
                        "retirement_date": "2024-06-01T00:00:00+00:00",
                        "replacement": "new-model",
                        "notes": "From cache",
                        "source_url": "https://example.com",
                        "last_updated": "2024-03-01T00:00:00+00:00",
                    }
                ],
                "provider_statuses": [
                    {
                        "name": "TestProvider",
                        "last_checked": "2024-03-01T00:00:00+00:00",
                        "is_healthy": True,
                        "error_message": None,
                    }
                ],
                "last_updated": "2024-03-01T00:00:00+00:00",
            }
            with open(data_file, "w") as f:
                json.dump(test_data, f)

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(side_effect=Exception("Network error"))

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir, data_file)

                    # Check that generator was called with cached data
                    MockGenerator.assert_called_once()
                    feed_data = MockGenerator.call_args[0][0]
                    assert len(feed_data.deprecations) == 1
                    assert feed_data.deprecations[0].model == "cached-model"

    @pytest.mark.asyncio
    async def test_no_generation_when_no_data_available(self):
        """Test that site generation is skipped when no data is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            data_file = Path(tmpdir) / "nonexistent.json"  # File doesn't exist

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": []})

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir, data_file)

                    # Check that generator was NOT called
                    MockGenerator.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_scraped_data_to_json(self):
        """Test that successfully scraped data is saved to data.json."""
        mock_deprecations = [
            DeprecationEntry(
                provider="Anthropic",
                model="test-model",
                deprecation_date=datetime(2024, 8, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 11, 1, tzinfo=UTC),
                replacement="new-model",
                notes="Test",
                source_url="https://example.com",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            data_file = Path(tmpdir) / "data.json"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": mock_deprecations})

                with patch("src.site.generate_site.StaticSiteGenerator"):
                    await generate_site_from_real_data(output_dir, data_file)

                    # Check that data was saved
                    assert data_file.exists()
                    with open(data_file) as f:
                        saved_data = json.load(f)
                    assert len(saved_data["deprecations"]) == 1
                    assert saved_data["deprecations"][0]["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_handles_generator_error(self):
        """Test that generator errors are handled properly."""
        mock_deprecations = [
            DeprecationEntry(
                provider="Anthropic",
                model="test-model",
                deprecation_date=datetime(2024, 8, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 11, 1, tzinfo=UTC),
                replacement="new-model",
                notes="Test",
                source_url="https://example.com",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": mock_deprecations})

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    MockGenerator.return_value.generate_site.side_effect = Exception(
                        "Template error"
                    )

                    with pytest.raises(Exception) as exc_info:
                        await generate_site_from_real_data(output_dir)

                    assert "Template error" in str(exc_info.value)
