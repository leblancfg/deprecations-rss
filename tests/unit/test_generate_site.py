"""Tests for the generate_site script."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.deprecation import DeprecationEntry, FeedData
from src.site.generate_site import (
    generate_site_from_real_data,
    scrape_real_data,
    use_mock_data_fallback,
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


class TestMockDataFallback:
    """Tests for mock data fallback."""

    def test_returns_feed_data(self):
        """Test that mock data fallback returns valid FeedData."""
        feed = use_mock_data_fallback()

        assert isinstance(feed, FeedData)
        assert len(feed.deprecations) > 0
        assert len(feed.provider_statuses) > 0
        assert isinstance(feed.last_updated, datetime)

    def test_contains_multiple_providers(self):
        """Test that mock data contains deprecations from multiple providers."""
        feed = use_mock_data_fallback()

        providers = {dep.provider for dep in feed.deprecations}
        assert len(providers) >= 3  # Should have at least 3 different providers


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
    async def test_falls_back_to_mock_when_scraping_fails(self):
        """Test that mock data is used when scraping fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(side_effect=Exception("Network error"))

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir)

                    # Check that generator was called with mock data
                    MockGenerator.assert_called_once()
                    feed_data = MockGenerator.call_args[0][0]
                    assert len(feed_data.deprecations) > 5  # Mock data has many deprecations

    @pytest.mark.asyncio
    async def test_falls_back_to_mock_when_no_deprecations(self):
        """Test that mock data is used when scraping returns no deprecations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": []})

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir)

                    # Check that generator was called with mock data
                    MockGenerator.assert_called_once()
                    feed_data = MockGenerator.call_args[0][0]
                    assert len(feed_data.deprecations) > 0  # Should have mock deprecations

    @pytest.mark.asyncio
    async def test_updates_anthropic_status_in_mock_data(self):
        """Test that Anthropic status is updated in mock data when using fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"

            with patch("src.site.generate_site.AnthropicScraper") as MockScraper:
                mock_scraper = MockScraper.return_value
                mock_scraper.scrape = AsyncMock(return_value={"deprecations": []})

                with patch("src.site.generate_site.StaticSiteGenerator") as MockGenerator:
                    await generate_site_from_real_data(output_dir)

                    # Check that Anthropic status was updated
                    feed_data = MockGenerator.call_args[0][0]
                    anthropic_status = next(
                        (s for s in feed_data.provider_statuses if s.name == "Anthropic"), None
                    )
                    assert anthropic_status is not None
                    assert anthropic_status.is_healthy is True
                    assert "No deprecations found" in (anthropic_status.error_message or "")

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
