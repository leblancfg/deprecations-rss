"""Test suite for the scraper orchestrator."""

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.deprecation import Deprecation
from src.models.scraper import ScraperConfig
from src.scrapers.base import BaseScraper
from src.scrapers.anthropic import AnthropicScraper
from src.scrapers.openai import OpenAIScraper
from src.scrapers.orchestrator import (
    OrchestratorConfig,
    OrchestratorResult,
    ScraperOrchestrator,
)
from src.storage.json_storage import JsonStorage


class _TestScraper(BaseScraper):
    """Test scraper that returns predictable data."""

    def __init__(
        self,
        url: str,
        provider: str,
        should_fail: bool = False,
        config: ScraperConfig | None = None,
    ):
        super().__init__(url, config)
        self.provider = provider
        self.should_fail = should_fail

    async def scrape_api(self) -> dict:
        """Mock API scraping."""
        if self.should_fail:
            raise Exception(f"{self.provider} scraping failed")

        return {
            "deprecations": [
                {
                    "provider": self.provider,
                    "model": f"{self.provider.lower()}-model-1",
                    "deprecation_date": "2024-01-01T00:00:00Z",
                    "retirement_date": "2024-04-01T00:00:00Z",
                    "source_url": self.url,
                    "notes": f"Test deprecation from {self.provider}",
                }
            ]
        }

    async def scrape_html(self) -> dict:
        """Mock HTML scraping."""
        if self.should_fail:
            raise Exception(f"{self.provider} scraping failed")
        return await self.scrape_api()

    async def scrape_playwright(self) -> dict:
        """Mock Playwright scraping."""
        if self.should_fail:
            raise Exception(f"{self.provider} scraping failed")
        return await self.scrape_api()

    async def scrape(self) -> dict:
        """Override main scrape method to control failure."""
        if self.should_fail:
            raise Exception(f"{self.provider} scraping failed")
        return await super().scrape()


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def orchestrator_config():
    """Create test orchestrator configuration."""
    return OrchestratorConfig(
        max_concurrent=2, timeout_seconds=30, retry_failed=True, fail_fast=False
    )


@pytest.fixture
def sample_scrapers():
    """Create sample scrapers for testing."""
    return [
        _TestScraper("https://openai.com/api", "OpenAI"),
        _TestScraper("https://anthropic.com/api", "Anthropic"),
        _TestScraper("https://google.com/api", "Google"),
    ]


def describe_orchestrator_config():
    """Test orchestrator configuration."""

    def it_creates_with_defaults():
        """Creates config with default values."""
        config = OrchestratorConfig()
        assert config.max_concurrent == 5
        assert config.timeout_seconds == 300
        assert config.retry_failed is True
        assert config.fail_fast is False

    def it_accepts_custom_values():
        """Accepts custom configuration values."""
        config = OrchestratorConfig(
            max_concurrent=3, timeout_seconds=60, retry_failed=False, fail_fast=True
        )
        assert config.max_concurrent == 3
        assert config.timeout_seconds == 60
        assert config.retry_failed is False
        assert config.fail_fast is True


def describe_orchestrator_result():
    """Test orchestrator result model."""

    def it_creates_result_summary():
        """Creates result summary with all fields."""
        result = OrchestratorResult(
            total_scrapers=3,
            successful_scrapers=2,
            failed_scrapers=1,
            total_deprecations=5,
            new_deprecations=3,
            updated_deprecations=2,
            execution_time_seconds=45.5,
            errors=["OpenAI scraper failed: API error"],
        )

        assert result.total_scrapers == 3
        assert result.successful_scrapers == 2
        assert result.failed_scrapers == 1
        assert result.total_deprecations == 5
        assert result.new_deprecations == 3
        assert result.updated_deprecations == 2
        assert result.execution_time_seconds == 45.5
        assert len(result.errors) == 1

    def it_calculates_success_rate():
        """Calculates success rate property."""
        result = OrchestratorResult(
            total_scrapers=4,
            successful_scrapers=3,
            failed_scrapers=1,
            total_deprecations=0,
            new_deprecations=0,
            updated_deprecations=0,
            execution_time_seconds=0,
            errors=[],
        )

        assert result.success_rate == 0.75

    def it_handles_zero_scrapers():
        """Handles zero scrapers gracefully."""
        result = OrchestratorResult(
            total_scrapers=0,
            successful_scrapers=0,
            failed_scrapers=0,
            total_deprecations=0,
            new_deprecations=0,
            updated_deprecations=0,
            execution_time_seconds=0,
            errors=[],
        )

        assert result.success_rate == 0.0


