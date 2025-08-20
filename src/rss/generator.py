"""RSS feed generator for AI model deprecations."""

from datetime import UTC, datetime
from pathlib import Path

from feedgen.feed import FeedGenerator  # type: ignore[import-untyped]

from src.models.deprecation import DeprecationEntry
from src.rss.config import RSSConfig, get_default_config


class RSSGenerator:
    """Generator for creating RSS feeds from deprecation entries."""

    def __init__(self, config: RSSConfig | None = None) -> None:
        """Initialize RSS generator with configuration.

        Args:
            config: RSS configuration. Uses default if not provided.
        """
        self.config = config or get_default_config()
        self._feeds: dict[str, FeedGenerator] = {}

    def _create_feed(self, version: str) -> FeedGenerator:
        """Create a new feed generator for a specific version.

        Args:
            version: Version identifier (e.g., "v1")

        Returns:
            Configured FeedGenerator instance
        """
        fg = FeedGenerator()

        fg.title(self.config.feed.title)
        fg.description(self.config.feed.description)
        fg.link(href=self.config.feed.link, rel="alternate")
        fg.language(self.config.feed.language)

        if self.config.feed.copyright:
            fg.copyright(self.config.feed.copyright)

        if self.config.feed.managing_editor:
            fg.managingEditor(self.config.feed.managing_editor)

        if self.config.feed.webmaster:
            fg.webMaster(self.config.feed.webmaster)

        fg.ttl(self.config.feed.ttl)

        fg.generator(generator="deprecations-rss", version=version)
        fg.lastBuildDate(datetime.now(UTC))

        return fg

    def get_feed(self, version: str = "v1") -> FeedGenerator:
        """Get or create a feed generator for a specific version.

        Args:
            version: Version identifier

        Returns:
            FeedGenerator for the specified version

        Raises:
            ValueError: If version is not supported
        """
        if not self.config.version.is_version_supported(version):
            raise ValueError(
                f"Version {version} not supported. "
                f"Supported versions: {', '.join(self.config.version.supported_versions)}"
            )

        if version not in self._feeds:
            self._feeds[version] = self._create_feed(version)

        return self._feeds[version]

    def add_entry(
        self,
        entry: DeprecationEntry,
        version: str = "v1",
    ) -> None:
        """Add a deprecation entry to the feed.

        Args:
            entry: Deprecation entry to add
            version: Version of feed to add entry to
        """
        feed = self.get_feed(version)
        rss_item = entry.to_rss_item()

        fe = feed.add_entry()
        fe.title(rss_item["title"])
        fe.description(rss_item["description"])

        if rss_item["link"]:
            fe.link(href=rss_item["link"])

        fe.guid(rss_item["guid"], permalink=False)

        pubdate = rss_item["pubDate"]
        if isinstance(pubdate, datetime) and pubdate.tzinfo is None:
            pubdate = pubdate.replace(tzinfo=UTC)
        fe.pubDate(pubdate)

    def add_entries(
        self,
        entries: list[DeprecationEntry],
        version: str = "v1",
        sort_by_date: bool = True,
    ) -> None:
        """Add multiple deprecation entries to the feed.

        Args:
            entries: List of deprecation entries
            version: Version of feed to add entries to
            sort_by_date: Whether to sort entries by deprecation date (newest first)
        """
        if sort_by_date:
            # Sort oldest first because feedgen outputs in LIFO order
            # This results in newest-first in the final output
            entries = sorted(
                entries,
                key=lambda e: e.deprecation_date,
                reverse=False,
            )

        for entry in entries:
            self.add_entry(entry, version)

    def generate_rss(self, version: str = "v1") -> str:
        """Generate RSS 2.0 XML string.

        Args:
            version: Version of feed to generate

        Returns:
            RSS 2.0 XML string
        """
        feed = self.get_feed(version)
        rss_bytes: bytes = feed.rss_str(pretty=True)
        return rss_bytes.decode("utf-8")

    def save_feed(
        self,
        version: str = "v1",
        output_path: Path | None = None,
    ) -> Path:
        """Save RSS feed to file.

        Args:
            version: Version of feed to save
            output_path: Custom output path. Uses config path if not provided.

        Returns:
            Path where feed was saved
        """
        feed = self.get_feed(version)

        if output_path is None:
            self.config.output.ensure_directories(version)
            output_path = self.config.output.get_versioned_path(version)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        feed.rss_file(str(output_path))
        return output_path

    def clear_feed(self, version: str = "v1") -> None:
        """Clear all entries from a feed.

        Args:
            version: Version of feed to clear
        """
        if version in self._feeds:
            self._feeds[version] = self._create_feed(version)

    def clear_all_feeds(self) -> None:
        """Clear all feeds."""
        self._feeds.clear()

    def get_entry_count(self, version: str = "v1") -> int:
        """Get the number of entries in a feed.

        Args:
            version: Version of feed to check

        Returns:
            Number of entries in the feed
        """
        if version not in self._feeds:
            return 0

        feed = self._feeds[version]
        return len(feed.entry())

    def validate_feed(self, version: str = "v1") -> bool:
        """Validate that feed meets RSS 2.0 requirements.

        Args:
            version: Version of feed to validate

        Returns:
            True if feed is valid

        Raises:
            ValueError: If feed is invalid with details
        """
        feed = self.get_feed(version)

        if not feed.title():
            raise ValueError("Feed must have a title")

        if not feed.description():
            raise ValueError("Feed must have a description")

        if not feed.link():
            raise ValueError("Feed must have a link")

        for entry in feed.entry():
            if not entry.title() and not entry.description():
                raise ValueError("Each entry must have either title or description")

            if not entry.guid():
                raise ValueError("Each entry must have a GUID")

        return True
