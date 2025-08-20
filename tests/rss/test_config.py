"""Tests for RSS configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.rss.config import (
    FeedConfig,
    OutputConfig,
    RSSConfig,
    VersionConfig,
    get_default_config,
)


class DescribeFeedConfig:
    """Tests for FeedConfig."""

    def it_creates_with_default_values(self) -> None:
        """Test creation with default values."""
        config = FeedConfig()

        assert config.title == "AI Model Deprecations"
        assert (
            config.description
            == "Daily-updated RSS feed tracking AI model deprecations across providers"
        )
        assert config.link == "https://leblancfg.github.io/deprecations-rss/"
        assert config.language == "en"
        assert config.copyright is None
        assert config.managing_editor is None
        assert config.webmaster is None
        assert config.ttl == 1440

    def it_creates_with_custom_values(self) -> None:
        """Test creation with custom values."""
        config = FeedConfig(
            title="Custom Title",
            description="Custom Description",
            link="https://custom.example.com",
            language="fr",
            copyright="© 2024 Example Corp",
            managing_editor="editor@example.com",
            webmaster="webmaster@example.com",
            ttl=720,
        )

        assert config.title == "Custom Title"
        assert config.description == "Custom Description"
        assert config.link == "https://custom.example.com"
        assert config.language == "fr"
        assert config.copyright == "© 2024 Example Corp"
        assert config.managing_editor == "editor@example.com"
        assert config.webmaster == "webmaster@example.com"
        assert config.ttl == 720

    def it_validates_positive_ttl(self) -> None:
        """Test that TTL must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            FeedConfig(ttl=0)

        errors = exc_info.value.errors()
        assert any("greater than 0" in str(e) for e in errors)

        with pytest.raises(ValidationError):
            FeedConfig(ttl=-1)

    def it_allows_assignment_validation(self) -> None:
        """Test that assignment validation works."""
        config = FeedConfig()
        config.title = "New Title"
        assert config.title == "New Title"

        with pytest.raises(ValidationError):
            config.ttl = -1


