"""Orchestrate all scrapers with error isolation and caching."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.errors.analyzer import ErrorAnalyzer
from src.errors.logger import get_logger
from src.notifications.notifier import NotificationManager
from src.scrapers.anthropic import AnthropicScraper
from src.scrapers.cache import CacheManager
from src.scrapers.enhanced_base import ErrorContext, ScraperResult
from src.scrapers.openai import OpenAIScraper

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)


@dataclass
class OrchestratorResult:
    """Result from running all scrapers."""

    total_providers: int
    successful_providers: int
    failed_providers: int
    all_deprecations: list[dict[str, Any]]
    errors: list[ErrorContext]
    used_cache_for: list[str]
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    provider_timings: dict[str, float] = field(default_factory=dict)
    url_changes: dict[str, dict[str, str]] | None = None

    def generate_report(self) -> str:
        """Generate a human-readable report."""
        report = []
        report.append("=" * 50)
        report.append("Scraper Orchestration Report")
        report.append("=" * 50)
        report.append(f"Run Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Duration: {self.duration_seconds:.2f} seconds")
        report.append("")
        report.append(f"Total Providers: {self.total_providers}")
        report.append(f"Successful: {self.successful_providers}")
        report.append(f"Failed: {self.failed_providers}")
        report.append(f"Used Cache: {len(self.used_cache_for)}")
        report.append("")
        report.append(f"Total Deprecations Found: {len(self.all_deprecations)}")

        if self.errors:
            report.append("")
            report.append("Errors:")
            for error in self.errors:
                report.append(f"  - {error.provider}: {error.error_type}")
                if error.status_code:
                    report.append(f"    Status: {error.status_code}")

        if self.url_changes:
            report.append("")
            report.append("URL Changes Detected:")
            for provider, change in self.url_changes.items():
                report.append(f"  - {provider}:")
                report.append(f"    Old: {change['old_url']}")
                report.append(f"    New: {change['new_url']}")

        if self.provider_timings:
            report.append("")
            report.append("Provider Timings:")
            for provider, timing in sorted(self.provider_timings.items()):
                report.append(f"  - {provider}: {timing:.2f}s")

        return "\n".join(report)

    def to_json(self) -> str:
        """Export results to JSON."""
        data = {
            "timestamp": self.start_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_providers": self.total_providers,
            "successful_providers": self.successful_providers,
            "failed_providers": self.failed_providers,
            "deprecations": self.all_deprecations,
            "errors": [
                {
                    "provider": e.provider,
                    "error_type": e.error_type,
                    "status_code": e.status_code,
                    "url": e.url,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.errors
            ],
            "used_cache_for": self.used_cache_for,
            "url_changes": self.url_changes,
            "provider_timings": self.provider_timings,
        }
        return json.dumps(data, indent=2)


class ScraperOrchestrator:
    """Orchestrates running all scrapers with error isolation."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl_hours: float = 23.0
    ) -> None:
        """Initialize orchestrator.
        
        Args:
            cache_dir: Directory for cache storage
            cache_ttl_hours: Cache time-to-live in hours
        """
        self.cache_manager = CacheManager(cache_dir=cache_dir, default_ttl_hours=cache_ttl_hours)

        # Initialize all scrapers
        self.scrapers = {
            "openai": OpenAIScraper(),
            "anthropic": AnthropicScraper(),
        }

    async def run_single_scraper(
        self,
        provider: str,
        scraper: Any
    ) -> tuple[str, ScraperResult, float]:
        """Run a single scraper with timing.
        
        Args:
            provider: Provider name
            scraper: Scraper instance
            
        Returns:
            Tuple of (provider, result, duration)
        """
        start = datetime.now()

        try:
            logger.info(f"Starting scraper for {provider}")
            result = await scraper.scrape()

            # If scraping failed, try cache
            if not result.success:
                logger.warning(f"Scraping failed for {provider}, trying cache")
                cache_entry = self.cache_manager.load(provider)
                if cache_entry and not cache_entry.is_expired():
                    logger.info(f"Using cached data for {provider}")
                    result = cache_entry.to_scraper_result()

            # Save successful results to cache
            if result.success and result.data:
                cache_entry = self.cache_manager.create_from_result(result)
                self.cache_manager.save(cache_entry)
                logger.info(f"Saved {len(result.data)} items to cache for {provider}")

        except Exception as e:
            logger.error(f"Unexpected error for {provider}: {e}")
            result = ScraperResult(
                success=False,
                provider=provider,
                error=ErrorContext(
                    url="",
                    timestamp=datetime.now(),
                    provider=provider,
                    error_type=type(e).__name__,
                ),
                timestamp=datetime.now(),
            )

        duration = (datetime.now() - start).total_seconds()
        return provider, result, duration

    async def run_all(
        self,
        providers: list[str] | None = None
    ) -> OrchestratorResult:
        """Run all scrapers in parallel.
        
        Args:
            providers: Optional list of providers to run (defaults to all)
            
        Returns:
            OrchestratorResult with aggregated data
        """
        start_time = datetime.now()

        # Filter scrapers if specific providers requested
        scrapers_to_run = self.scrapers
        if providers:
            scrapers_to_run = {
                name: scraper
                for name, scraper in self.scrapers.items()
                if name in providers
            }

        # Run all scrapers concurrently
        tasks = [
            self.run_single_scraper(name, scraper)
            for name, scraper in scrapers_to_run.items()
        ]

        results = await asyncio.gather(*tasks)

        # Aggregate results
        all_deprecations = []
        errors = []
        used_cache = []
        successful = 0
        failed = 0
        provider_timings = {}
        url_changes = {}

        for provider, result, duration in results:
            provider_timings[provider] = duration

            # Add provider info to each deprecation
            if result.data:
                for dep in result.data:
                    dep_with_provider = dep.copy()
                    dep_with_provider["provider"] = provider
                    all_deprecations.append(dep_with_provider)

            if result.success:
                successful += 1
                if result.from_cache:
                    used_cache.append(provider)
            else:
                failed += 1
                if result.error:
                    errors.append(result.error)

                    # Detect URL changes (redirects)
                    if result.error.status_code in [301, 302, 308]:
                        if result.error.headers and "Location" in result.error.headers:
                            url_changes[provider] = {
                                "old_url": result.error.url,
                                "new_url": result.error.headers["Location"],
                            }

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return OrchestratorResult(
            total_providers=len(scrapers_to_run),
            successful_providers=successful,
            failed_providers=failed,
            all_deprecations=all_deprecations,
            errors=errors,
            used_cache_for=used_cache,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            provider_timings=provider_timings,
            url_changes=url_changes if url_changes else None,
        )


