"""Example scraper implementation for demonstration purposes."""

from typing import Any

from src.scrapers.base_scraper import BaseScraper


class ExampleScraper(BaseScraper):
    """
    Example scraper demonstrating how to extend BaseScraper.

    This is a template for provider-specific scrapers.
    """

    async def extract_deprecations(self) -> list[dict[str, Any]]:
        """
        Extract deprecation data from the example provider.

        Returns:
            List of deprecation dictionaries
        """
        # Fetch the main page
        html = await self.fetch(self.url)
        soup = await self.parse_html(html)

        deprecations = []

        # Example: Find all deprecation announcements
        # This would be customized for each provider's HTML structure
        announcements = soup.find_all("div", class_="deprecation-notice")

        for announcement in announcements:
            # Extract model name
            model_elem = announcement.find("h3", class_="model-name")
            model = self.extract_text(model_elem)

            if not model:
                continue

            # Extract dates
            announcement_date_elem = announcement.find("time", class_="announced")
            retirement_date_elem = announcement.find("time", class_="retirement")

            announcement_date = self.extract_date(announcement_date_elem)
            retirement_date = self.extract_date(retirement_date_elem)

            # Extract replacement model
            replacement_elem = announcement.find("span", class_="replacement")
            replacement = self.extract_text(replacement_elem, default="")

            # Extract additional notes
            notes_elem = announcement.find("p", class_="notes")
            notes = self.extract_text(notes_elem, default="")

            deprecations.append(
                {
                    "provider": "Example Provider",
                    "model": model,
                    "announcement_date": announcement_date,
                    "retirement_date": retirement_date,
                    "replacement_model": replacement if replacement else None,
                    "notes": notes if notes else None,
                }
            )

        return deprecations
