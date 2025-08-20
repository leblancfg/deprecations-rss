"""Static site generator for creating GitHub Pages site from feed data."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models.deprecation import DeprecationEntry, FeedData
from src.rss.config import get_default_config
from src.rss.generator import RSSGenerator


class StaticSiteGenerator:
    """Generate static HTML site from deprecation feed data."""

    def __init__(self, feed_data: FeedData, output_dir: Path | None = None) -> None:
        """Initialize the generator with feed data.

        Args:
            feed_data: The complete feed data with deprecations and provider statuses
            output_dir: Output directory for generated site (defaults to 'docs')
        """
        self.feed_data = feed_data
        self.output_dir = output_dir or Path("docs")

        # Set up Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"])
        )

    def generate_site(self) -> None:
        """Generate the complete static site."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Copy CSS file
        self._copy_static_assets()

        # Generate HTML
        self._generate_html()

        # Generate RSS feed
        self._generate_rss()

    def _copy_static_assets(self) -> None:
        """Copy static assets (CSS) to output directory."""
        css_source = Path(__file__).parent / "styles.css"
        if css_source.exists():
            css_dest = self.output_dir / "styles.css"
            shutil.copy2(css_source, css_dest)

    def _generate_html(self) -> None:
        """Generate the main index.html file."""
        template = self.env.get_template("index.html")
        context = self._get_template_context()

        html_content = template.render(**context)

        output_file = self.output_dir / "index.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _get_template_context(self) -> dict[str, Any]:
        """Get the context dictionary for template rendering.

        Returns:
            Dictionary with all data needed for template rendering
        """
        return {
            "deprecations": self._get_sorted_deprecations(),
            "provider_statuses": self.feed_data.provider_statuses,
            "last_updated": self.feed_data.last_updated,
            "rss_feed_url": "https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml",
            "current_year": datetime.now().year,
        }

    def _get_sorted_deprecations(self) -> list[DeprecationEntry]:
        """Get deprecations sorted by announcement date (newest first).

        Returns:
            List of deprecations sorted by deprecation_date descending
        """
        return sorted(self.feed_data.deprecations, key=lambda d: d.deprecation_date, reverse=True)

    def _generate_rss(self) -> None:
        """Generate RSS feed with deprecation data."""
        # Create RSS generator with updated config for GitHub Pages
        rss_config = get_default_config()
        rss_generator = RSSGenerator(config=rss_config)

        # Add all deprecations to the feed
        rss_generator.add_entries(self.feed_data.deprecations, version="v1")

        # Save RSS feed to the expected GitHub Pages location
        rss_output_path = self.output_dir / "rss" / "v1" / "feed.xml"
        rss_generator.save_feed(version="v1", output_path=rss_output_path)