async def main() -> None:
    """Main entry point for running all scrapers."""
    orchestrator = ScraperOrchestrator()
    error_analyzer = ErrorAnalyzer()
    notifier = NotificationManager()

    logger.info("Starting scraper orchestration")
    result = await orchestrator.run_all()

    # Print report
    print(result.generate_report())

    # Analyze errors and send notifications if needed
    if result.errors:
        for error in result.errors:
            error_analyzer.add_error(error)
        
        # Check for critical issues
        critical_issues = error_analyzer.get_critical_issues()
        if critical_issues:
            logger.warning(f"Found {len(critical_issues)} critical issues")
            for issue in critical_issues:
                await notifier.notify(
                    title=f"Critical: {issue['provider']} - {issue['error_type']}",
                    message=issue['description'],
                    priority="critical",
                    metadata=issue
                )
    
    # Check for URL changes
    if result.url_changes:
        for provider, urls in result.url_changes.items():
            await notifier.notify(
                title=f"URL Change Detected: {provider}",
                message=f"Provider {provider} URL changed from {urls['old_url']} to {urls['new_url']}",
                priority="warning",
                metadata=urls
            )

    # Save results to file
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"deprecations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        f.write(result.to_json())

    logger.info(f"Results saved to {output_file}")

    # Exit with appropriate code
    if result.failed_providers > 0 and result.successful_providers == 0:
        # All scrapers failed
        exit(1)
    elif result.failed_providers > 0:
        # Partial success
        logger.warning("Some scrapers failed but others succeeded")
        exit(0)
    else:
        # Complete success
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())
