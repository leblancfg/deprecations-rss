"""Example scraper implementation demonstrating cache usage."""

from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, DeprecationEntry


class ExampleScraper(BaseScraper):
    """Example scraper for a hypothetical AI provider."""

    PROVIDER_NAME = "Example AI"
    BASE_URL = "https://example-ai.com"
    DEPRECATIONS_URL = f"{BASE_URL}/deprecations"

    def parse_deprecations(self, soup: BeautifulSoup, base_url: str) -> list[DeprecationEntry]:
        """Parse deprecation entries from the HTML page.

        This is an example implementation that would need to be
        adapted for each specific provider's HTML structure.
        """
        entries = []

        # Example: Find all deprecation items
        # Each provider will have different HTML structure
        deprecation_items = soup.find_all("div", class_="deprecation-item")

        for item in deprecation_items:
            # Extract title
            title_elem = item.find("h3", class_="deprecation-title")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)

            # Extract description
            desc_elem = item.find("div", class_="deprecation-description")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Extract deprecation date
            date_elem = item.find("span", class_="deprecation-date")
            if date_elem:
                date_str = date_elem.get_text(strip=True)
                try:
                    # Parse date - format will vary by provider
                    deprecation_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    # Default to far future if date parsing fails
                    deprecation_date = datetime(2099, 12, 31, tzinfo=UTC)
            else:
                deprecation_date = datetime(2099, 12, 31, tzinfo=UTC)

            # Extract link
            link_elem = item.find("a", class_="deprecation-link")
            if link_elem and link_elem.get("href"):
                link = urljoin(base_url, link_elem["href"])
            else:
                link = base_url

            entries.append(
                DeprecationEntry(
                    title=title,
                    description=description,
                    deprecation_date=deprecation_date,
                    link=link,
                    provider=self.PROVIDER_NAME,
                )
            )

        return entries


async def main() -> None:
    """Example usage of the scraper with caching."""
    from pathlib import Path

    # Create scraper with custom cache directory
    cache_dir = Path(".cache/scrapers")
    scraper = ExampleScraper(cache_dir=cache_dir)

    try:
        # Scrape deprecations - will use cache if available
        deprecations = await scraper.scrape(ExampleScraper.DEPRECATIONS_URL)

        if deprecations:
            print(f"Found {len(deprecations)} deprecations:")
            for dep in deprecations:
                print(f"  - {dep.title}: {dep.deprecation_date.date()}")
        else:
            print("Failed to fetch deprecations or none found")

    finally:
        # Clean up resources
        await scraper.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
