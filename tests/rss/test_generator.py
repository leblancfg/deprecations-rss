"""Tests for RSS generator."""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from src.models.deprecation import DeprecationEntry
from src.rss.config import FeedConfig, OutputConfig, RSSConfig, VersionConfig
from src.rss.generator import RSSGenerator


class DescribeRSSGenerator:
    """Tests for RSSGenerator initialization."""

    def it_creates_with_default_config(self) -> None:
        """Test creation with default configuration."""
        generator = RSSGenerator()

        assert generator.config is not None
        assert generator.config.feed.title == "AI Model Deprecations"
        assert generator.config.version.version == "v1"

    def it_creates_with_custom_config(self) -> None:
        """Test creation with custom configuration."""
        config = RSSConfig(
            feed=FeedConfig(title="Custom Feed"),
            version=VersionConfig(version="v2"),
        )
        generator = RSSGenerator(config)

        assert generator.config.feed.title == "Custom Feed"
        assert generator.config.version.version == "v2"


class DescribeFeedManagement:
    """Tests for feed creation and management."""

    def it_creates_feed_on_demand(self) -> None:
        """Test that feeds are created on demand."""
        generator = RSSGenerator()

        assert len(generator._feeds) == 0

        feed = generator.get_feed("v1")
        assert feed is not None
        assert len(generator._feeds) == 1
        assert "v1" in generator._feeds

    def it_reuses_existing_feed(self) -> None:
        """Test that existing feeds are reused."""
        generator = RSSGenerator()

        feed1 = generator.get_feed("v1")
        feed2 = generator.get_feed("v1")

        assert feed1 is feed2
        assert len(generator._feeds) == 1

    def it_creates_multiple_version_feeds(self) -> None:
        """Test creation of multiple version feeds."""
        config = RSSConfig(
            version=VersionConfig(
                version="v1",
                supported_versions=["v1", "v2"],
            )
        )
        generator = RSSGenerator(config)

        feed1 = generator.get_feed("v1")
        feed2 = generator.get_feed("v2")

        assert feed1 is not feed2
        assert len(generator._feeds) == 2
        assert "v1" in generator._feeds
        assert "v2" in generator._feeds

    def it_raises_error_for_unsupported_version(self) -> None:
        """Test error for unsupported version."""
        generator = RSSGenerator()

        with pytest.raises(ValueError) as exc_info:
            generator.get_feed("v99")

        assert "Version v99 not supported" in str(exc_info.value)
        assert "Supported versions: v1" in str(exc_info.value)

    def it_configures_feed_metadata(self) -> None:
        """Test that feed metadata is properly configured."""
        config = RSSConfig(
            feed=FeedConfig(
                title="Test Feed",
                description="Test Description",
                link="https://test.example.com",
                language="fr",
                copyright="© Test",
                managing_editor="editor@test.com",
                webmaster="webmaster@test.com",
                ttl=360,
            )
        )
        generator = RSSGenerator(config)

        feed = generator.get_feed("v1")

        rss_str = feed.rss_str(pretty=True).decode("utf-8")

        assert "Test Feed" in rss_str
        assert "Test Description" in rss_str
        assert "https://test.example.com" in rss_str
        assert "<language>fr</language>" in rss_str
        assert "© Test" in rss_str
        assert "editor@test.com" in rss_str
        assert "webmaster@test.com" in rss_str
        assert "<ttl>360</ttl>" in rss_str


