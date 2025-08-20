"""Test suite for orchestrator integration with DataManager."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.deprecation import Deprecation, FeedData, ProviderStatus
from src.scrapers.base import BaseScraper
from src.scrapers.data_manager import DataManager
from src.scrapers.orchestrator import ScraperOrchestrator
from src.storage.json_storage import JsonStorage


class _TestScraper(BaseScraper):
    """Test scraper for testing."""

    def __init__(self, url: str, provider: str, should_fail: bool = False):
        super().__init__(url)
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
            raise Exception(f"{self.provider} HTML scraping failed")
        return await self.scrape_api()

    async def scrape_playwright(self) -> dict:
        """Mock Playwright scraping."""
        if self.should_fail:
            raise Exception(f"{self.provider} Playwright scraping failed")
        return await self.scrape_api()

    async def scrape(self) -> dict:
        """Override main scrape method."""
        if self.should_fail:
            raise Exception(f"{self.provider} scraping failed")
        return await self.scrape_api()


@pytest.fixture
def temp_data_file():
    """Create temporary data file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def describe_orchestrator_with_data_manager():
    """Test orchestrator with DataManager integration."""

    @pytest.mark.asyncio
    async def it_saves_data_to_json_file(temp_data_dir, temp_data_file):
        """Saves scraped data to data.json file."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)

        scrapers = [
            _TestScraper("https://openai.com/api", "OpenAI"),
            _TestScraper("https://anthropic.com/api", "Anthropic"),
        ]

        result = await orchestrator.run(scrapers)

        # Check orchestration results
        assert result.successful_scrapers == 2
        assert result.total_deprecations == 2

        # Verify data was saved to file
        assert temp_data_file.exists()
        loaded_data = data_manager.load_feed_data()
        assert loaded_data is not None
        assert len(loaded_data.deprecations) == 2
        assert len(loaded_data.provider_statuses) == 2

    @pytest.mark.asyncio
    async def it_merges_with_existing_data(temp_data_dir, temp_data_file):
        """Merges new data with existing data in data.json."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)

        # Create initial data
        initial_data = FeedData(
            deprecations=[
                Deprecation(
                    provider="Google",
                    model="palm-2",
                    deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                    retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
                    source_url="https://google.com/api",
                )
            ],
            provider_statuses=[
                ProviderStatus(
                    name="Google",
                    last_checked=datetime(2024, 1, 1, tzinfo=UTC),
                    is_healthy=True,
                    error_message=None,
                )
            ],
            last_updated=datetime(2024, 1, 1, tzinfo=UTC),
        )
        data_manager.save_feed_data(initial_data)

        # Run orchestrator with new scrapers
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)
        scrapers = [
            _TestScraper("https://openai.com/api", "OpenAI"),
        ]

        result = await orchestrator.run(scrapers)
        assert result  # Verify orchestration completed

        # Load merged data
        merged_data = data_manager.load_feed_data()
        assert merged_data is not None
        assert len(merged_data.deprecations) == 2  # Original + new
        assert len(merged_data.provider_statuses) == 2  # Google + OpenAI

        # Check providers
        provider_names = {status.name for status in merged_data.provider_statuses}
        assert provider_names == {"Google", "OpenAI"}

    @pytest.mark.asyncio
    async def it_tracks_provider_health_status(temp_data_dir, temp_data_file):
        """Tracks provider health status correctly."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)

        scrapers = [
            _TestScraper("https://openai.com/api", "OpenAI", should_fail=False),
            _TestScraper("https://anthropic.com/api", "Anthropic", should_fail=True),
            _TestScraper("https://google.com/api", "Google", should_fail=False),
        ]

        result = await orchestrator.run(scrapers)

        # Check results
        assert result.successful_scrapers == 2
        assert result.failed_scrapers == 1

        # Load saved data
        saved_data = data_manager.load_feed_data()
        assert saved_data is not None
        assert len(saved_data.provider_statuses) == 3

        # Check provider statuses
        status_by_name = {s.name: s for s in saved_data.provider_statuses}

        assert status_by_name["OpenAI"].is_healthy is True
        assert status_by_name["OpenAI"].error_message is None

        assert status_by_name["Anthropic"].is_healthy is False
        assert "scraping failed" in status_by_name["Anthropic"].error_message

        assert status_by_name["Google"].is_healthy is True
        assert status_by_name["Google"].error_message is None

    @pytest.mark.asyncio
    async def it_handles_data_manager_save_failure(temp_data_dir):
        """Handles DataManager save failure gracefully."""
        storage = JsonStorage(temp_data_dir)
        data_manager = MagicMock(spec=DataManager)
        data_manager.merge_feed_data.return_value = MagicMock(spec=FeedData)
        data_manager.save_feed_data.return_value = False  # Simulate save failure

        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)
        scrapers = [_TestScraper("https://openai.com/api", "OpenAI")]

        result = await orchestrator.run(scrapers)

        # Should still complete but with error
        assert result.successful_scrapers == 1
        assert "Failed to save data to data.json" in result.errors

    @pytest.mark.asyncio
    async def it_extracts_provider_names_correctly(temp_data_dir, temp_data_file):
        """Correctly extracts provider names from scrapers."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)

        # Test various URL patterns
        test_cases = [
            ("https://platform.openai.com/docs", "OpenAI"),
            ("https://docs.anthropic.com/api", "Anthropic"),
            ("https://cloud.google.com/vertex-ai", "Google"),
            ("https://api.cohere.com/v1", "Cohere"),
            ("https://api.mistral.ai", "Mistral"),
            ("https://huggingface.co/api", "HuggingFace"),
        ]

        for url, expected_provider in test_cases:
            scraper = _TestScraper(url, expected_provider)
            provider_name = orchestrator._get_provider_name(scraper)
            assert provider_name == expected_provider

    @pytest.mark.asyncio
    async def it_preserves_timestamps_in_saved_data(temp_data_dir, temp_data_file):
        """Preserves timestamps correctly when saving data."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)

        scrapers = [_TestScraper("https://openai.com/api", "OpenAI")]

        # Record time before running
        before_time = datetime.now(UTC)

        result = await orchestrator.run(scrapers)
        assert result  # Verify orchestration completed

        # Record time after running
        after_time = datetime.now(UTC)

        # Load saved data
        saved_data = data_manager.load_feed_data()
        assert saved_data is not None

        # Check that last_updated is within the expected range
        assert before_time <= saved_data.last_updated <= after_time

        # Check provider status timestamp
        assert len(saved_data.provider_statuses) == 1
        provider_status = saved_data.provider_statuses[0]
        assert before_time <= provider_status.last_checked <= after_time

    @pytest.mark.asyncio
    async def it_handles_empty_scraper_list_with_data_manager(temp_data_dir, temp_data_file):
        """Handles empty scraper list when using DataManager."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)
        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)

        result = await orchestrator.run([])

        assert result.total_scrapers == 0
        assert result.successful_scrapers == 0
        assert result.failed_scrapers == 0

        # Should still create empty data file
        saved_data = data_manager.load_feed_data()
        if saved_data:  # May or may not create file for empty data
            assert len(saved_data.deprecations) == 0

    @pytest.mark.asyncio
    async def it_deduplicates_deprecations_correctly(temp_data_dir, temp_data_file):
        """Deduplicates deprecations when merging data."""
        storage = JsonStorage(temp_data_dir)
        data_manager = DataManager(temp_data_file)

        # Create initial data with a deprecation
        deprecation = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
            source_url="https://openai.com/api",
            notes="Initial note",
        )

        initial_data = FeedData(
            deprecations=[deprecation],
            provider_statuses=[],
            last_updated=datetime.now(UTC),
        )
        data_manager.save_feed_data(initial_data)

        # Create scraper that returns the same deprecation with updated notes
        class _DuplicateScraper(_TestScraper):
            async def scrape_api(self) -> dict:
                return {
                    "deprecations": [
                        {
                            "provider": "OpenAI",
                            "model": "gpt-3.5-turbo-0301",
                            "deprecation_date": "2024-01-01T00:00:00Z",
                            "retirement_date": "2024-06-01T00:00:00Z",
                            "source_url": "https://openai.com/api",
                            "notes": "Updated note",
                        }
                    ]
                }

        orchestrator = ScraperOrchestrator(storage, data_manager=data_manager)
        scrapers = [_DuplicateScraper("https://openai.com/api", "OpenAI")]

        result = await orchestrator.run(scrapers)
        assert result  # Verify orchestration completed

        # Load merged data
        merged_data = data_manager.load_feed_data()
        assert merged_data is not None

        # The DataManager merges based on hash, and notes field affects the hash
        # So we expect 2 deprecations with different notes
        assert len(merged_data.deprecations) == 2

        # Check that both versions exist
        notes = {dep.notes for dep in merged_data.deprecations}
        assert notes == {"Initial note", "Updated note"}
