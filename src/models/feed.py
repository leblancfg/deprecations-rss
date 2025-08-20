"""Deprecation feed model for RSS generation."""

from datetime import UTC, datetime

from feedgen.feed import FeedGenerator  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from src.models.deprecation import DeprecationEntry


class DeprecationFeed(BaseModel):
    """Model for managing and generating RSS feeds of deprecation entries."""

    entries: list[DeprecationEntry] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = "v1"

    def add_entry(self, entry: DeprecationEntry) -> None:
        """Add a deprecation entry to the feed."""
        self.entries.append(entry)

    def get_active_entries(self) -> list[DeprecationEntry]:
        """Get only active deprecation entries.

        Returns entries where retirement date hasn't passed yet.
        """
        return [entry for entry in self.entries if entry.is_active()]

    def to_rss(self) -> str:
        """Generate RSS XML feed from deprecation entries."""
        fg = FeedGenerator()

        # Set feed metadata
        fg.title("AI Model Deprecations")
        fg.description("Track deprecations and retirements of AI models across providers")
        fg.link(href="https://deprecations.example.com", rel="alternate")
        fg.language("en")
        fg.generator("deprecations-rss", version=self.version)
        fg.lastBuildDate(self.generated_at)

        # Sort entries by created date (newest first)
        sorted_entries = sorted(
            self.entries,
            key=lambda e: e.created_at,
            reverse=True
        )

        # Add entries to feed
        for entry in sorted_entries:
            rss_item = entry.to_rss_item()

            fe = fg.add_entry()
            fe.title(rss_item["title"])
            fe.description(rss_item["description"])
            fe.guid(rss_item["guid"], permalink=False)
            fe.pubDate(rss_item["pubDate"])
            fe.link(href=rss_item["link"])

        # Generate RSS XML string
        rss_bytes: bytes = fg.rss_str(pretty=True)
        return rss_bytes.decode("utf-8")

