"""RSS feed configuration."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class FeedConfig(BaseModel):
    """Configuration for RSS feed generation."""

    title: str = Field(
        default="AI Model Deprecations",
        description="Feed title",
    )
    description: str = Field(
        default="Daily-updated RSS feed tracking AI model deprecations across providers",
        description="Feed description",
    )
    link: str = Field(
        default="https://leblancfg.github.io/deprecations-rss/",
        description="Feed website link",
    )
    language: str = Field(
        default="en",
        description="Feed language code",
    )
    copyright: str | None = Field(
        default=None,
        description="Copyright information",
    )
    managing_editor: str | None = Field(
        default=None,
        description="Managing editor email",
    )
    webmaster: str | None = Field(
        default=None,
        description="Webmaster email",
    )
    ttl: int = Field(
        default=1440,
        description="Time to live in minutes (default 24 hours)",
        gt=0,
    )

    model_config = {"validate_assignment": True}


class VersionConfig(BaseModel):
    """Configuration for RSS feed versioning."""

    version: str = Field(
        default="v1",
        description="Feed version identifier",
        pattern=r"^v\d+$",
    )
    supported_versions: list[str] = Field(
        default_factory=lambda: ["v1"],
        description="List of supported versions",
    )

    def is_version_supported(self, version: str) -> bool:
        """Check if a version is supported."""
        return version in self.supported_versions

    model_config = {"validate_assignment": True}


class OutputConfig(BaseModel):
    """Configuration for RSS feed output paths."""

    base_path: Path = Field(
        default=Path("docs/rss"),
        description="Base output directory for RSS feeds",
    )
    filename: str = Field(
        default="feed.xml",
        description="RSS feed filename",
    )

    def get_versioned_path(self, version: str) -> Path:
        """Get the full path for a versioned feed."""
        return self.base_path / version / self.filename

    def ensure_directories(self, version: str) -> None:
        """Ensure output directories exist for a given version."""
        versioned_dir = self.base_path / version
        versioned_dir.mkdir(parents=True, exist_ok=True)

    model_config = {"validate_assignment": True}


class RSSConfig(BaseModel):
    """Complete RSS configuration."""

    feed: FeedConfig = Field(
        default_factory=FeedConfig,
        description="Feed metadata configuration",
    )
    version: VersionConfig = Field(
        default_factory=VersionConfig,
        description="Version configuration",
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output path configuration",
    )

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "RSSConfig":
        """Create RSSConfig from dictionary."""
        return cls(
            feed=FeedConfig(**config_dict.get("feed", {})),
            version=VersionConfig(**config_dict.get("version", {})),
            output=OutputConfig(**config_dict.get("output", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feed": self.feed.model_dump(),
            "version": self.version.model_dump(),
            "output": {
                "base_path": str(self.output.base_path),
                "filename": self.output.filename,
            },
        }

    model_config = {"validate_assignment": True}


def get_default_config() -> RSSConfig:
    """Get default RSS configuration."""
    return RSSConfig()