class DescribeVersionConfig:
    """Tests for VersionConfig."""

    def it_creates_with_default_values(self) -> None:
        """Test creation with default values."""
        config = VersionConfig()

        assert config.version == "v1"
        assert config.supported_versions == ["v1"]

    def it_creates_with_custom_values(self) -> None:
        """Test creation with custom values."""
        config = VersionConfig(
            version="v2",
            supported_versions=["v1", "v2", "v3"],
        )

        assert config.version == "v2"
        assert config.supported_versions == ["v1", "v2", "v3"]

    def it_validates_version_pattern(self) -> None:
        """Test version pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            VersionConfig(version="version1")

        errors = exc_info.value.errors()
        assert any("string_pattern_mismatch" in e["type"] for e in errors)

        with pytest.raises(ValidationError):
            VersionConfig(version="1")

        config = VersionConfig(version="v123")
        assert config.version == "v123"

    def it_checks_version_support(self) -> None:
        """Test version support checking."""
        config = VersionConfig(
            version="v1",
            supported_versions=["v1", "v2"],
        )

        assert config.is_version_supported("v1")
        assert config.is_version_supported("v2")
        assert not config.is_version_supported("v3")
        assert not config.is_version_supported("invalid")


class DescribeOutputConfig:
    """Tests for OutputConfig."""

    def it_creates_with_default_values(self) -> None:
        """Test creation with default values."""
        config = OutputConfig()

        assert config.base_path == Path("docs/rss")
        assert config.filename == "feed.xml"

    def it_creates_with_custom_values(self) -> None:
        """Test creation with custom values."""
        config = OutputConfig(
            base_path=Path("/custom/path"),
            filename="custom_feed.xml",
        )

        assert config.base_path == Path("/custom/path")
        assert config.filename == "custom_feed.xml"

    def it_generates_versioned_path(self) -> None:
        """Test versioned path generation."""
        config = OutputConfig(
            base_path=Path("output"),
            filename="feed.xml",
        )

        path = config.get_versioned_path("v1")
        assert path == Path("output/v1/feed.xml")

        path = config.get_versioned_path("v2")
        assert path == Path("output/v2/feed.xml")

    def it_ensures_directories_exist(self, tmp_path: Path) -> None:
        """Test directory creation."""
        config = OutputConfig(
            base_path=tmp_path / "test_output",
            filename="feed.xml",
        )

        version_dir = tmp_path / "test_output" / "v1"
        assert not version_dir.exists()

        config.ensure_directories("v1")
        assert version_dir.exists()
        assert version_dir.is_dir()

        config.ensure_directories("v1")
        assert version_dir.exists()


class DescribeRSSConfig:
    """Tests for RSSConfig."""

    def it_creates_with_default_values(self) -> None:
        """Test creation with default values."""
        config = RSSConfig()

        assert isinstance(config.feed, FeedConfig)
        assert isinstance(config.version, VersionConfig)
        assert isinstance(config.output, OutputConfig)

        assert config.feed.title == "AI Model Deprecations"
        assert config.version.version == "v1"
        assert config.output.filename == "feed.xml"

    def it_creates_with_custom_values(self) -> None:
        """Test creation with custom values."""
        config = RSSConfig(
            feed=FeedConfig(title="Custom Feed"),
            version=VersionConfig(version="v2"),
            output=OutputConfig(filename="custom.xml"),
        )

        assert config.feed.title == "Custom Feed"
        assert config.version.version == "v2"
        assert config.output.filename == "custom.xml"

    def it_creates_from_dict(self) -> None:
        """Test creation from dictionary."""
        config_dict = {
            "feed": {
                "title": "Dict Title",
                "description": "Dict Description",
                "ttl": 360,
            },
            "version": {
                "version": "v3",
                "supported_versions": ["v1", "v2", "v3"],
            },
            "output": {
                "base_path": "/custom/path",
                "filename": "dict_feed.xml",
            },
        }

        config = RSSConfig.from_dict(config_dict)

        assert config.feed.title == "Dict Title"
        assert config.feed.description == "Dict Description"
        assert config.feed.ttl == 360
        assert config.version.version == "v3"
        assert config.version.supported_versions == ["v1", "v2", "v3"]
        assert config.output.base_path == Path("/custom/path")
        assert config.output.filename == "dict_feed.xml"

    def it_creates_from_partial_dict(self) -> None:
        """Test creation from partial dictionary uses defaults."""
        config_dict = {"feed": {"title": "Partial Title"}}

        config = RSSConfig.from_dict(config_dict)

        assert config.feed.title == "Partial Title"
        assert (
            config.feed.description
            == "Daily-updated RSS feed tracking AI model deprecations across providers"
        )
        assert config.version.version == "v1"
        assert config.output.filename == "feed.xml"

    def it_converts_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = RSSConfig(
            feed=FeedConfig(title="Test Title", ttl=480),
            version=VersionConfig(version="v2"),
            output=OutputConfig(
                base_path=Path("/test/path"),
                filename="test.xml",
            ),
        )

        config_dict = config.to_dict()

        assert config_dict["feed"]["title"] == "Test Title"
        assert config_dict["feed"]["ttl"] == 480
        assert config_dict["version"]["version"] == "v2"
        assert config_dict["output"]["base_path"] == "/test/path"
        assert config_dict["output"]["filename"] == "test.xml"


class DescribeGetDefaultConfig:
    """Tests for get_default_config function."""

    def it_returns_default_config(self) -> None:
        """Test that get_default_config returns expected defaults."""
        config = get_default_config()

        assert isinstance(config, RSSConfig)
        assert config.feed.title == "AI Model Deprecations"
        assert config.version.version == "v1"
        assert config.output.base_path == Path("docs/rss")

    def it_returns_new_instance_each_time(self) -> None:
        """Test that get_default_config returns new instances."""
        config1 = get_default_config()
        config2 = get_default_config()

        assert config1 is not config2

        config1.feed.title = "Modified Title"
        assert config2.feed.title == "AI Model Deprecations"
