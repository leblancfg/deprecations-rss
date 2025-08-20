#!/usr/bin/env python
"""Generate static site using real scraper data with fallback to mock data."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.models.deprecation import Deprecation, FeedData, ProviderStatus
from src.scrapers.anthropic import AnthropicScraper
from src.scrapers.mock_data import generate_mock_feed_data
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


def use_mock_data_fallback() -> FeedData:
    """Get mock data as fallback when real scraping fails.

    Returns:
        FeedData with mock deprecations
    """
    logger.warning("Using mock data as fallback")
    return generate_mock_feed_data()


async def generate_site_from_real_data(output_dir: Path | None = None) -> None:
    """Generate static site using real scraper data with fallback to mock.

    Args:
        output_dir: Output directory for generated site (defaults to 'docs')
    """
    try:
        # Try to get real data
        deprecations, provider_status = await scrape_real_data()

        if deprecations:
            # Use real data if we got any deprecations
            logger.info("Using real scraped data for site generation")
            feed_data = FeedData(
                deprecations=deprecations,
                provider_statuses=[provider_status],
                last_updated=datetime.now(UTC),
            )
        else:
            # Fall back to mock data if no real data available
            logger.warning("No real deprecations found, falling back to mock data")
            feed_data = use_mock_data_fallback()

            # Update the Anthropic provider status to show the scraping attempt
            for status in feed_data.provider_statuses:
                if status.name == "Anthropic":
                    status.last_checked = provider_status.last_checked
                    status.is_healthy = provider_status.is_healthy
                    status.error_message = provider_status.error_message or "No deprecations found"
                    break
            else:
                # Add the status if Anthropic wasn't in the mock data
                feed_data.provider_statuses.append(provider_status)

    except Exception as e:
        logger.error(f"Error during data collection: {e}")
        logger.info("Falling back to mock data due to error")
        feed_data = use_mock_data_fallback()

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
