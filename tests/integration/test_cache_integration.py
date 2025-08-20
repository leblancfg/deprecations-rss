"""Integration tests for the complete caching system."""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.cache import CacheManager, FileSystemStorage


class TestCacheIntegration:
    """Integration tests for cache system."""

    @pytest.mark.asyncio
    async def test_end_to_end_caching_workflow(self):
        """Test complete caching workflow with fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileSystemStorage(cache_dir=Path(tmpdir) / "test-cache")
            manager = CacheManager(storage=storage)

            # Simulate scraping OpenAI deprecation data
            openai_data = {
                "models": ["text-davinci-003", "code-davinci-002"],
                "deprecation_date": "2024-01-04",
                "details": "These models will be deprecated",
            }

            # Save the data
            success = await manager.save_deprecation_data("openai", openai_data)
            assert success

            # Retrieve the data
            retrieved_data = await manager.get_deprecation_data("openai")
            assert retrieved_data == openai_data

            # Test with fallback - data should come from cache
            async def failing_scraper():
                raise Exception("Scraper is down")

            key = storage.generate_key("deprecations", "anthropic", datetime.now(UTC))
            result = await manager.get_with_fallback(
                key, fetch_func=failing_scraper, use_stale_on_error=True
            )
            assert result is None  # No cached data, scraper failed

            # Now add some cached data for anthropic
            anthropic_data = {"models": ["claude-1"], "status": "deprecated"}
            await manager.save_deprecation_data("anthropic", anthropic_data)

            # Try again with fallback - should get cached data even though scraper fails
            result = await manager.get_deprecation_data("anthropic")
            assert result == anthropic_data

    @pytest.mark.asyncio
    async def test_cache_expiration_and_refresh(self):
        """Test cache expiration and refresh mechanism."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileSystemStorage(cache_dir=Path(tmpdir) / "test-cache")
            manager = CacheManager(storage=storage)

            fetch_count = 0

            async def data_fetcher():
                nonlocal fetch_count
                fetch_count += 1
                return {"version": fetch_count, "timestamp": datetime.now(UTC).isoformat()}

            key = "test:expiry"

            # First fetch - should call fetcher
            result1 = await manager.get_with_fallback(key, fetch_func=data_fetcher, ttl=2)
            assert result1["version"] == 1
            assert fetch_count == 1

            # Immediate second fetch - should use cache
            result2 = await manager.get_with_fallback(key, fetch_func=data_fetcher, ttl=2)
            assert result2["version"] == 1
            assert fetch_count == 1  # No new fetch

            # Wait for expiration
            await asyncio.sleep(3)

            # Third fetch - cache expired, should fetch new data
            result3 = await manager.get_with_fallback(key, fetch_func=data_fetcher, ttl=2)
            assert result3["version"] == 2
            assert fetch_count == 2

    @pytest.mark.asyncio
    async def test_multiple_providers_caching(self):
        """Test caching for multiple providers simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileSystemStorage(cache_dir=Path(tmpdir) / "test-cache")
            manager = CacheManager(storage=storage)

            # Save data for multiple providers
            providers_data = {
                "openai": {"deprecated": ["gpt-3"]},
                "anthropic": {"deprecated": ["claude-1"]},
                "google": {"deprecated": ["palm-1"]},
            }

            for provider, data in providers_data.items():
                await manager.save_deprecation_data(provider, data)

            # Retrieve all providers data
            all_data = await manager.get_all_providers_data()

            assert "openai" in all_data
            assert "anthropic" in all_data
            assert "google" in all_data
            assert all_data["openai"] == providers_data["openai"]
            assert all_data["anthropic"] == providers_data["anthropic"]
            assert all_data["google"] == providers_data["google"]

    @pytest.mark.asyncio
    async def test_historical_data_retrieval(self):
        """Test retrieving historical cached data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileSystemStorage(cache_dir=Path(tmpdir) / "test-cache")
            manager = CacheManager(storage=storage)

            # Save data for different dates
            base_date = datetime.now(UTC)
            for days_ago in range(5):
                date = base_date - timedelta(days=days_ago)
                data = {"day": days_ago, "date": date.isoformat()}

                # Save using the manager's save method
                success = await manager.save_deprecation_data("test-provider", data, date)
                assert success

            # Try to get data with max_age_days=3
            # Should get data from 0, 1, or 2 days ago
            result = await manager.get_deprecation_data("test-provider", base_date, max_age_days=3)
            assert result is not None

            # Try with a date from 10 days ago - should find nothing
            old_date = base_date - timedelta(days=10)
            result = await manager.get_deprecation_data("test-provider", old_date, max_age_days=3)
            assert result is None
