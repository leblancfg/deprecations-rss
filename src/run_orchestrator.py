"""Main script to run the scraper orchestrator with configured scrapers."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from src.models.scraper import ScraperConfig
from src.scrapers.orchestrator import OrchestratorConfig, ScraperOrchestrator
from src.scrapers.registry import registry
from src.storage.json_storage import JsonStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("orchestrator.log")
    ]
)
logger = logging.getLogger(__name__)


async def run_orchestrator(
    data_dir: Path | None = None,
    scraper_names: list[str] | None = None,
    orchestrator_config: OrchestratorConfig | None = None,
    scraper_config: ScraperConfig | None = None
) -> dict[str, Any]:
    """
    Run the scraper orchestrator.

    Args:
        data_dir: Directory for data storage (defaults to ./data)
        scraper_names: List of scraper names to run (defaults to all)
        orchestrator_config: Orchestrator configuration
        scraper_config: Shared scraper configuration

    Returns:
        Dictionary with orchestration results
    """
    # Set defaults
    if data_dir is None:
        data_dir = Path("./data")

    if orchestrator_config is None:
        orchestrator_config = OrchestratorConfig(
            max_concurrent=3,
            timeout_seconds=120,
            retry_failed=True,
            fail_fast=False
        )

    if scraper_config is None:
        scraper_config = ScraperConfig(
            timeout=60,
            max_retries=3,
            cache_ttl_hours=23,
            rate_limit_delay=2.0
        )

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize storage
    storage = JsonStorage(data_dir)
    logger.info(f"Using data directory: {data_dir}")

    # Initialize orchestrator
    orchestrator = ScraperOrchestrator(storage, orchestrator_config)

    # Create scrapers
    if scraper_names:
        scrapers = []
        for name in scraper_names:
            scraper = registry.create(name, scraper_config)
            if scraper:
                scrapers.append(scraper)
                logger.info(f"Created scraper: {name}")
            else:
                logger.warning(f"Failed to create scraper: {name}")
    else:
        # Use all available scrapers
        scrapers = registry.create_all(scraper_config)
        logger.info(f"Created {len(scrapers)} scrapers from registry")

    if not scrapers:
        logger.error("No scrapers available to run")
        return {
            "success": False,
            "error": "No scrapers available"
        }

    # Run orchestration
    logger.info(f"Starting orchestration with {len(scrapers)} scrapers")
    result = await orchestrator.run(scrapers)

    # Log results
    logger.info(
        f"Orchestration completed: {result.successful_scrapers}/{result.total_scrapers} successful, "
        f"{result.new_deprecations} new, {result.updated_deprecations} updated"
    )

    if result.errors:
        for error in result.errors:
            logger.error(f"Scraper error: {error}")

    return {
        "success": True,
        "result": {
            "total_scrapers": result.total_scrapers,
            "successful_scrapers": result.successful_scrapers,
            "failed_scrapers": result.failed_scrapers,
            "total_deprecations": result.total_deprecations,
            "new_deprecations": result.new_deprecations,
            "updated_deprecations": result.updated_deprecations,
            "execution_time_seconds": result.execution_time_seconds,
            "success_rate": result.success_rate,
            "errors": result.errors
        }
    }


async def main() -> None:
    """Main entry point for running the orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the deprecation scraper orchestrator")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="Directory for data storage"
    )
    parser.add_argument(
        "--scrapers",
        nargs="+",
        help="Specific scrapers to run (defaults to all)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent scrapers"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout for each scraper in seconds"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Fail immediately on first scraper error"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configure orchestrator
    orchestrator_config = OrchestratorConfig(
        max_concurrent=args.max_concurrent,
        timeout_seconds=args.timeout,
        retry_failed=True,
        fail_fast=args.fail_fast
    )

    # Run orchestrator
    try:
        result = await run_orchestrator(
            data_dir=args.data_dir,
            scraper_names=args.scrapers,
            orchestrator_config=orchestrator_config
        )

        # Print summary
        if result["success"]:
            res = result["result"]
            print("\n✅ Orchestration completed successfully!")
            print(f"   Scrapers: {res['successful_scrapers']}/{res['total_scrapers']} successful")
            print(f"   Deprecations: {res['new_deprecations']} new, {res['updated_deprecations']} updated")
            print(f"   Execution time: {res['execution_time_seconds']:.2f}s")

            if res["errors"]:
                print(f"\n⚠️  {len(res['errors'])} errors occurred:")
                for error in res["errors"]:
                    print(f"   - {error}")
        else:
            print(f"\n❌ Orchestration failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Orchestration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error during orchestration")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
