"""Tests for scraper orchestration."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scrapers.base import ErrorContext, ScraperResult
from src.scrapers.run_all import ScraperOrchestrator


def describe_ScraperOrchestrator():
    """Test the scraper orchestration system."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        cache = tmp_path / "cache"
        cache.mkdir()
        return cache

    @pytest.fixture
    def orchestrator(self, cache_dir):
        """Create orchestrator instance."""
        return ScraperOrchestrator(cache_dir=cache_dir)

    @pytest.fixture
    def mock_scrapers(self):
        """Create mock scrapers."""
        openai_scraper = MagicMock()
        openai_scraper.provider_name = "openai"
        openai_scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=True,
            provider="openai",
            data=[{"model": "gpt-4", "deprecation_date": "2024-01-01"}],
            timestamp=datetime.now(),
        ))

        anthropic_scraper = MagicMock()
        anthropic_scraper.provider_name = "anthropic"
        anthropic_scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=True,
            provider="anthropic",
            data=[{"model": "claude-2", "deprecation_date": "2024-02-01"}],
            timestamp=datetime.now(),
        ))

        return {
            "openai": openai_scraper,
            "anthropic": anthropic_scraper,
        }

    async def it_initializes_with_default_scrapers(self, orchestrator):
        """Should initialize with default scrapers."""
        assert len(orchestrator.scrapers) >= 2
        assert "openai" in orchestrator.scrapers
        assert "anthropic" in orchestrator.scrapers

    async def it_runs_all_scrapers_in_parallel(self, orchestrator, mock_scrapers):
        """Should run all scrapers concurrently."""
        orchestrator.scrapers = mock_scrapers

        start_time = asyncio.get_event_loop().time()
        result = await orchestrator.run_all()
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should complete quickly (parallel execution)
        assert elapsed < 1.0
        assert result.total_providers == 2
        assert result.successful_providers == 2
        assert len(result.all_deprecations) == 2

    async def it_handles_individual_scraper_failures(self, orchestrator):
        """Should continue if individual scrapers fail."""
        failing_scraper = MagicMock()
        failing_scraper.provider_name = "failing"
        failing_scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=False,
            provider="failing",
            error=ErrorContext(
                url="https://example.com",
                timestamp=datetime.now(),
                provider="failing",
                error_type="TestError",
            ),
            timestamp=datetime.now(),
        ))

        success_scraper = MagicMock()
        success_scraper.provider_name = "success"
        success_scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=True,
            provider="success",
            data=[{"model": "test-model"}],
            timestamp=datetime.now(),
        ))

        orchestrator.scrapers = {
            "failing": failing_scraper,
            "success": success_scraper,
        }

        result = await orchestrator.run_all()

        assert result.total_providers == 2
        assert result.successful_providers == 1
        assert result.failed_providers == 1
        assert len(result.all_deprecations) == 1

    async def it_uses_cache_fallback_on_failure(self, orchestrator, cache_dir):
        """Should use cached data when scraping fails."""
        from src.scrapers.cache import CacheEntry

        # Create cached data
        cached_entry = CacheEntry(
            provider="openai",
            data=[{"model": "cached-gpt-4", "deprecation_date": "2024-01-01"}],
            timestamp=datetime.now() - timedelta(hours=12),
            expires_at=datetime.now() + timedelta(hours=11),
        )

        with patch.object(orchestrator.cache_manager, "load") as mock_load:
            mock_load.return_value = cached_entry

            failing_scraper = MagicMock()
            failing_scraper.provider_name = "openai"
            failing_scraper.scrape = AsyncMock(return_value=ScraperResult(
                success=False,
                provider="openai",
                error=ErrorContext(
                    url="https://example.com",
                    timestamp=datetime.now(),
                    provider="openai",
                    error_type="NetworkError",
                ),
                timestamp=datetime.now(),
            ))

            orchestrator.scrapers = {"openai": failing_scraper}

            result = await orchestrator.run_all()

            assert result.total_providers == 1
            assert result.successful_providers == 1  # Cache counts as success
            assert result.used_cache_for == ["openai"]
            assert result.all_deprecations[0]["model"] == "cached-gpt-4"

    async def it_aggregates_results_correctly(self, orchestrator, mock_scrapers):
        """Should aggregate results from all scrapers."""
        orchestrator.scrapers = mock_scrapers

        result = await orchestrator.run_all()

        assert len(result.all_deprecations) == 2

        # Check each deprecation has provider info
        for dep in result.all_deprecations:
            assert "provider" in dep
            assert dep["provider"] in ["openai", "anthropic"]

    async def it_collects_error_contexts(self, orchestrator):
        """Should collect error contexts from failed scrapers."""
        error1 = ErrorContext(
            url="https://openai.com",
            timestamp=datetime.now(),
            provider="openai",
            error_type="HTTPError",
            status_code=404,
        )

        error2 = ErrorContext(
            url="https://anthropic.com",
            timestamp=datetime.now(),
            provider="anthropic",
            error_type="TimeoutError",
        )

        scraper1 = MagicMock()
        scraper1.provider_name = "openai"
        scraper1.scrape = AsyncMock(return_value=ScraperResult(
            success=False,
            provider="openai",
            error=error1,
            timestamp=datetime.now(),
        ))

        scraper2 = MagicMock()
        scraper2.provider_name = "anthropic"
        scraper2.scrape = AsyncMock(return_value=ScraperResult(
            success=False,
            provider="anthropic",
            error=error2,
            timestamp=datetime.now(),
        ))

        orchestrator.scrapers = {
            "openai": scraper1,
            "anthropic": scraper2,
        }

        result = await orchestrator.run_all()

        assert len(result.errors) == 2
        assert result.errors[0].provider == "openai"
        assert result.errors[0].status_code == 404
        assert result.errors[1].provider == "anthropic"

    async def it_respects_provider_filter(self, orchestrator, mock_scrapers):
        """Should only run specified providers when filtered."""
        orchestrator.scrapers = mock_scrapers

        result = await orchestrator.run_all(providers=["openai"])

        assert result.total_providers == 1
        assert result.successful_providers == 1
        assert result.all_deprecations[0]["provider"] == "openai"

        # Anthropic scraper should not have been called
        mock_scrapers["anthropic"].scrape.assert_not_called()

    async def it_saves_successful_results_to_cache(self, orchestrator, mock_scrapers):
        """Should save successful scrapes to cache."""
        orchestrator.scrapers = mock_scrapers

        with patch.object(orchestrator.cache_manager, "save") as mock_save:
            result = await orchestrator.run_all()

            # Should save both successful scrapes
            assert mock_save.call_count == 2

    async def it_handles_partial_data_with_errors(self, orchestrator):
        """Should handle scrapers returning partial data with errors."""
        scraper = MagicMock()
        scraper.provider_name = "partial"
        scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=False,  # Failed but has partial data
            provider="partial",
            data=[{"model": "partial-model", "deprecation_date": "2024-01-01"}],
            error=ErrorContext(
                url="https://example.com/page2",
                timestamp=datetime.now(),
                provider="partial",
                error_type="PartialFailure",
            ),
            timestamp=datetime.now(),
        ))

        orchestrator.scrapers = {"partial": scraper}

        result = await orchestrator.run_all()

        assert result.total_providers == 1
        assert result.failed_providers == 1
        assert len(result.all_deprecations) == 1  # Partial data included
        assert len(result.errors) == 1

    async def it_tracks_timing_information(self, orchestrator, mock_scrapers):
        """Should track timing for each scraper."""
        orchestrator.scrapers = mock_scrapers

        result = await orchestrator.run_all()

        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration_seconds >= 0
        assert result.provider_timings is not None
        assert "openai" in result.provider_timings
        assert "anthropic" in result.provider_timings

    async def it_detects_url_changes(self, orchestrator):
        """Should detect and report URL changes."""
        error = ErrorContext(
            url="https://openai.com/old-url",
            timestamp=datetime.now(),
            provider="openai",
            error_type="HTTPStatusError",
            status_code=301,
            headers={"Location": "https://openai.com/new-url"},
        )

        scraper = MagicMock()
        scraper.provider_name = "openai"
        scraper.scrape = AsyncMock(return_value=ScraperResult(
            success=False,
            provider="openai",
            error=error,
            timestamp=datetime.now(),
        ))

        orchestrator.scrapers = {"openai": scraper}

        result = await orchestrator.run_all()

        assert result.url_changes is not None
        assert "openai" in result.url_changes
        assert result.url_changes["openai"]["old_url"] == "https://openai.com/old-url"
        assert result.url_changes["openai"]["new_url"] == "https://openai.com/new-url"

    async def it_generates_summary_report(self, orchestrator, mock_scrapers):
        """Should generate a summary report."""
        orchestrator.scrapers = mock_scrapers

        result = await orchestrator.run_all()
        report = result.generate_report()

        assert "Scraper Orchestration Report" in report
        assert "Total Providers: 2" in report
        assert "Successful: 2" in report
        assert "Total Deprecations Found: 2" in report

    async def it_exports_to_json(self, orchestrator, mock_scrapers):
        """Should export results to JSON format."""
        orchestrator.scrapers = mock_scrapers

        result = await orchestrator.run_all()
        json_data = result.to_json()

        import json
        parsed = json.loads(json_data)

        assert parsed["total_providers"] == 2
        assert len(parsed["deprecations"]) == 2
        assert "timestamp" in parsed
        assert "duration_seconds" in parsed
