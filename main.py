"""Main script to scrape deprecations and update data.json."""

import json
from pathlib import Path
from providers import SCRAPERS


def scrape_all():
    """Scrape all providers and return results."""
    results = []
    
    for scraper_class in SCRAPERS:
        try:
            scraper = scraper_class()
            result = scraper.scrape()
            results.append(result)
            print(f"✓ Scraped {result['provider']}")
        except Exception as e:
            print(f"✗ Failed to scrape {scraper_class.__name__}: {e}")
    
    return results


def save_data(data):
    """Save scraped data to data.json."""
    output_file = Path("data.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved {len(data)} provider deprecations to data.json")


if __name__ == "__main__":
    data = scrape_all()
    save_data(data)