class DescribeAddingEntries:
    """Tests for adding deprecation entries."""

    def it_adds_single_entry(self) -> None:
        """Test adding a single entry."""
        generator = RSSGenerator()
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )

        generator.add_entry(entry)

        assert generator.get_entry_count("v1") == 1

        rss_str = generator.generate_rss("v1")
        assert "OpenAI - gpt-3.5-turbo Deprecation" in rss_str
        assert "Provider: OpenAI" in rss_str
        assert "Model: gpt-3.5-turbo" in rss_str

    def it_adds_entry_with_all_fields(self) -> None:
        """Test adding entry with all fields."""
        generator = RSSGenerator()
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement="gpt-4-turbo",
            notes="Please migrate soon",
            source_url="https://openai.com/deprecation",
        )

        generator.add_entry(entry)

        rss_str = generator.generate_rss("v1")
        assert "Replacement: gpt-4-turbo" in rss_str
        assert "Notes: Please migrate soon" in rss_str
        assert "https://openai.com/deprecation" in rss_str

    def it_adds_multiple_entries(self) -> None:
        """Test adding multiple entries."""
        generator = RSSGenerator()
        entries = [
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-3.5-turbo",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
                source_url="https://example.com",
            ),
            DeprecationEntry(
                provider="Anthropic",
                model="claude-1",
                deprecation_date=datetime(2024, 2, 1),
                retirement_date=datetime(2024, 7, 1),
                source_url="https://example.com",
            ),
            DeprecationEntry(
                provider="Google",
                model="palm-2",
                deprecation_date=datetime(2024, 3, 1),
                retirement_date=datetime(2024, 8, 1),
                source_url="https://example.com",
            ),
        ]

        generator.add_entries(entries)

        assert generator.get_entry_count("v1") == 3

        rss_str = generator.generate_rss("v1")
        assert "OpenAI - gpt-3.5-turbo" in rss_str
        assert "Anthropic - claude-1" in rss_str
        assert "Google - palm-2" in rss_str

    def it_sorts_entries_by_date_newest_first(self) -> None:
        """Test that entries are sorted by deprecation date (newest first)."""
        generator = RSSGenerator()
        entries = [
            DeprecationEntry(
                provider="OpenAI",
                model="old-model",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
                source_url="https://example.com",
            ),
            DeprecationEntry(
                provider="Anthropic",
                model="newest-model",
                deprecation_date=datetime(2024, 3, 1),
                retirement_date=datetime(2024, 8, 1),
                source_url="https://example.com",
            ),
            DeprecationEntry(
                provider="Google",
                model="middle-model",
                deprecation_date=datetime(2024, 2, 1),
                retirement_date=datetime(2024, 7, 1),
                source_url="https://example.com",
            ),
        ]

        generator.add_entries(entries, sort_by_date=True)

        rss_str = generator.generate_rss("v1")

        # Check items appear in the XML in newest-first order
        # Note: feedgen outputs entries in LIFO order, so we need to check
        # that when sorted newest-first and added, they appear correctly
        import re

        items = re.findall(r"Model: (.*?)\n", rss_str)
        assert items == ["newest-model", "middle-model", "old-model"]

    def it_adds_without_sorting_when_specified(self) -> None:
        """Test adding entries without sorting."""
        generator = RSSGenerator()
        entries = [
            DeprecationEntry(
                provider="OpenAI",
                model="first",
                deprecation_date=datetime(2024, 3, 1),
                retirement_date=datetime(2024, 8, 1),
                source_url="https://example.com",
            ),
            DeprecationEntry(
                provider="Anthropic",
                model="second",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
                source_url="https://example.com",
            ),
        ]

        generator.add_entries(entries, sort_by_date=False)

        rss_str = generator.generate_rss("v1")

        # feedgen outputs in LIFO order, so second added appears first
        import re

        items = re.findall(r"Model: (.*?)\n", rss_str)
        assert items == ["second", "first"]


class DescribeRSSGeneration:
    """Tests for RSS generation."""

    def it_generates_valid_rss_xml(self) -> None:
        """Test that generated RSS is valid XML."""
        generator = RSSGenerator()
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )

        generator.add_entry(entry)
        rss_str = generator.generate_rss("v1")

        root = ET.fromstring(rss_str)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"

        channel = root.find("channel")
        assert channel is not None

        title = channel.find("title")
        assert title is not None
        assert title.text == "AI Model Deprecations"

        items = channel.findall("item")
        assert len(items) == 1

    def it_includes_all_required_rss_fields(self) -> None:
        """Test that all required RSS fields are included."""
        generator = RSSGenerator()
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://example.com",
        )

        generator.add_entry(entry)
        rss_str = generator.generate_rss("v1")

        root = ET.fromstring(rss_str)
        channel = root.find("channel")

        assert channel.find("title") is not None
        assert channel.find("description") is not None
        assert channel.find("link") is not None

        item = channel.find("item")
        assert item is not None

        assert item.find("title") is not None
        assert item.find("description") is not None
        assert item.find("guid") is not None
        assert item.find("pubDate") is not None
        assert item.find("link") is not None

    def it_generates_empty_feed(self) -> None:
        """Test generating empty feed."""
        generator = RSSGenerator()
        rss_str = generator.generate_rss("v1")

        root = ET.fromstring(rss_str)
        channel = root.find("channel")
        items = channel.findall("item")

        assert len(items) == 0


