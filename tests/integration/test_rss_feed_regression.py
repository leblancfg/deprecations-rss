"""Comprehensive regression tests for RSS feed generation.

This test suite ensures that the RSS feed generation continues to work correctly
as part of the site generation pipeline. It tests the complete end-to-end flow
and various edge cases to prevent regressions like Issue #28.

Test Coverage:
- RSS feed is always generated alongside HTML during site generation
- RSS feed contains actual deprecation data (not empty)
- RSS feed is saved to correct GitHub Pages location (docs/rss/v1/feed.xml)
- RSS feed is valid XML with proper RSS 2.0 structure
- RSS feed contains required metadata (title, description, link)
- Deprecation entries have all required RSS item fields
- Edge cases: empty feeds, single entries, many entries
- End-to-end pipeline testing with mocked data sources
- Error scenarios: directory creation, missing fields, invalid dates
- Concurrent generation safety
- Proper error handling and logging

These tests specifically prevent the type of issue where the RSS feed
generation silently fails or produces invalid output that breaks feed readers.
"""

import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.site.generate_site import generate_site_from_real_data
from src.site.generator import StaticSiteGenerator


@pytest.fixture
def sample_feed_data() -> FeedData:
    """Create comprehensive sample feed data for testing."""
    return FeedData(
        deprecations=[
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-3.5-turbo-0301",
                deprecation_date=datetime(2024, 12, 20),
                retirement_date=datetime(2025, 1, 15),
                replacement="gpt-3.5-turbo",
                notes="Legacy snapshot model being retired",
                source_url="https://platform.openai.com/docs/deprecations",
            ),
            DeprecationEntry(
                provider="Anthropic",
                model="claude-instant-1.2",
                deprecation_date=datetime(2024, 12, 15),
                retirement_date=datetime(2025, 2, 1),
                replacement="claude-3-haiku",
                notes="Upgrading to Claude 3 family models",
                source_url="https://docs.anthropic.com/deprecations",
            ),
            DeprecationEntry(
                provider="Google",
                model="palm-2",
                deprecation_date=datetime(2024, 11, 30),
                retirement_date=datetime(2025, 3, 30),
                replacement="gemini-pro",
                notes=None,  # Test handling of missing notes
                source_url="https://cloud.google.com/deprecations",
            ),
        ],
        provider_statuses=[
            ProviderStatus(
                name="OpenAI",
                last_checked=datetime(2024, 12, 20, 15, 30, tzinfo=UTC),
                is_healthy=True,
                error_message=None,
            ),
            ProviderStatus(
                name="Anthropic",
                last_checked=datetime(2024, 12, 20, 15, 30, tzinfo=UTC),
                is_healthy=True,
                error_message=None,
            ),
            ProviderStatus(
                name="Google",
                last_checked=datetime(2024, 12, 20, 15, 30, tzinfo=UTC),
                is_healthy=False,
                error_message="Connection timeout",
            ),
        ],
        last_updated=datetime(2024, 12, 20, 15, 30, tzinfo=UTC),
    )


@pytest.fixture
def empty_feed_data() -> FeedData:
    """Create empty feed data for edge case testing."""
    return FeedData(
        deprecations=[],
        provider_statuses=[
            ProviderStatus(
                name="OpenAI",
                last_checked=datetime.now(UTC),
                is_healthy=True,
                error_message=None,
            ),
        ],
        last_updated=datetime.now(UTC),
    )


