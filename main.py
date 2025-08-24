"""Main script to scrape deprecations and update data.json."""

import json
from pathlib import Path
from providers import SCRAPERS


def scrape_all():
    """Scrape all providers and return results."""
    all_deprecations = []

    for scraper_class in SCRAPERS:
        try:
            scraper = scraper_class()
            deprecations = scraper.scrape()  # Now returns a list
            all_deprecations.extend(deprecations)

            # Get provider name from first item or fallback
            provider = (
                deprecations[0]["provider"]
                if deprecations
                else scraper_class.__name__.replace("Scraper", "")
            )
            print(f"✓ Scraped {provider}: {len(deprecations)} deprecations")
        except Exception as e:
            print(f"✗ Failed to scrape {scraper_class.__name__}: {e}")

    return all_deprecations


def save_data(data):
    """Save scraped data to data.json."""
    output_file = Path("data.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved {len(data)} deprecation notices to data.json")


if __name__ == "__main__":
    data = scrape_all()
    save_data(data)
