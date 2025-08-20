"""Deprecation entry model for tracking AI model deprecations."""

import uuid
from datetime import UTC, datetime
from typing import Any

from dateutil import parser
from pydantic import BaseModel, Field, field_validator


class DeprecationEntry(BaseModel):
    """Model representing a single deprecation entry."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: str
    model_name: str
    deprecation_date: datetime | None = None
    retirement_date: datetime | None = None
    replacement: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("deprecation_date", "retirement_date", mode="before")
    @classmethod
    def ensure_timezone(cls, v: datetime | None) -> datetime | None:
        """Ensure datetime fields have timezone information."""
        if v is not None and isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    def to_rss_item(self) -> dict[str, Any]:
        """Convert deprecation entry to RSS item format."""
        title = f"{self.provider}: {self.model_name} Deprecation"

        description_parts = [
            f"Model: {self.model_name}",
            f"Provider: {self.provider}",
        ]

        if self.deprecation_date:
            description_parts.append(
                f"Deprecation Date: {self.deprecation_date.strftime('%Y-%m-%d')}"
            )
        else:
            description_parts.append("No deprecation date announced")

        if self.retirement_date:
            description_parts.append(
                f"Retirement Date: {self.retirement_date.strftime('%Y-%m-%d')}"
            )
        else:
            description_parts.append("No retirement date announced")

        if self.replacement:
            description_parts.append(f"Replacement: {self.replacement}")
        else:
            description_parts.append("No replacement specified")

        if self.notes:
            description_parts.append(f"Notes: {self.notes}")

        description = " | ".join(description_parts)

        return {
            "title": title,
            "description": description,
            "guid": self.id,
            "pubDate": self.created_at,
            "link": f"https://deprecations.example.com/models/{self.id}",
        }

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> "DeprecationEntry":
        """Create DeprecationEntry from raw deprecation data.

        Handles various field name mappings and date formats.
        """
        provider = raw_data.get("provider", "")
        model_name = raw_data.get("model", "") or raw_data.get("model_name", "")

        deprecation_date = None
        if deprecated_date_str := raw_data.get("deprecated_date"):
            try:
                deprecation_date = parser.parse(deprecated_date_str)
                if deprecation_date.tzinfo is None:
                    deprecation_date = deprecation_date.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                pass

        retirement_date = None
        if shutdown_date_str := raw_data.get("shutdown_date"):
            try:
                retirement_date = parser.parse(shutdown_date_str)
                if retirement_date.tzinfo is None:
                    retirement_date = retirement_date.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                pass

        replacement = raw_data.get("replacement_model") or raw_data.get("replacement")
        notes = raw_data.get("additional_info") or raw_data.get("notes")

        return cls(
            provider=provider,
            model_name=model_name,
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            replacement=replacement,
            notes=notes,
        )

    def is_active(self) -> bool:
        """Check if the deprecation entry is still active.

        Returns False if retirement_date has passed (including today).
        Returns True if no retirement_date or retirement_date is in the future.
        """
        if self.retirement_date is None:
            return True

        now = datetime.now(UTC)
        return self.retirement_date > now