def describe_scraper_orchestrator():
    """Test scraper orchestrator functionality."""

    @pytest.mark.asyncio
    async def it_initializes_correctly(temp_data_dir):
        """Initializes with storage and configuration."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig()

        orchestrator = ScraperOrchestrator(storage, config)
        assert orchestrator.storage == storage
        assert orchestrator.config == config

    @pytest.mark.asyncio
    async def it_runs_single_scraper_successfully(temp_data_dir):
        """Runs a single scraper successfully."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        scrapers = [_TestScraper("https://openai.com/api", "OpenAI")]
        result = await orchestrator.run(scrapers)

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 1
        assert result.failed_scrapers == 0
        assert result.total_deprecations == 1
        assert result.new_deprecations == 1
        assert result.updated_deprecations == 0
        assert len(result.errors) == 0
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def it_runs_multiple_scrapers_concurrently(temp_data_dir, sample_scrapers):
        """Runs multiple scrapers concurrently."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(max_concurrent=2)
        orchestrator = ScraperOrchestrator(storage, config)

        result = await orchestrator.run(sample_scrapers)

        assert result.total_scrapers == 3
        assert result.successful_scrapers == 3
        assert result.failed_scrapers == 0
        assert result.total_deprecations == 3
        assert result.new_deprecations == 3
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def it_handles_scraper_failures_gracefully(temp_data_dir):
        """Handles scraper failures gracefully."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        scrapers = [
            _TestScraper("https://openai.com/api", "OpenAI", should_fail=False),
            _TestScraper("https://anthropic.com/api", "Anthropic", should_fail=True),
            _TestScraper("https://google.com/api", "Google", should_fail=False),
        ]

        result = await orchestrator.run(scrapers)

        assert result.total_scrapers == 3
        assert result.successful_scrapers == 2
        assert result.failed_scrapers == 1
        assert result.total_deprecations == 2
        assert result.new_deprecations == 2
        assert len(result.errors) == 1
        assert "Anthropic scraping failed" in result.errors[0]
        assert result.success_rate == 2 / 3

    @pytest.mark.asyncio
    async def it_fails_fast_when_configured(temp_data_dir):
        """Fails fast when fail_fast is enabled."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(fail_fast=True)
        orchestrator = ScraperOrchestrator(storage, config)

        scrapers = [
            _TestScraper("https://openai.com/api", "OpenAI", should_fail=True),
            _TestScraper("https://anthropic.com/api", "Anthropic", should_fail=False),
            _TestScraper("https://google.com/api", "Google", should_fail=False),
        ]

        with pytest.raises(Exception, match="OpenAI scraping failed"):
            await orchestrator.run(scrapers)

    @pytest.mark.asyncio
    async def it_respects_concurrency_limits(temp_data_dir, sample_scrapers):
        """Respects concurrency limits."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(max_concurrent=1)
        orchestrator = ScraperOrchestrator(storage, config)

        # Mock semaphore to verify it's being used
        with patch("asyncio.Semaphore") as mock_semaphore:
            mock_semaphore.return_value.__aenter__ = AsyncMock()
            mock_semaphore.return_value.__aexit__ = AsyncMock()

            await orchestrator.run(sample_scrapers)

            # Semaphore should be created with correct limit
            mock_semaphore.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def it_handles_timeout_gracefully(temp_data_dir):
        """Handles timeout gracefully."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(timeout_seconds=0.1)  # Very short timeout
        orchestrator = ScraperOrchestrator(storage, config)

        # Create a slow scraper
        slow_scraper = _TestScraper("https://slow.com/api", "SlowProvider")

        # Mock the scrape method to be slow
        async def slow_scrape():
            await asyncio.sleep(1)  # Longer than timeout
            return {"deprecations": []}

        slow_scraper.scrape = slow_scrape

        result = await orchestrator.run([slow_scraper])

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 0
        assert result.failed_scrapers == 1
        assert len(result.errors) == 1
        assert "timed out" in result.errors[0].lower() or "cancelled" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def it_updates_existing_deprecations(temp_data_dir):
        """Updates existing deprecations when found."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        # Store initial deprecation
        initial_dep = Deprecation(
            provider="OpenAI",
            model="openai-model-1",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://openai.com/api",
            notes="Initial note",
        )
        await storage.store([initial_dep])

        # Run scraper that returns updated version
        class _UpdatedScraper(_TestScraper):
            async def scrape_api(self) -> dict:
                return {
                    "deprecations": [
                        {
                            "provider": "OpenAI",
                            "model": "openai-model-1",
                            "deprecation_date": "2024-01-01T00:00:00Z",
                            "retirement_date": "2024-04-01T00:00:00Z",
                            "source_url": "https://openai.com/api",
                            "notes": "Updated note",
                            "replacement": "new-model",
                        }
                    ]
                }

        scrapers = [_UpdatedScraper("https://openai.com/api", "OpenAI")]
        result = await orchestrator.run(scrapers)

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 1
        assert result.total_deprecations == 1
        assert result.new_deprecations == 0
        assert result.updated_deprecations == 1

    @pytest.mark.asyncio
    async def it_tracks_execution_time(temp_data_dir, sample_scrapers):
        """Tracks execution time."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        result = await orchestrator.run(sample_scrapers)

        assert result.execution_time_seconds > 0
        assert isinstance(result.execution_time_seconds, float)

    @pytest.mark.asyncio
    async def it_handles_empty_scraper_list(temp_data_dir):
        """Handles empty scraper list gracefully."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        result = await orchestrator.run([])

        assert result.total_scrapers == 0
        assert result.successful_scrapers == 0
        assert result.failed_scrapers == 0
        assert result.total_deprecations == 0
        assert result.new_deprecations == 0
        assert result.updated_deprecations == 0
        assert len(result.errors) == 0
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def it_handles_malformed_scraper_data(temp_data_dir):
        """Handles malformed data from scrapers gracefully."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        class _MalformedScraper(_TestScraper):
            async def scrape_api(self) -> dict:
                return {
                    "deprecations": [
                        {
                            "provider": "Test",
                            "model": "test-model",
                            # Missing required fields
                        }
                    ]
                }

        scrapers = [_MalformedScraper("https://test.com/api", "Test")]
        result = await orchestrator.run(scrapers)

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 0  # Scraper failed due to malformed data
        assert result.failed_scrapers == 1
        assert result.total_deprecations == 0  # No valid deprecations
        assert result.new_deprecations == 0
        assert len(result.errors) > 0  # Should have parsing errors

    @pytest.mark.asyncio
    async def it_logs_detailed_progress(temp_data_dir, sample_scrapers):
        """Logs detailed progress information."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        # Mock logger to verify logging calls
        with patch("src.scrapers.orchestrator.logger") as mock_logger:
            await orchestrator.run(sample_scrapers)

            # Verify progress logging
            assert mock_logger.info.call_count >= 3  # At least start and end messages

            # Check for specific log messages
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Starting orchestration" in call for call in log_calls)
            assert any("Orchestration completed" in call for call in log_calls)

    @pytest.mark.asyncio
    async def it_preserves_storage_data_integrity(temp_data_dir):
        """Preserves storage data integrity across runs."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        # First run
        scrapers1 = [_TestScraper("https://openai.com/api", "OpenAI")]
        result1 = await orchestrator.run(scrapers1)
        assert result1.new_deprecations == 1

        # Second run with different provider
        scrapers2 = [_TestScraper("https://anthropic.com/api", "Anthropic")]
        result2 = await orchestrator.run(scrapers2)
        assert result2.new_deprecations == 1

        # Verify both deprecations are stored
        all_deps = await storage.get_all()
        assert len(all_deps) == 2
        assert {dep.provider for dep in all_deps} == {"OpenAI", "Anthropic"}


def describe_openai_scraper_integration():
    """Test OpenAI scraper integration with orchestrator."""

    @pytest.mark.asyncio
    async def it_integrates_openai_scraper_successfully(temp_data_dir):
        """Integrates OpenAI scraper successfully."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        # Mock the OpenAI scraper's scrape method
        openai_scraper = OpenAIScraper()

        async def mock_scrape():
            return {
                "deprecations": [
                    {
                        "provider": "OpenAI",
                        "model": "gpt-3.5-turbo-0301",
                        "deprecation_date": "2024-01-01T00:00:00Z",
                        "retirement_date": "2024-06-01T00:00:00Z",
                        "replacement": "gpt-3.5-turbo",
                        "source_url": "https://platform.openai.com/docs/deprecations",
                        "notes": "Legacy model being replaced",
                    }
                ]
            }

        openai_scraper.scrape = mock_scrape

        result = await orchestrator.run([openai_scraper])

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 1
        assert result.failed_scrapers == 0
        assert result.total_deprecations == 1
        assert result.new_deprecations == 1

    @pytest.mark.asyncio
    async def it_handles_openai_scraper_failures(temp_data_dir):
        """Handles OpenAI scraper failures gracefully."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(fail_fast=False)
        orchestrator = ScraperOrchestrator(storage, config)

        # Create OpenAI scraper that will fail
        openai_scraper = OpenAIScraper()

        async def mock_failing_scrape():
            raise Exception("OpenAI API rate limit exceeded")

        openai_scraper.scrape = mock_failing_scrape

        # Create another working scraper
        working_scraper = _TestScraper("https://anthropic.com/api", "Anthropic")

        result = await orchestrator.run([openai_scraper, working_scraper])

        assert result.total_scrapers == 2
        assert result.successful_scrapers == 1
        assert result.failed_scrapers == 1
        assert len(result.errors) == 1
        assert "OpenAI API rate limit exceeded" in result.errors[0]

    @pytest.mark.asyncio
    async def it_runs_openai_scraper_with_other_scrapers(temp_data_dir):
        """Runs OpenAI scraper concurrently with other scrapers."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(max_concurrent=3)
        orchestrator = ScraperOrchestrator(storage, config)

        # Create OpenAI scraper with mock data
        openai_scraper = OpenAIScraper()

        async def mock_openai_scrape():
            return {
                "deprecations": [
                    {
                        "provider": "OpenAI",
                        "model": "text-davinci-003",
                        "deprecation_date": "2024-01-04T00:00:00Z",
                        "retirement_date": "2025-01-04T00:00:00Z",
                        "replacement": "gpt-3.5-turbo-instruct",
                        "source_url": "https://platform.openai.com/docs/deprecations",
                    },
                    {
                        "provider": "OpenAI",
                        "model": "code-davinci-002",
                        "deprecation_date": "2024-03-01T00:00:00Z",
                        "retirement_date": "2024-09-01T00:00:00Z",
                        "source_url": "https://platform.openai.com/docs/deprecations",
                    },
                ]
            }

        openai_scraper.scrape = mock_openai_scrape

        # Add other scrapers
        scrapers = [
            openai_scraper,
            _TestScraper("https://anthropic.com/api", "Anthropic"),
            _TestScraper("https://google.com/api", "Google"),
        ]

        result = await orchestrator.run(scrapers)

        assert result.total_scrapers == 3
        assert result.successful_scrapers == 3
        assert result.failed_scrapers == 0
        assert result.total_deprecations == 4  # 2 from OpenAI, 1 each from others
        assert result.new_deprecations == 4

    @pytest.mark.asyncio
    async def it_respects_timeout_for_openai_scraper(temp_data_dir):
        """Respects timeout configuration for OpenAI scraper."""
        storage = JsonStorage(temp_data_dir)
        config = OrchestratorConfig(timeout_seconds=0.1)
        orchestrator = ScraperOrchestrator(storage, config)

        # Create OpenAI scraper that will timeout
        openai_scraper = OpenAIScraper()

        async def slow_scrape():
            await asyncio.sleep(1)  # Longer than timeout
            return {"deprecations": []}

        openai_scraper.scrape = slow_scrape

        result = await orchestrator.run([openai_scraper])

        assert result.total_scrapers == 1
        assert result.successful_scrapers == 0
        assert result.failed_scrapers == 1
        assert len(result.errors) == 1
        assert "timed out" in result.errors[0].lower() or "cancelled" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def it_handles_duplicate_deprecations_from_openai(temp_data_dir):
        """Handles duplicate deprecations from OpenAI scraper correctly."""
        storage = JsonStorage(temp_data_dir)
        orchestrator = ScraperOrchestrator(storage)

        # First run with OpenAI scraper
        openai_scraper1 = OpenAIScraper()

        async def mock_scrape1():
            return {
                "deprecations": [
                    {
                        "provider": "OpenAI",
                        "model": "gpt-4-0314",
                        "deprecation_date": "2024-06-13T00:00:00Z",
                        "retirement_date": "2025-06-13T00:00:00Z",
                        "source_url": "https://platform.openai.com/docs/deprecations",
                    }
                ]
            }

        openai_scraper1.scrape = mock_scrape1

        result1 = await orchestrator.run([openai_scraper1])
        assert result1.new_deprecations == 1

        # Second run with same deprecation but updated notes
        openai_scraper2 = OpenAIScraper()

        async def mock_scrape2():
            return {
                "deprecations": [
                    {
                        "provider": "OpenAI",
                        "model": "gpt-4-0314",
                        "deprecation_date": "2024-06-13T00:00:00Z",
                        "retirement_date": "2025-06-13T00:00:00Z",
                        "source_url": "https://platform.openai.com/docs/deprecations",
                        "notes": "Updated: Migration guide available",
                    }
                ]
            }

        openai_scraper2.scrape = mock_scrape2

        result2 = await orchestrator.run([openai_scraper2])
        assert result2.new_deprecations == 0
        assert result2.updated_deprecations == 1

        # Verify only one deprecation exists
        all_deps = await storage.get_all()
        assert len(all_deps) == 1
        assert all_deps[0].notes == "Updated: Migration guide available"
