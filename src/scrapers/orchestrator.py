"""Scraper orchestrator for coordinating multiple scrapers."""

import asyncio
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.models.deprecation import Deprecation
from src.scrapers.base import BaseScraper
from src.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class OrchestratorConfig(BaseModel):
    """Configuration for the scraper orchestrator."""

    max_concurrent: int = Field(default=5, description="Maximum number of concurrent scrapers")
    timeout_seconds: float = Field(default=300.0, description="Timeout for individual scrapers")
    retry_failed: bool = Field(default=True, description="Whether to retry failed scrapers")
    fail_fast: bool = Field(default=False, description="Whether to fail fast on first error")


class OrchestratorResult(BaseModel):
    """Result summary from orchestrator execution."""

    total_scrapers: int = Field(description="Total number of scrapers")
    successful_scrapers: int = Field(description="Number of successful scrapers")
    failed_scrapers: int = Field(description="Number of failed scrapers")
    total_deprecations: int = Field(description="Total deprecations processed")
    new_deprecations: int = Field(description="Number of new deprecations stored")
    updated_deprecations: int = Field(description="Number of updated deprecations")
    execution_time_seconds: float = Field(description="Total execution time in seconds")
    errors: list[str] = Field(
        default_factory=list, description="Error messages from failed scrapers"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_scrapers == 0:
            return 0.0
        return self.successful_scrapers / self.total_scrapers


class ScraperOrchestrator:
    """Orchestrates multiple scrapers to collect deprecation data."""

    def __init__(self, storage: BaseStorage, config: OrchestratorConfig | None = None) -> None:
        """
        Initialize orchestrator with storage and configuration.

        Args:
            storage: Storage implementation for deprecation data
            config: Orchestrator configuration
        """
        self.storage = storage
        self.config = config or OrchestratorConfig()

    async def run(self, scrapers: list[BaseScraper]) -> OrchestratorResult:
        """
        Run all scrapers and aggregate results.

        Args:
            scrapers: List of scraper instances to run

        Returns:
            Summary of orchestration results

        Raises:
            Exception: If fail_fast is enabled and any scraper fails
        """
        start_time = time.time()
        logger.info(f"Starting orchestration of {len(scrapers)} scrapers")

        if not scrapers:
            logger.info("No scrapers to run")
            return OrchestratorResult(
                total_scrapers=0,
                successful_scrapers=0,
                failed_scrapers=0,
                total_deprecations=0,
                new_deprecations=0,
                updated_deprecations=0,
                execution_time_seconds=0.0,
                errors=[],
            )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Run scrapers with concurrency control
        tasks = []
        for scraper in scrapers:
            task = asyncio.create_task(self._run_single_scraper(scraper, semaphore))
            tasks.append(task)

        # Wait for all tasks to complete
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            if self.config.fail_fast:
                logger.error(f"Orchestration failed fast: {e}")
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise
            results = []

        # Process results
        successful_count = 0
        failed_count = 0
        all_deprecations: list[Deprecation] = []
        errors: list[str] = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_count += 1
                error_msg = f"Scraper {i} failed: {result}"
                errors.append(error_msg)
                logger.error(error_msg)

                if self.config.fail_fast:
                    raise result

            elif result is None:
                # Task was cancelled or returned None
                failed_count += 1
                error_msg = f"Scraper {i} returned no data"
                errors.append(error_msg)
                logger.warning(error_msg)
            else:
                # Ensure result is a tuple, not an exception
                if isinstance(result, tuple) and len(result) == 2:
                    deprecations, scraper_errors = result
                else:
                    # Handle unexpected result format
                    failed_count += 1
                    error_msg = f"Scraper {i} returned unexpected data format"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    continue

                if scraper_errors:
                    # Scraper returned errors - consider it failed
                    failed_count += 1
                    errors.extend(scraper_errors)
                else:
                    # Scraper succeeded
                    successful_count += 1
                    all_deprecations.extend(deprecations)

        # Store new deprecations and update existing ones
        new_count, updated_count = await self._store_deprecations(all_deprecations)

        execution_time = time.time() - start_time

        orchestration_result = OrchestratorResult(
            total_scrapers=len(scrapers),
            successful_scrapers=successful_count,
            failed_scrapers=failed_count,
            total_deprecations=len(all_deprecations),
            new_deprecations=new_count,
            updated_deprecations=updated_count,
            execution_time_seconds=execution_time,
            errors=errors,
        )

        logger.info(
            f"Orchestration completed: {orchestration_result.successful_scrapers}/{orchestration_result.total_scrapers} "
            f"scrapers successful, {orchestration_result.new_deprecations} new deprecations, "
            f"{orchestration_result.updated_deprecations} updated, {execution_time:.2f}s"
        )

        return orchestration_result

    async def _run_single_scraper(
        self, scraper: BaseScraper, semaphore: asyncio.Semaphore
    ) -> tuple[list[Deprecation], list[str]] | None:
        """
        Run a single scraper with concurrency control and timeout.

        Args:
            scraper: Scraper instance to run
            semaphore: Semaphore for concurrency control

        Returns:
            Tuple of (deprecations, errors) or None if failed
        """
        async with semaphore:
            try:
                # Run scraper with timeout
                data = await asyncio.wait_for(scraper.scrape(), timeout=self.config.timeout_seconds)

                # Parse deprecations from scraper data
                deprecations, errors = self._parse_scraper_data(data)

                logger.info(f"Scraper {scraper.url} completed: {len(deprecations)} deprecations")
                return deprecations, errors

            except TimeoutError:
                error_msg = f"Scraper {scraper.url} timed out after {self.config.timeout_seconds}s"
                logger.error(error_msg)
                return [], [error_msg]

            except Exception as e:
                error_msg = f"Scraper {scraper.url} failed: {e}"
                logger.error(error_msg)

                if self.config.fail_fast:
                    raise e
                else:
                    return [], [error_msg]

    def _parse_scraper_data(self, data: dict[str, Any]) -> tuple[list[Deprecation], list[str]]:
        """
        Parse raw scraper data into Deprecation objects.

        Args:
            data: Raw data from scraper

        Returns:
            Tuple of (parsed deprecations, parsing errors)
        """
        deprecations: list[Deprecation] = []
        errors: list[str] = []

        # Extract deprecations from scraper data
        raw_deprecations = data.get("deprecations", [])

        if not isinstance(raw_deprecations, list):
            errors.append("Scraper data 'deprecations' field is not a list")
            return deprecations, errors

        for raw_dep in raw_deprecations:
            try:
                # Validate and create Deprecation object
                deprecation = Deprecation.model_validate(raw_dep)
                deprecations.append(deprecation)
            except Exception as e:
                error_msg = f"Failed to parse deprecation: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)
                continue

        return deprecations, errors

    async def _store_deprecations(self, deprecations: list[Deprecation]) -> tuple[int, int]:
        """
        Store deprecations, handling both new and updated entries.

        Args:
            deprecations: List of deprecations to store

        Returns:
            Tuple of (new_count, updated_count)
        """
        if not deprecations:
            return 0, 0

        # Get existing deprecations to check for updates
        existing_deprecations = await self.storage.get_all()
        existing_by_identity = {dep.get_identity_hash(): dep for dep in existing_deprecations}

        new_deprecations = []
        updated_count = 0

        for deprecation in deprecations:
            identity_hash = deprecation.get_identity_hash()

            if identity_hash in existing_by_identity:
                # This is an update to existing deprecation
                existing_dep = existing_by_identity[identity_hash]

                # Only update if data has actually changed
                if existing_dep.get_hash() != deprecation.get_hash():
                    success = await self.storage.update(deprecation)
                    if success:
                        updated_count += 1
                        logger.debug(
                            f"Updated deprecation: {deprecation.provider} {deprecation.model}"
                        )
            else:
                # This is a new deprecation
                new_deprecations.append(deprecation)

        # Store new deprecations
        new_count = 0
        if new_deprecations:
            new_count = await self.storage.store(new_deprecations)
            logger.debug(f"Stored {new_count} new deprecations")

        return new_count, updated_count