class TestRSSFeedRegression:
    """Regression tests for RSS feed generation pipeline."""

    def test_rss_feed_always_generated_with_site(self, sample_feed_data: FeedData):
        """Test that RSS feed is always generated when site is generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            # Generate complete site
            generator.generate_site()

            # Verify HTML was generated
            assert (output_dir / "index.html").exists()

            # Verify RSS feed was generated at correct location
            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists(), "RSS feed must be generated at docs/rss/v1/feed.xml"

            # Verify RSS directory structure
            assert rss_path.parent.exists()
            assert rss_path.parent.name == "v1"
            assert rss_path.parent.parent.name == "rss"

    def test_rss_feed_contains_actual_deprecation_data(self, sample_feed_data: FeedData):
        """Test that RSS feed contains actual deprecation data (not empty)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            rss_content = rss_path.read_text()

            # Verify all test deprecations are present
            assert "OpenAI - gpt-3.5-turbo-0301 Deprecation" in rss_content
            assert "Anthropic - claude-instant-1.2 Deprecation" in rss_content
            assert "Google - palm-2 Deprecation" in rss_content

            # Verify deprecation details are included
            assert "Legacy snapshot model being retired" in rss_content
            assert "Upgrading to Claude 3 family models" in rss_content
            assert "gpt-3.5-turbo" in rss_content  # replacement
            assert "claude-3-haiku" in rss_content  # replacement
            assert "gemini-pro" in rss_content  # replacement

    def test_rss_feed_saved_to_correct_location(self, sample_feed_data: FeedData):
        """Test that RSS feed is saved to the correct GitHub Pages location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "docs"  # Use GitHub Pages directory name
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            # Verify exact expected path structure
            expected_path = output_dir / "rss" / "v1" / "feed.xml"
            assert expected_path.exists(), f"RSS feed must be at {expected_path}"

            # Verify the path matches what's referenced in HTML
            html_content = (output_dir / "index.html").read_text()
            assert "https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml" in html_content

    def test_rss_feed_is_valid_xml(self, sample_feed_data: FeedData):
        """Test that generated RSS feed is valid XML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            rss_content = rss_path.read_text()

            # Parse XML to verify it's valid
            try:
                root = ET.fromstring(rss_content)
            except ET.ParseError as e:
                pytest.fail(f"Generated RSS feed is not valid XML: {e}")

            # Verify root element
            assert root.tag == "rss"
            assert root.get("version") == "2.0"

            # Verify channel element exists
            channel = root.find("channel")
            assert channel is not None, "RSS feed must contain a channel element"

    def test_rss_feed_contains_required_metadata(self, sample_feed_data: FeedData):
        """Test that RSS feed contains all required metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            root = ET.fromstring(rss_path.read_text())
            channel = root.find("channel")

            # Required RSS 2.0 fields
            assert channel.find("title") is not None
            assert channel.find("description") is not None
            assert channel.find("link") is not None

            # Verify specific values
            title = channel.find("title").text
            description = channel.find("description").text
            link = channel.find("link").text

            assert title == "AI Model Deprecations"
            assert "RSS feed tracking AI model deprecations" in description
            assert "https://leblancfg.github.io/deprecations-rss/" in link

            # Additional recommended fields
            assert channel.find("language") is not None
            assert channel.find("lastBuildDate") is not None
            assert channel.find("generator") is not None
            assert channel.find("ttl") is not None

    def test_deprecation_entries_have_required_fields(self, sample_feed_data: FeedData):
        """Test that all deprecation entries have required RSS item fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            root = ET.fromstring(rss_path.read_text())
            channel = root.find("channel")
            items = channel.findall("item")

            # Should have 3 items matching our sample data
            assert len(items) == 3

            for item in items:
                # Required fields for each item
                assert item.find("title") is not None
                assert item.find("description") is not None
                assert item.find("guid") is not None
                assert item.find("pubDate") is not None

                # Verify content is meaningful
                title = item.find("title").text
                description = item.find("description").text
                guid = item.find("guid").text
                pub_date = item.find("pubDate").text

                assert "Deprecation" in title
                assert "Provider:" in description
                assert "Model:" in description
                assert guid is not None and len(guid) > 0
                assert pub_date is not None and len(pub_date) > 0

    def test_empty_feed_generation(self, empty_feed_data: FeedData):
        """Test RSS feed generation with no deprecations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(empty_feed_data, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists(), "RSS feed should be generated even with no deprecations"

            root = ET.fromstring(rss_path.read_text())
            channel = root.find("channel")
            items = channel.findall("item")

            # Should have no items but still be valid RSS
            assert len(items) == 0

            # Should still have required metadata
            assert channel.find("title") is not None
            assert channel.find("description") is not None
            assert channel.find("link") is not None

    def test_single_deprecation_feed(self):
        """Test RSS feed generation with only one deprecation."""
        single_item_feed = FeedData(
            deprecations=[
                DeprecationEntry(
                    provider="OpenAI",
                    model="test-model",
                    deprecation_date=datetime(2024, 1, 1),
                    retirement_date=datetime(2024, 6, 1),
                    source_url="https://example.com/test",
                ),
            ],
            provider_statuses=[
                ProviderStatus(
                    name="OpenAI",
                    last_checked=datetime.now(UTC),
                    is_healthy=True,
                    error_message=None,
                ),
            ],
            last_updated=datetime.now(UTC),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(single_item_feed, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            root = ET.fromstring(rss_path.read_text())
            channel = root.find("channel")
            items = channel.findall("item")

            assert len(items) == 1

            item = items[0]
            title = item.find("title").text
            assert "OpenAI - test-model" in title

    def test_many_deprecations_feed(self):
        """Test RSS feed generation with many deprecations."""
        # Create a large number of deprecations to test performance and structure
        deprecations = []
        for i in range(50):
            deprecations.append(
                DeprecationEntry(
                    provider=f"Provider{i % 5}",
                    model=f"model-{i:03d}",
                    deprecation_date=datetime(2024, 1, (i % 30) + 1),
                    retirement_date=datetime(2024, 6, (i % 30) + 1),
                    source_url=f"https://provider{i % 5}.com/deprecation-{i}",
                )
            )

        large_feed = FeedData(
            deprecations=deprecations,
            provider_statuses=[
                ProviderStatus(
                    name=f"Provider{i}",
                    last_checked=datetime.now(UTC),
                    is_healthy=True,
                    error_message=None,
                )
                for i in range(5)
            ],
            last_updated=datetime.now(UTC),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(large_feed, output_dir=output_dir)

            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists()

            root = ET.fromstring(rss_path.read_text())
            channel = root.find("channel")
            items = channel.findall("item")

            # Should have all 50 items
            assert len(items) == 50

            # Verify RSS is still valid with many items
            assert channel.find("title") is not None
            assert channel.find("description") is not None


class TestEndToEndPipeline:
    """End-to-end tests for the complete site generation pipeline."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_with_real_site_generation(self):
        """Test the complete pipeline from site generation script to RSS output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "complete_site"

            # Mock the scraper to avoid network calls
            with patch("src.site.generate_site.AnthropicScraper") as mock_scraper_class:
                mock_scraper = AsyncMock()
                mock_scraper.scrape.return_value = {
                    "deprecations": [
                        DeprecationEntry(
                            provider="Anthropic",
                            model="claude-2.1",
                            deprecation_date=datetime(2024, 12, 1),
                            retirement_date=datetime(2025, 1, 1),
                            replacement="claude-3-opus",
                            source_url="https://docs.anthropic.com/deprecations",
                        )
                    ]
                }
                mock_scraper_class.return_value = mock_scraper

                # Run the complete site generation
                await generate_site_from_real_data(output_dir)

            # Verify complete site structure
            assert output_dir.exists()
            assert (output_dir / "index.html").exists()
            assert (output_dir / "styles.css").exists()

            # Verify RSS feed exists and has correct content
            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists()

            rss_content = rss_path.read_text()
            assert "claude-2.1" in rss_content
            assert "Anthropic" in rss_content

            # Verify XML structure
            root = ET.fromstring(rss_content)
            assert root.tag == "rss"

            # Verify feed URL is correctly referenced in HTML
            html_content = (output_dir / "index.html").read_text()
            assert "https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml" in html_content

    def test_rss_generation_survives_html_generation_failure(self, sample_feed_data: FeedData):
        """Test that RSS can be generated even if other parts fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            # Directly call RSS generation (simulating partial failure scenario)
            generator._generate_rss()

            # RSS should still be generated
            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists()

            # Verify it contains expected data
            rss_content = rss_path.read_text()
            assert "OpenAI - gpt-3.5-turbo-0301" in rss_content


