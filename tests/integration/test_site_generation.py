"""Integration tests for static site generation."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.site.generator import StaticSiteGenerator


class TestSiteGenerationIntegration:
    """Integration tests for complete site generation."""

    @pytest.fixture
    def sample_feed_data(self) -> FeedData:
        """Create comprehensive sample feed data."""
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
                    notes=None,
                    source_url="https://cloud.google.com/deprecations",
                ),
            ],
            provider_statuses=[
                ProviderStatus(
                    name="OpenAI",
                    last_checked=datetime(2024, 12, 20, 15, 30),
                    is_healthy=True,
                    error_message=None,
                ),
                ProviderStatus(
                    name="Anthropic",
                    last_checked=datetime(2024, 12, 20, 15, 30),
                    is_healthy=True,
                    error_message=None,
                ),
                ProviderStatus(
                    name="Google",
                    last_checked=datetime(2024, 12, 20, 15, 30),
                    is_healthy=False,
                    error_message="Connection timeout",
                ),
            ],
            last_updated=datetime(2024, 12, 20, 15, 30),
        )

    def test_complete_site_generation(self, sample_feed_data: FeedData):
        """Test complete site generation with all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            generator.generate_site()

            # Check that output directory was created
            assert output_dir.exists()
            assert output_dir.is_dir()

            # Check that index.html was created
            index_file = output_dir / "index.html"
            assert index_file.exists()

            # Check that CSS was copied
            css_file = output_dir / "styles.css"
            assert css_file.exists()

            # Verify HTML content
            html_content = index_file.read_text()

            # Check for RSS feed link
            assert "https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml" in html_content

            # Check for deprecation entries (should be sorted newest first)
            assert "gpt-3.5-turbo-0301" in html_content
            assert "claude-instant-1.2" in html_content
            assert "palm-2" in html_content

            # Verify order (newest first)
            gpt_pos = html_content.index("gpt-3.5-turbo-0301")
            claude_pos = html_content.index("claude-instant-1.2")
            palm_pos = html_content.index("palm-2")
            assert gpt_pos < claude_pos < palm_pos

            # Check for provider statuses
            assert "OpenAI" in html_content
            assert "Anthropic" in html_content
            assert "Google" in html_content
            assert "Healthy" in html_content
            assert "Error" in html_content
            assert "Connection timeout" in html_content

            # Check for last updated timestamp
            assert "2024-12-20 15:30 UTC" in html_content

            # Verify proper HTML structure
            assert "<!DOCTYPE html>" in html_content
            assert '<html lang="en">' in html_content
            assert "</html>" in html_content

    def test_site_generation_without_css(self, sample_feed_data: FeedData):
        """Test site generation when CSS file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(sample_feed_data, output_dir=output_dir)

            # Remove CSS file if it exists
            css_source = Path(generator.env.loader.searchpath[0]).parent / "styles.css"
            if css_source.exists():
                original_css = css_source.read_text()
                css_source.unlink()

            try:
                generator.generate_site()

                # Should still generate HTML even without CSS
                assert (output_dir / "index.html").exists()
                assert not (output_dir / "styles.css").exists()
            finally:
                # Restore CSS file for other tests
                if "original_css" in locals():
                    css_source.write_text(original_css)

    def test_empty_feed_generation(self):
        """Test site generation with no deprecations."""
        empty_feed = FeedData(
            deprecations=[],
            provider_statuses=[
                ProviderStatus(
                    name="OpenAI", last_checked=datetime.now(), is_healthy=True, error_message=None
                )
            ],
            last_updated=datetime.now(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "site"
            generator = StaticSiteGenerator(empty_feed, output_dir=output_dir)

            generator.generate_site()

            html_content = (output_dir / "index.html").read_text()

            # Should show empty state message
            assert "No deprecations to display" in html_content

            # Should still show provider status
            assert "OpenAI" in html_content
            assert "Healthy" in html_content
