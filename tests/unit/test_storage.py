"""Test suite for storage interfaces and implementations."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.models.deprecation import Deprecation
from src.storage.base import BaseStorage
from src.storage.json_storage import JsonStorage


class _TestStorage(BaseStorage):
    """Test implementation of BaseStorage for testing abstract methods."""

    def __init__(self):
        self.data = []

    async def store(self, deprecations: list[Deprecation]) -> int:
        """Store deprecations."""
        stored_count = 0
        for dep in deprecations:
            if dep not in self.data:
                self.data.append(dep)
                stored_count += 1
        return stored_count

    async def get_all(self) -> list[Deprecation]:
        """Get all deprecations."""
        return self.data.copy()

    async def get_by_provider(self, provider: str) -> list[Deprecation]:
        """Get deprecations by provider."""
        return [dep for dep in self.data if dep.provider == provider]

    async def get_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Deprecation]:
        """Get deprecations by date range."""
        return [dep for dep in self.data if start_date <= dep.deprecation_date <= end_date]

    async def delete_by_provider(self, provider: str) -> int:
        """Delete deprecations by provider."""
        original_count = len(self.data)
        self.data = [dep for dep in self.data if dep.provider != provider]
        return original_count - len(self.data)

    async def clear_all(self) -> int:
        """Clear all deprecations."""
        count = len(self.data)
        self.data.clear()
        return count

    async def update(self, deprecation: Deprecation) -> bool:
        """Update existing deprecation."""
        for i, dep in enumerate(self.data):
            if dep.same_deprecation(deprecation):
                self.data[i] = deprecation
                return True
        return False


@pytest.fixture
def sample_deprecations():
    """Create sample deprecation data for tests."""
    base_date = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=base_date,
            retirement_date=base_date + timedelta(days=90),
            source_url="https://example.com/openai",
        ),
        Deprecation(
            provider="Anthropic",
            model="claude-v1",
            deprecation_date=base_date + timedelta(days=30),
            retirement_date=base_date + timedelta(days=120),
            source_url="https://example.com/anthropic",
        ),
        Deprecation(
            provider="OpenAI",
            model="gpt-4-0314",
            deprecation_date=base_date + timedelta(days=60),
            retirement_date=base_date + timedelta(days=150),
            source_url="https://example.com/openai2",
        ),
    ]


def describe_base_storage():
    """Test abstract base storage interface."""

    @pytest.mark.asyncio
    async def it_stores_deprecations(sample_deprecations):
        """Stores deprecations and returns count of new entries."""
        storage = _TestStorage()

        count = await storage.store(sample_deprecations)
        assert count == 3

        # Storing same data again should return 0
        count = await storage.store(sample_deprecations)
        assert count == 0

    @pytest.mark.asyncio
    async def it_gets_all_deprecations(sample_deprecations):
        """Retrieves all stored deprecations."""
        storage = _TestStorage()
        await storage.store(sample_deprecations)

        result = await storage.get_all()
        assert len(result) == 3
        assert all(dep in sample_deprecations for dep in result)

    @pytest.mark.asyncio
    async def it_gets_by_provider(sample_deprecations):
        """Retrieves deprecations filtered by provider."""
        storage = _TestStorage()
        await storage.store(sample_deprecations)

        openai_deps = await storage.get_by_provider("OpenAI")
        assert len(openai_deps) == 2
        assert all(dep.provider == "OpenAI" for dep in openai_deps)

        anthropic_deps = await storage.get_by_provider("Anthropic")
        assert len(anthropic_deps) == 1
        assert anthropic_deps[0].provider == "Anthropic"

    @pytest.mark.asyncio
    async def it_gets_by_date_range(sample_deprecations):
        """Retrieves deprecations filtered by date range."""
        storage = _TestStorage()
        await storage.store(sample_deprecations)

        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2024, 1, 31, tzinfo=UTC)

        result = await storage.get_by_date_range(start_date, end_date)
        assert len(result) == 2  # Should include first and second deprecation

    @pytest.mark.asyncio
    async def it_deletes_by_provider(sample_deprecations):
        """Deletes deprecations by provider."""
        storage = _TestStorage()
        await storage.store(sample_deprecations)

        deleted_count = await storage.delete_by_provider("OpenAI")
        assert deleted_count == 2

        remaining = await storage.get_all()
        assert len(remaining) == 1
        assert remaining[0].provider == "Anthropic"

    @pytest.mark.asyncio
    async def it_clears_all_deprecations(sample_deprecations):
        """Clears all stored deprecations."""
        storage = _TestStorage()
        await storage.store(sample_deprecations)

        cleared_count = await storage.clear_all()
        assert cleared_count == 3

        remaining = await storage.get_all()
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def it_updates_existing_deprecation(sample_deprecations):
        """Updates an existing deprecation."""
        storage = _TestStorage()
        await storage.store(sample_deprecations[:1])

        # Update the deprecation
        updated = sample_deprecations[0].model_copy()
        updated.notes = "Updated note"

        success = await storage.update(updated)
        assert success is True

        result = await storage.get_all()
        assert len(result) == 1
        assert result[0].notes == "Updated note"

    @pytest.mark.asyncio
    async def it_fails_to_update_nonexistent_deprecation():
        """Returns False when trying to update non-existent deprecation."""
        storage = _TestStorage()

        new_dep = Deprecation(
            provider="Test",
            model="test-model",
            deprecation_date=datetime.now(UTC),
            retirement_date=datetime.now(UTC) + timedelta(days=30),
            source_url="https://example.com",
        )

        success = await storage.update(new_dep)
        assert success is False


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def describe_json_storage():
    """Test JSON file storage implementation."""

    @pytest.mark.asyncio
    async def it_initializes_with_data_directory(temp_data_dir):
        """Initializes with data directory."""
        storage = JsonStorage(temp_data_dir)
        assert storage.data_dir == temp_data_dir
        assert storage.data_file == temp_data_dir / "deprecations.json"

    @pytest.mark.asyncio
    async def it_creates_data_directory_if_missing():
        """Creates data directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "nested" / "data"
            storage = JsonStorage(data_dir)

            # Directory should be created when storing data
            test_dep = Deprecation(
                provider="Test",
                model="test-model",
                deprecation_date=datetime.now(UTC),
                retirement_date=datetime.now(UTC) + timedelta(days=30),
                source_url="https://example.com",
            )

            await storage.store([test_dep])
            assert data_dir.exists()
            assert storage.data_file.exists()

    @pytest.mark.asyncio
    async def it_stores_and_loads_deprecations(temp_data_dir, sample_deprecations):
        """Stores deprecations to JSON file and loads them back."""
        storage = JsonStorage(temp_data_dir)

        count = await storage.store(sample_deprecations)
        assert count == 3

        # Verify file was created
        assert storage.data_file.exists()

        # Load data back
        loaded = await storage.get_all()
        assert len(loaded) == 3

        # Verify data integrity (comparing by hash since last_updated may differ)
        loaded_hashes = {dep.get_hash() for dep in loaded}
        original_hashes = {dep.get_hash() for dep in sample_deprecations}
        assert loaded_hashes == original_hashes

    @pytest.mark.asyncio
    async def it_merges_with_existing_data(temp_data_dir, sample_deprecations):
        """Merges new data with existing data in JSON file."""
        storage = JsonStorage(temp_data_dir)

        # Store first batch
        await storage.store(sample_deprecations[:2])
        first_load = await storage.get_all()
        assert len(first_load) == 2

        # Store additional data
        await storage.store([sample_deprecations[2]])
        second_load = await storage.get_all()
        assert len(second_load) == 3

    @pytest.mark.asyncio
    async def it_avoids_duplicate_storage(temp_data_dir, sample_deprecations):
        """Avoids storing duplicate deprecations."""
        storage = JsonStorage(temp_data_dir)

        # Store data twice
        count1 = await storage.store(sample_deprecations)
        count2 = await storage.store(sample_deprecations)

        assert count1 == 3
        assert count2 == 0  # No new entries

        loaded = await storage.get_all()
        assert len(loaded) == 3

    @pytest.mark.asyncio
    async def it_handles_empty_file(temp_data_dir):
        """Handles case where JSON file doesn't exist yet."""
        storage = JsonStorage(temp_data_dir)

        loaded = await storage.get_all()
        assert loaded == []

        # File shouldn't exist yet
        assert not storage.data_file.exists()

    @pytest.mark.asyncio
    async def it_handles_corrupted_json_file(temp_data_dir):
        """Handles corrupted JSON file gracefully."""
        storage = JsonStorage(temp_data_dir)

        # Create corrupted file
        storage.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(storage.data_file, "w") as f:
            f.write("invalid json content")

        # Should handle gracefully and return empty list
        loaded = await storage.get_all()
        assert loaded == []

    @pytest.mark.asyncio
    async def it_performs_atomic_writes(temp_data_dir, sample_deprecations):
        """Performs atomic writes to prevent corruption."""
        storage = JsonStorage(temp_data_dir)

        # Store initial data
        await storage.store(sample_deprecations[:1])

        # Verify temp file is not left behind
        temp_files = list(temp_data_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Verify data was written correctly
        loaded = await storage.get_all()
        assert len(loaded) == 1

    @pytest.mark.asyncio
    async def it_filters_by_provider(temp_data_dir, sample_deprecations):
        """Filters deprecations by provider."""
        storage = JsonStorage(temp_data_dir)
        await storage.store(sample_deprecations)

        openai_deps = await storage.get_by_provider("OpenAI")
        assert len(openai_deps) == 2
        assert all(dep.provider == "OpenAI" for dep in openai_deps)

    @pytest.mark.asyncio
    async def it_filters_by_date_range(temp_data_dir, sample_deprecations):
        """Filters deprecations by date range."""
        storage = JsonStorage(temp_data_dir)
        await storage.store(sample_deprecations)

        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2024, 1, 31, tzinfo=UTC)

        result = await storage.get_by_date_range(start_date, end_date)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def it_deletes_by_provider(temp_data_dir, sample_deprecations):
        """Deletes deprecations by provider and updates file."""
        storage = JsonStorage(temp_data_dir)
        await storage.store(sample_deprecations)

        deleted_count = await storage.delete_by_provider("OpenAI")
        assert deleted_count == 2

        # Verify persistence
        loaded = await storage.get_all()
        assert len(loaded) == 1
        assert loaded[0].provider == "Anthropic"

    @pytest.mark.asyncio
    async def it_clears_all_data(temp_data_dir, sample_deprecations):
        """Clears all data and removes file."""
        storage = JsonStorage(temp_data_dir)
        await storage.store(sample_deprecations)

        cleared_count = await storage.clear_all()
        assert cleared_count == 3

        # File should be removed
        assert not storage.data_file.exists()

        # Loading should return empty list
        loaded = await storage.get_all()
        assert loaded == []

    @pytest.mark.asyncio
    async def it_updates_existing_deprecation(temp_data_dir, sample_deprecations):
        """Updates existing deprecation in storage."""
        storage = JsonStorage(temp_data_dir)
        await storage.store(sample_deprecations[:1])

        # Update the deprecation
        updated = sample_deprecations[0].model_copy()
        updated.notes = "Updated note"
        updated.last_updated = datetime.now(UTC)

        success = await storage.update(updated)
        assert success is True

        # Verify persistence
        loaded = await storage.get_all()
        assert len(loaded) == 1
        assert loaded[0].notes == "Updated note"

    @pytest.mark.asyncio
    async def it_fails_to_update_nonexistent_deprecation(temp_data_dir):
        """Fails to update non-existent deprecation."""
        storage = JsonStorage(temp_data_dir)

        new_dep = Deprecation(
            provider="Test",
            model="test-model",
            deprecation_date=datetime.now(UTC),
            retirement_date=datetime.now(UTC) + timedelta(days=30),
            source_url="https://example.com",
        )

        success = await storage.update(new_dep)
        assert success is False