class TestErrorScenarios:
    """Tests for error handling and edge cases in RSS generation."""

    def test_docs_directory_creation(self, sample_feed_data: FeedData):
        """Test that RSS generation creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a non-existent directory path
            output_dir = Path(tmpdir) / "new" / "nested" / "path"
            assert not output_dir.exists()

            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)
            generator.generate_site()

            # Directories should be created
            assert output_dir.exists()
            assert (output_dir / "rss" / "v1").exists()
            assert (output_dir / "rss" / "v1" / "feed.xml").exists()

    def test_rss_generation_with_missing_optional_fields(self):
        """Test RSS generation when deprecations have missing optional fields."""
        minimal_deprecation = DeprecationEntry(
            provider="TestProvider",
            model="test-model",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement=None,  # Optional field missing
            notes=None,  # Optional field missing
            source_url="https://example.com",
        )

        feed_data = FeedData(
            deprecations=[minimal_deprecation],
            provider_statuses=[
                ProviderStatus(
                    name="TestProvider",
                    last_checked=datetime.now(UTC),
                    is_healthy=True,
                    error_message=None,
                )
            ],
            last_updated=datetime.now(UTC),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(feed_data, output_dir=output_dir)

            # Should not raise an exception
            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists()

            # Should still contain the deprecation
            rss_content = rss_path.read_text()
            assert "TestProvider - test-model" in rss_content

    def test_invalid_dates_handling(self):
        """Test handling of edge cases with dates."""
        # Test with timezone-naive dates (should still work)
        deprecation = DeprecationEntry(
            provider="TestProvider",
            model="test-model",
            deprecation_date=datetime(2024, 1, 1),  # No timezone
            retirement_date=datetime(2024, 6, 1),  # No timezone
            source_url="https://example.com",
        )

        feed_data = FeedData(
            deprecations=[deprecation],
            provider_statuses=[],
            last_updated=datetime.now(UTC),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(feed_data, output_dir=output_dir)

            # Should handle timezone conversion gracefully
            generator.generate_site()

            rss_path = output_dir / "rss" / "v1" / "feed.xml"
            assert rss_path.exists()

            # Verify the XML is still valid
            root = ET.fromstring(rss_path.read_text())
            assert root.tag == "rss"

    def test_rss_generation_logs_appropriately(self, sample_feed_data: FeedData, caplog):
        """Test that RSS generation provides appropriate logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            with caplog.at_level("DEBUG"):
                generator.generate_site()

            # RSS generation should not produce error logs
            error_logs = [
                record for record in caplog.records if record.levelno >= 40
            ]  # ERROR and above
            assert len(error_logs) == 0, f"Unexpected error logs: {[r.message for r in error_logs]}"

    def test_concurrent_rss_generation(self, sample_feed_data: FeedData):
        """Test that RSS generation works correctly with concurrent access patterns."""
        import threading

        results = []
        errors = []

        def generate_in_thread(thread_id: int):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_dir = Path(tmpdir) / f"site_{thread_id}"
                    generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)
                    generator.generate_site()

                    rss_path = output_dir / "rss" / "v1" / "feed.xml"
                    results.append(rss_path.exists())
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # Run multiple threads concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=generate_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should succeed
        assert len(errors) == 0, f"Concurrent generation errors: {errors}"
        assert all(results), "All RSS feeds should be generated successfully"
        assert len(results) == 5
