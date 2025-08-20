#!/usr/bin/env python
"""Generate static site using real scraper data."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.models.deprecation import Deprecation, FeedData, ProviderStatus
from src.scrapers.anthropic import AnthropicScraper
from src.site.generator import StaticSiteGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def scrape_real_data() -> tuple[list[Deprecation], ProviderStatus]:
    """Scrape real deprecation data from Anthropic.

    Returns:
        Tuple of (deprecations list, provider status)
    """
    scraper = AnthropicScraper()
    provider_name = "Anthropic"
    check_time = datetime.now(UTC)

    try:
        logger.info(f"Starting scrape for {provider_name}...")
        result = await scraper.scrape()

        # Extract deprecations from result
        deprecations = result.get("deprecations", [])
        logger.info(f"Successfully scraped {len(deprecations)} deprecations from {provider_name}")

        # Create successful provider status
        provider_status = ProviderStatus(
            name=provider_name, last_checked=check_time, is_healthy=True, error_message=None
        )

        return deprecations, provider_status

    except Exception as e:
        logger.error(f"Failed to scrape {provider_name}: {e}")

        # Create failed provider status
        provider_status = ProviderStatus(
            name=provider_name, last_checked=check_time, is_healthy=False, error_message=str(e)
        )

        return [], provider_status


def load_data_from_json(file_path: Path = Path("data.json")) -> FeedData | None:
    """Load feed data from JSON file.

    Args:
        file_path: Path to the JSON data file

    Returns:
        FeedData if file exists and is valid, None otherwise
    """
    if not file_path.exists():
        logger.warning(f"Data file {file_path} does not exist")
        return None

    try:
        with open(file_path) as f:
            data = json.load(f)

        # Convert JSON data to FeedData
        deprecations = []
        for dep_data in data.get("deprecations", []):
            # Convert ISO strings back to datetime
            dep_data["deprecation_date"] = datetime.fromisoformat(dep_data["deprecation_date"])
            dep_data["retirement_date"] = datetime.fromisoformat(dep_data["retirement_date"])
            if "last_updated" in dep_data:
                dep_data["last_updated"] = datetime.fromisoformat(dep_data["last_updated"])
            deprecations.append(Deprecation(**dep_data))

        provider_statuses = []
        for status_data in data.get("provider_statuses", []):
            status_data["last_checked"] = datetime.fromisoformat(status_data["last_checked"])
            provider_statuses.append(ProviderStatus(**status_data))

        last_updated = (
            datetime.fromisoformat(data["last_updated"])
            if "last_updated" in data
            else datetime.now(UTC)
        )

        return FeedData(
            deprecations=deprecations,
            provider_statuses=provider_statuses,
            last_updated=last_updated,
        )
    except Exception as e:
        logger.error(f"Failed to load data from {file_path}: {e}")
        return None


def save_data_to_json(feed_data: FeedData, file_path: Path = Path("data.json")) -> None:
    """Save feed data to JSON file.

    Args:
        feed_data: The feed data to save
        file_path: Path to the JSON data file
    """
    try:
        data = {
            "deprecations": [dep.to_json_dict() for dep in feed_data.deprecations],
            "provider_statuses": [
                {
                    "name": status.name,
                    "last_checked": status.last_checked.isoformat(),
                    "is_healthy": status.is_healthy,
                    "error_message": status.error_message,
                }
                for status in feed_data.provider_statuses
            ],
            "last_updated": feed_data.last_updated.isoformat(),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved data to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save data to {file_path}: {e}")


async def generate_site_from_real_data(
    output_dir: Path | None = None, data_file: Path = Path("data.json")
) -> None:
    """Generate static site using real scraper data.

    Args:
        output_dir: Output directory for generated site (defaults to 'docs')
        data_file: Path to the data.json file
    """
    feed_data = None

    try:
        # Try to get real data from scraper
        deprecations, provider_status = await scrape_real_data()

        if deprecations:
            # Use real data if we got any deprecations
            logger.info("Using real scraped data for site generation")
            feed_data = FeedData(
                deprecations=deprecations,
                provider_statuses=[provider_status],
                last_updated=datetime.now(UTC),
            )
            # Save the scraped data to data.json
            save_data_to_json(feed_data, data_file)
        else:
            # Try to load from existing data.json if no new deprecations found
            logger.warning("No new deprecations found from scraping")
            feed_data = load_data_from_json(data_file)

            if feed_data:
                logger.info(f"Loaded existing data from {data_file}")
                # Update the Anthropic provider status to show the latest scraping attempt
                for status in feed_data.provider_statuses:
                    if status.name == "Anthropic":
                        status.last_checked = provider_status.last_checked
                        status.is_healthy = provider_status.is_healthy
                        status.error_message = (
                            provider_status.error_message or "No new deprecations found"
                        )
                        break
                else:
                    # Add the status if Anthropic wasn't in the data
                    feed_data.provider_statuses.append(provider_status)
            else:
                logger.error("No data available for site generation")
                return

    except Exception as e:
        logger.error(f"Error during data collection: {e}")
        # Try to load from existing data.json
        feed_data = load_data_from_json(data_file)

        if not feed_data:
            logger.error("No data available for site generation and no cached data found")
            return

    # Generate the static site
    try:
        generator = StaticSiteGenerator(feed_data, output_dir=output_dir)
        generator.generate_site()

        output_path = output_dir or Path("docs")
        logger.info("✅ Static site generated successfully!")
        logger.info(f"📁 Output directory: {output_path.absolute()}")
        logger.info(f"🌐 View the site: file://{(output_path / 'index.html').absolute()}")

        # Log summary
        logger.info("Summary:")
        logger.info(f"  - Total deprecations: {len(feed_data.deprecations)}")
        logger.info(f"  - Providers tracked: {len(feed_data.provider_statuses)}")
        healthy_count = sum(1 for s in feed_data.provider_statuses if s.is_healthy)
        logger.info(f"  - Healthy providers: {healthy_count}/{len(feed_data.provider_statuses)}")

    except Exception as e:
        logger.error(f"Failed to generate static site: {e}")
        raise


def main() -> None:
    """Main entry point for the script."""
    try:
        # Run the async function
        asyncio.run(generate_site_from_real_data())
    except KeyboardInterrupt:
        logger.info("Site generation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
