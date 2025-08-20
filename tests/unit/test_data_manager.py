"""Tests for the data manager module."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.scrapers.data_manager import DataManager


class TestDataManager:
    """Tests for DataManager class."""

    def test_save_and_load_feed_data(self):
        """Test saving and loading FeedData."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            manager = DataManager(tmp_path)

            # Create test data
            deprecations = [
                DeprecationEntry(
                    provider="TestProvider",
                    model="test-model-1",
                    deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                    retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
                    replacement="new-model",
                    notes="Test notes",
                    source_url="https://example.com",
                ),
                DeprecationEntry(
                    provider="TestProvider",
                    model="test-model-2",
                    deprecation_date=datetime(2024, 2, 1, tzinfo=UTC),
                    retirement_date=datetime(2024, 7, 1, tzinfo=UTC),
                    replacement=None,
                    notes=None,
                    source_url="https://example.com/2",
                ),
            ]
            provider_statuses = [
                ProviderStatus(
                    name="TestProvider",
                    last_checked=datetime(2024, 3, 1, tzinfo=UTC),
                    is_healthy=True,
                    error_message=None,
                ),
                ProviderStatus(
                    name="AnotherProvider",
                    last_checked=datetime(2024, 3, 1, tzinfo=UTC),
                    is_healthy=False,
                    error_message="Connection timeout",
                ),
            ]
            feed_data = FeedData(
                deprecations=deprecations,
                provider_statuses=provider_statuses,
                last_updated=datetime(2024, 3, 1, tzinfo=UTC),
            )

            # Save data
            success = manager.save_feed_data(feed_data)
            assert success is True
            assert tmp_path.exists()

            # Load data
            loaded_data = manager.load_feed_data()
            assert loaded_data is not None
            assert len(loaded_data.deprecations) == 2
            assert loaded_data.deprecations[0].model == "test-model-1"
            assert loaded_data.deprecations[1].model == "test-model-2"
            assert len(loaded_data.provider_statuses) == 2
            assert loaded_data.provider_statuses[0].name == "TestProvider"
            assert loaded_data.provider_statuses[1].error_message == "Connection timeout"

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading from a non-existent file returns None."""
        manager = DataManager(Path("/nonexistent/file.json"))
        result = manager.load_feed_data()
        assert result is None

    def test_merge_feed_data(self):
        """Test merging feed data."""
        manager = DataManager()

        # Create existing data
        existing_deprecations = [
            DeprecationEntry(
                provider="Provider1",
                model="old-model",
                deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
                replacement="newer-model",
                notes="Old deprecation",
                source_url="https://example.com/old",
            )
        ]
        existing_statuses = [
            ProviderStatus(
                name="Provider1",
                last_checked=datetime(2024, 2, 1, tzinfo=UTC),
                is_healthy=True,
                error_message=None,
            )
        ]
        existing_data = FeedData(
            deprecations=existing_deprecations,
            provider_statuses=existing_statuses,
            last_updated=datetime(2024, 2, 1, tzinfo=UTC),
        )

        # Create new data
        new_deprecations = [
            DeprecationEntry(
                provider="Provider2",
                model="new-model",
                deprecation_date=datetime(2024, 3, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 8, 1, tzinfo=UTC),
                replacement="latest-model",
                notes="New deprecation",
                source_url="https://example.com/new",
            )
        ]
        new_statuses = [
            ProviderStatus(
                name="Provider1",  # Same provider, newer timestamp
                last_checked=datetime(2024, 3, 1, tzinfo=UTC),
                is_healthy=False,
                error_message="API changed",
            ),
            ProviderStatus(
                name="Provider2",
                last_checked=datetime(2024, 3, 1, tzinfo=UTC),
                is_healthy=True,
                error_message=None,
            ),
        ]
        new_data = FeedData(
            deprecations=new_deprecations,
            provider_statuses=new_statuses,
            last_updated=datetime(2024, 3, 1, tzinfo=UTC),
        )

        # Merge data
        merged = manager.merge_feed_data(new_data, existing_data)

        # Check merged deprecations
        assert len(merged.deprecations) == 2
        models = {dep.model for dep in merged.deprecations}
        assert "old-model" in models
        assert "new-model" in models

        # Check merged provider statuses (should have latest for each provider)
        assert len(merged.provider_statuses) == 2
        provider1_status = next(s for s in merged.provider_statuses if s.name == "Provider1")
        assert provider1_status.is_healthy is False  # Should have the newer status
        assert provider1_status.error_message == "API changed"
        assert provider1_status.last_checked == datetime(2024, 3, 1, tzinfo=UTC)

    def test_update_from_scraper_result(self):
        """Test updating data from scraper result."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            manager = DataManager(tmp_path)

            # Create scraper result
            scraper_result = {
                "deprecations": [
                    DeprecationEntry(
                        provider="OpenAI",
                        model="gpt-3.5-turbo-0301",
                        deprecation_date=datetime(2024, 6, 13, tzinfo=UTC),
                        retirement_date=datetime(2024, 9, 13, tzinfo=UTC),
                        replacement="gpt-3.5-turbo",
                        notes="Model snapshot being retired",
                        source_url="https://openai.com/deprecations",
                    )
                ],
                "success": True,
            }

            # Update from scraper result
            feed_data = manager.update_from_scraper_result(
                "OpenAI", scraper_result, merge_with_existing=False
            )

            assert len(feed_data.deprecations) == 1
            assert feed_data.deprecations[0].model == "gpt-3.5-turbo-0301"
            assert len(feed_data.provider_statuses) == 1
            assert feed_data.provider_statuses[0].name == "OpenAI"
            assert feed_data.provider_statuses[0].is_healthy is True

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_update_from_scraper_result_with_error(self):
        """Test updating data from scraper result with error."""
        manager = DataManager()

        # Create scraper result with error
        scraper_result = {
            "deprecations": [],
            "success": False,
            "error": "Failed to connect to API",
        }

        # Update from scraper result
        feed_data = manager.update_from_scraper_result(
            "FailedProvider", scraper_result, merge_with_existing=False
        )

        assert len(feed_data.deprecations) == 0
        assert len(feed_data.provider_statuses) == 1
        assert feed_data.provider_statuses[0].name == "FailedProvider"
        assert feed_data.provider_statuses[0].is_healthy is False
        assert feed_data.provider_statuses[0].error_message == "Failed to connect to API"

    def test_save_creates_parent_directory(self):
        """Test that save creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "data.json"
            manager = DataManager(nested_path)

            feed_data = FeedData(
                deprecations=[],
                provider_statuses=[],
                last_updated=datetime.now(UTC),
            )

            success = manager.save_feed_data(feed_data)
            assert success is True
            assert nested_path.exists()
            assert nested_path.parent.exists()
