"""Data manager for handling scraper data persistence."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.models.deprecation import Deprecation, FeedData, ProviderStatus

logger = logging.getLogger(__name__)


class DataManager:
    """Manages loading and saving of scraper data to JSON format."""

    def __init__(self, data_file: Path = Path("data.json")) -> None:
        """Initialize the data manager.

        Args:
            data_file: Path to the JSON data file
        """
        self.data_file = data_file

    def load_feed_data(self) -> FeedData | None:
        """Load feed data from JSON file.

        Returns:
            FeedData if file exists and is valid, None otherwise
        """
        if not self.data_file.exists():
            logger.info(f"Data file {self.data_file} does not exist")
            return None

        try:
            with open(self.data_file) as f:
                data = json.load(f)

            deprecations = []
            for dep_data in data.get("deprecations", []):
                # Convert ISO strings back to datetime
                dep_data["deprecation_date"] = datetime.fromisoformat(dep_data["deprecation_date"])
                dep_data["retirement_date"] = datetime.fromisoformat(dep_data["retirement_date"])
                if "last_updated" in dep_data:
                    dep_data["last_updated"] = datetime.fromisoformat(dep_data["last_updated"])
                else:
                    dep_data["last_updated"] = datetime.now(UTC)
                deprecations.append(Deprecation(**dep_data))

            provider_statuses = []
            for status_data in data.get("provider_statuses", []):
                status_data["last_checked"] = datetime.fromisoformat(status_data["last_checked"])
                provider_statuses.append(ProviderStatus(**status_data))

            last_updated = (
                datetime.fromisoformat(data["last_updated"])
                if "last_updated" in data
                else datetime.now(UTC)
            )

            return FeedData(
                deprecations=deprecations,
                provider_statuses=provider_statuses,
                last_updated=last_updated,
            )
        except Exception as e:
            logger.error(f"Failed to load data from {self.data_file}: {e}")
            return None

    def save_feed_data(self, feed_data: FeedData) -> bool:
        """Save feed data to JSON file.

        Args:
            feed_data: The feed data to save

        Returns:
            True if save was successful, False otherwise
        """
        try:
            data = {
                "deprecations": [dep.to_json_dict() for dep in feed_data.deprecations],
                "provider_statuses": [
                    {
                        "name": status.name,
                        "last_checked": status.last_checked.isoformat(),
                        "is_healthy": status.is_healthy,
                        "error_message": status.error_message,
                    }
                    for status in feed_data.provider_statuses
                ],
                "last_updated": feed_data.last_updated.isoformat(),
            }

            # Create parent directory if it doesn't exist
            self.data_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(feed_data.deprecations)} deprecations to {self.data_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save data to {self.data_file}: {e}")
            return False

    def merge_feed_data(
        self, new_data: FeedData, existing_data: FeedData | None = None
    ) -> FeedData:
        """Merge new feed data with existing data.

        Args:
            new_data: New feed data to merge
            existing_data: Existing feed data (if None, will try to load from file)

        Returns:
            Merged FeedData
        """
        if existing_data is None:
            existing_data = self.load_feed_data()

        if existing_data is None:
            return new_data

        # Merge deprecations (using hash to avoid duplicates)
        merged_deprecations = {dep.get_hash(): dep for dep in existing_data.deprecations}
        for dep in new_data.deprecations:
            merged_deprecations[dep.get_hash()] = dep

        # Merge provider statuses (keeping the most recent for each provider)
        merged_statuses = {status.name: status for status in existing_data.provider_statuses}
        for status in new_data.provider_statuses:
            if (
                status.name not in merged_statuses
                or status.last_checked > merged_statuses[status.name].last_checked
            ):
                merged_statuses[status.name] = status

        return FeedData(
            deprecations=list(merged_deprecations.values()),
            provider_statuses=list(merged_statuses.values()),
            last_updated=max(new_data.last_updated, existing_data.last_updated),
        )

    def update_from_scraper_result(
        self, provider: str, scraper_result: dict[str, Any], merge_with_existing: bool = True
    ) -> FeedData:
        """Update data from a scraper result.

        Args:
            provider: Name of the provider
            scraper_result: Result from scraper.scrape() method
            merge_with_existing: Whether to merge with existing data

        Returns:
            Updated FeedData
        """
        deprecations = scraper_result.get("deprecations", [])

        # Ensure deprecations are DeprecationEntry objects
        if deprecations and not isinstance(deprecations[0], Deprecation):
            # Convert dict to DeprecationEntry if needed
            converted_deprecations = []
            for dep in deprecations:
                if isinstance(dep, dict):
                    # Convert datetime strings if present
                    if "deprecation_date" in dep and isinstance(dep["deprecation_date"], str):
                        dep["deprecation_date"] = datetime.fromisoformat(dep["deprecation_date"])
                    if "retirement_date" in dep and isinstance(dep["retirement_date"], str):
                        dep["retirement_date"] = datetime.fromisoformat(dep["retirement_date"])
                    if "last_updated" in dep and isinstance(dep["last_updated"], str):
                        dep["last_updated"] = datetime.fromisoformat(dep["last_updated"])
                    converted_deprecations.append(Deprecation(**dep))
                else:
                    converted_deprecations.append(dep)
            deprecations = converted_deprecations

        # Create provider status
        now = datetime.now(UTC)
        is_healthy = len(deprecations) > 0 or scraper_result.get("success", True)
        error_message = scraper_result.get("error")

        provider_status = ProviderStatus(
            name=provider,
            last_checked=now,
            is_healthy=is_healthy,
            error_message=error_message,
        )

        new_data = FeedData(
            deprecations=deprecations,
            provider_statuses=[provider_status],
            last_updated=now,
        )

        if merge_with_existing:
            return self.merge_feed_data(new_data)
        return new_data