class DescribeSavingFeeds:
    """Tests for saving feeds to disk."""

    def it_saves_feed_to_default_path(self, tmp_path: Path) -> None:
        """Test saving feed to default configured path."""
        config = RSSConfig(
            output=OutputConfig(
                base_path=tmp_path / "output",
                filename="test_feed.xml",
            )
        )
        generator = RSSGenerator(config)

        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )
        generator.add_entry(entry)

        saved_path = generator.save_feed("v1")

        assert saved_path == tmp_path / "output" / "v1" / "test_feed.xml"
        assert saved_path.exists()

        content = saved_path.read_text()
        assert "OpenAI - gpt-3.5-turbo" in content

    def it_saves_feed_to_custom_path(self, tmp_path: Path) -> None:
        """Test saving feed to custom path."""
        generator = RSSGenerator()

        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )
        generator.add_entry(entry)

        custom_path = tmp_path / "custom" / "feed.xml"
        saved_path = generator.save_feed("v1", custom_path)

        assert saved_path == custom_path
        assert saved_path.exists()

        content = saved_path.read_text()
        assert "OpenAI - gpt-3.5-turbo" in content

    def it_creates_directories_if_not_exist(self, tmp_path: Path) -> None:
        """Test that directories are created if they don't exist."""
        config = RSSConfig(
            output=OutputConfig(
                base_path=tmp_path / "new" / "nested" / "path",
                filename="feed.xml",
            )
        )
        generator = RSSGenerator(config)

        assert not (tmp_path / "new").exists()

        saved_path = generator.save_feed("v1")

        assert saved_path.exists()
        assert saved_path.parent.exists()


class DescribeFeedManipulation:
    """Tests for feed manipulation operations."""

    def it_clears_single_feed(self) -> None:
        """Test clearing a single feed."""
        generator = RSSGenerator()

        entries = [
            DeprecationEntry(
                provider="OpenAI",
                model=f"model-{i}",
                deprecation_date=datetime(2024, 1, i),
                retirement_date=datetime(2024, 6, i),
                source_url="https://example.com",
            )
            for i in range(1, 4)
        ]
        generator.add_entries(entries)

        assert generator.get_entry_count("v1") == 3

        generator.clear_feed("v1")

        assert generator.get_entry_count("v1") == 0

    def it_clears_all_feeds(self) -> None:
        """Test clearing all feeds."""
        config = RSSConfig(
            version=VersionConfig(
                supported_versions=["v1", "v2"],
            )
        )
        generator = RSSGenerator(config)

        entry = DeprecationEntry(
            provider="OpenAI",
            model="test-model",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://example.com",
        )

        generator.add_entry(entry, "v1")
        generator.add_entry(entry, "v2")

        assert len(generator._feeds) == 2

        generator.clear_all_feeds()

        assert len(generator._feeds) == 0

    def it_counts_entries_correctly(self) -> None:
        """Test entry counting."""
        generator = RSSGenerator()

        assert generator.get_entry_count("v1") == 0

        entry = DeprecationEntry(
            provider="OpenAI",
            model="test-model",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://example.com",
        )

        generator.add_entry(entry)
        assert generator.get_entry_count("v1") == 1

        generator.add_entry(entry)
        assert generator.get_entry_count("v1") == 2

        generator.clear_feed("v1")
        assert generator.get_entry_count("v1") == 0


class DescribeFeedValidation:
    """Tests for feed validation."""

    def it_validates_complete_feed(self) -> None:
        """Test validation of complete feed."""
        generator = RSSGenerator()

        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )
        generator.add_entry(entry)

        assert generator.validate_feed("v1") is True

    def it_validates_empty_feed(self) -> None:
        """Test validation of empty feed (should be valid)."""
        generator = RSSGenerator()

        assert generator.validate_feed("v1") is True

    def it_validates_feed_has_required_metadata(self) -> None:
        """Test that feed validation checks required metadata."""
        generator = RSSGenerator()

        assert generator.validate_feed("v1") is True
