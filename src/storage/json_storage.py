"""JSON file-based storage implementation for deprecation data."""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.models.deprecation import Deprecation
from src.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class JsonStorage(BaseStorage):
    """JSON file-based storage for historical deprecation data."""

    def __init__(self, data_dir: Path | str) -> None:
        """
        Initialize JSON storage with data directory.

        Args:
            data_dir: Directory to store JSON files in
        """
        self.data_dir = Path(data_dir)
        self.data_file = self.data_dir / "deprecations.json"

    async def store(self, deprecations: list[Deprecation]) -> int:
        """Store deprecations, avoiding duplicates."""
        # Load existing data
        existing = await self._load_from_file()
        existing_hashes = {dep.get_hash() for dep in existing}

        # Filter out duplicates
        new_deprecations = [dep for dep in deprecations if dep.get_hash() not in existing_hashes]

        if not new_deprecations:
            return 0

        # Merge with existing data
        all_deprecations = existing + new_deprecations

        # Save to file
        await self._save_to_file(all_deprecations)

        logger.info(f"Stored {len(new_deprecations)} new deprecations")
        return len(new_deprecations)

    async def get_all(self) -> list[Deprecation]:
        """Retrieve all stored deprecations."""
        return await self._load_from_file()

    async def get_by_provider(self, provider: str) -> list[Deprecation]:
        """Retrieve deprecations for a specific provider."""
        all_deprecations = await self._load_from_file()
        return [dep for dep in all_deprecations if dep.provider == provider]

    async def get_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Deprecation]:
        """Retrieve deprecations within a date range."""
        all_deprecations = await self._load_from_file()
        return [dep for dep in all_deprecations if start_date <= dep.deprecation_date <= end_date]

    async def delete_by_provider(self, provider: str) -> int:
        """Delete all deprecations for a specific provider."""
        all_deprecations = await self._load_from_file()
        original_count = len(all_deprecations)

        filtered_deprecations = [dep for dep in all_deprecations if dep.provider != provider]

        deleted_count = original_count - len(filtered_deprecations)

        if deleted_count > 0:
            await self._save_to_file(filtered_deprecations)
            logger.info(f"Deleted {deleted_count} deprecations for provider {provider}")

        return deleted_count

    async def clear_all(self) -> int:
        """Clear all stored deprecations."""
        all_deprecations = await self._load_from_file()
        count = len(all_deprecations)

        if count > 0:
            # Remove the file entirely
            if self.data_file.exists():
                self.data_file.unlink()
            logger.info(f"Cleared {count} deprecations")

        return count

    async def update(self, deprecation: Deprecation) -> bool:
        """Update an existing deprecation."""
        all_deprecations = await self._load_from_file()

        # Find the deprecation to update (by identity)
        for i, dep in enumerate(all_deprecations):
            if dep.same_deprecation(deprecation):
                all_deprecations[i] = deprecation
                await self._save_to_file(all_deprecations)
                logger.info(f"Updated deprecation: {deprecation.provider} {deprecation.model}")
                return True

        return False

    async def _load_from_file(self) -> list[Deprecation]:
        """Load deprecations from JSON file."""
        if not self.data_file.exists():
            return []

        try:
            with open(self.data_file, encoding="utf-8") as f:
                data = json.load(f)

            deprecations = []
            for item in data:
                try:
                    dep = Deprecation.model_validate(item)
                    deprecations.append(dep)
                except Exception as e:
                    logger.warning(f"Failed to parse deprecation item: {e}")
                    continue

            logger.debug(f"Loaded {len(deprecations)} deprecations from file")
            return deprecations

        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load deprecations from file: {e}")
            return []

    async def _save_to_file(self, deprecations: list[Deprecation]) -> None:
        """Save deprecations to JSON file using atomic write."""
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Prepare data for serialization
        data = []
        for dep in deprecations:
            try:
                # Use model_dump with custom serializer for datetime
                dep_data = dep.model_dump(mode="json")
                data.append(dep_data)
            except Exception as e:
                logger.warning(f"Failed to serialize deprecation: {e}")
                continue

        # Write to temporary file first (atomic write)
        temp_file = self.data_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self.data_file)
            logger.debug(f"Saved {len(deprecations)} deprecations to file")

        except OSError as e:
            logger.error(f"Failed to save deprecations to file: {e}")
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise
