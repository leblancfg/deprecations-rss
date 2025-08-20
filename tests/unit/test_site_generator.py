"""Tests for the static site generator."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from jinja2 import Environment

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.site.generator import StaticSiteGenerator


class TestStaticSiteGenerator:
    """Test cases for StaticSiteGenerator class."""

    @pytest.fixture
    def sample_feed_data(self) -> FeedData:
        """Create sample feed data for testing."""
        return FeedData(
            deprecations=[
                DeprecationEntry(
                    provider="OpenAI",
                    model="gpt-3.5-turbo",
                    deprecation_date=datetime(2024, 12, 1),
                    retirement_date=datetime(2025, 1, 1),
                    replacement="gpt-4",
                    notes="Legacy model being phased out",
                    source_url="https://openai.com/deprecations",
                ),
                DeprecationEntry(
                    provider="Anthropic",
                    model="claude-2",
                    deprecation_date=datetime(2024, 11, 15),
                    retirement_date=datetime(2025, 1, 15),
                    replacement="claude-3",
                    notes=None,
                    source_url="https://anthropic.com/deprecations",
                ),
            ],
            provider_statuses=[
                ProviderStatus(
                    name="OpenAI",
                    last_checked=datetime(2024, 12, 20, 12, 0),
                    is_healthy=True,
                    error_message=None,
                ),
                ProviderStatus(
                    name="Anthropic",
                    last_checked=datetime(2024, 12, 20, 12, 0),
                    is_healthy=False,
                    error_message="404 Not Found",
                ),
            ],
            last_updated=datetime(2024, 12, 20, 12, 0),
        )

    def test_initialization(self, sample_feed_data: FeedData):
        """Test that StaticSiteGenerator initializes correctly."""
        generator = StaticSiteGenerator(sample_feed_data)
        assert generator.feed_data == sample_feed_data
        assert generator.output_dir == Path("docs")
        assert isinstance(generator.env, Environment)

    def test_custom_output_dir(self, sample_feed_data: FeedData):
        """Test initialization with custom output directory."""
        custom_dir = Path("custom_output")
        generator = StaticSiteGenerator(sample_feed_data, output_dir=custom_dir)
        assert generator.output_dir == custom_dir

    @patch("src.site.generator.Path.mkdir")
    @patch("src.site.generator.shutil.copy2")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_site(self, mock_file, mock_copy, mock_mkdir, sample_feed_data: FeedData):
        """Test the generate_site method creates all necessary files."""

        generator = StaticSiteGenerator(sample_feed_data)

        # Mock template rendering
        generator.env.get_template = MagicMock(
            return_value=MagicMock(render=MagicMock(return_value="<html>Rendered HTML</html>"))
        )

        # Mock the RSS generator to avoid file system operations
        with patch("src.site.generator.RSSGenerator") as mock_rss_gen:
            mock_rss_instance = MagicMock()
            mock_rss_gen.return_value = mock_rss_instance
            mock_rss_instance.add_entries.return_value = None
            mock_rss_instance.save_feed.return_value = Path("docs/rss/v1/feed.xml")

            generator.generate_site()

            # Check that output directory is created
            mock_mkdir.assert_called_with(parents=True, exist_ok=True)

            # Check that CSS file is copied
            mock_copy.assert_called_once()

            # Check that index.html is written
            mock_file.assert_called()
            write_calls = mock_file().write.call_args_list
            assert any("<html>Rendered HTML</html>" in str(call) for call in write_calls)

            # Check that RSS generator was used
            mock_rss_gen.assert_called_once()
            mock_rss_instance.add_entries.assert_called_once()
            mock_rss_instance.save_feed.assert_called_once()

    def test_deprecations_sorted_by_date(self, sample_feed_data: FeedData):
        """Test that deprecations are sorted by announcement date (newest first)."""
        generator = StaticSiteGenerator(sample_feed_data)

        # Add more deprecations with different dates
        sample_feed_data.deprecations.append(
            DeprecationEntry(
                provider="Google",
                model="palm-2",
                deprecation_date=datetime(2024, 12, 15),
                retirement_date=datetime(2025, 3, 15),
                replacement="gemini",
                notes=None,
                source_url="https://cloud.google.com/deprecations",
            )
        )

        sorted_deprecations = generator._get_sorted_deprecations()

        # Check that deprecations are sorted newest first
        assert sorted_deprecations[0].deprecation_date == datetime(2024, 12, 15)
        assert sorted_deprecations[1].deprecation_date == datetime(2024, 12, 1)
        assert sorted_deprecations[2].deprecation_date == datetime(2024, 11, 15)

    def test_template_context(self, sample_feed_data: FeedData):
        """Test that the correct context is passed to templates."""
        generator = StaticSiteGenerator(sample_feed_data)
        context = generator._get_template_context()

        assert "deprecations" in context
        assert "provider_statuses" in context
        assert "last_updated" in context
        assert "rss_feed_url" in context
        assert (
            context["rss_feed_url"]
            == "https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml"
        )

        # Check deprecations are sorted
        assert len(context["deprecations"]) == 2
        assert (
            context["deprecations"][0].deprecation_date
            >= context["deprecations"][1].deprecation_date
        )

    @patch("src.site.generator.Path.exists")
    def test_css_file_not_found(self, mock_exists, sample_feed_data: FeedData):
        """Test handling when CSS file doesn't exist."""
        mock_exists.return_value = False
        generator = StaticSiteGenerator(sample_feed_data)

        with patch("builtins.open", new_callable=mock_open):
            with patch("src.site.generator.shutil.copy2") as mock_copy:
                generator.generate_site()
                # Should not attempt to copy non-existent CSS
                mock_copy.assert_not_called()

    def test_empty_feed_data(self):
        """Test generator handles empty feed data gracefully."""
        empty_feed = FeedData(deprecations=[], provider_statuses=[], last_updated=datetime.now())
        generator = StaticSiteGenerator(empty_feed)
        context = generator._get_template_context()

        assert context["deprecations"] == []
        assert context["provider_statuses"] == []
        assert "last_updated" in context

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.site.generator.Path.mkdir")
    def test_rss_generation_integration(self, mock_mkdir, mock_file, sample_feed_data: FeedData):
        """Test that RSS feed is generated alongside HTML."""
        from pathlib import Path

        # These mocks are needed to prevent actual file operations
        _ = mock_mkdir  # noqa: F841
        _ = mock_file  # noqa: F841

        generator = StaticSiteGenerator(sample_feed_data)

        # Mock the RSS generator methods
        with patch("src.site.generator.RSSGenerator") as mock_rss_gen:
            mock_rss_instance = MagicMock()
            mock_rss_gen.return_value = mock_rss_instance
            mock_rss_instance.add_entries.return_value = None
            mock_rss_instance.save_feed.return_value = Path("docs/rss/v1/feed.xml")

            # Mock template rendering
            generator.env.get_template = MagicMock(
                return_value=MagicMock(render=MagicMock(return_value="<html>Rendered HTML</html>"))
            )

            generator.generate_site()

            # Verify RSS generator was created and used
            mock_rss_gen.assert_called_once()
            mock_rss_instance.add_entries.assert_called_once_with(
                sample_feed_data.deprecations, version="v1"
            )
            mock_rss_instance.save_feed.assert_called_once_with(
                version="v1", output_path=Path("docs/rss/v1/feed.xml")
            )
