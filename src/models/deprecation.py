"""Data models for deprecation entries."""

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class Deprecation(BaseModel):
    """Model for AI model deprecation information."""

    provider: str = Field(description="Provider name (e.g., 'OpenAI', 'Anthropic')")
    model: str = Field(description="Affected model name")
    deprecation_date: datetime = Field(description="When the deprecation was announced")
    retirement_date: datetime = Field(description="When the model stops working")
    replacement: str | None = Field(default=None, description="Suggested alternative model")
    notes: str | None = Field(default=None, description="Additional context")
    source_url: HttpUrl = Field(description="URL where the deprecation info came from")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When we last checked this information"
    )

    @field_validator("deprecation_date", "retirement_date", "last_updated")
    @classmethod
    def ensure_utc_timezone(cls, v: datetime) -> datetime:
        """Ensure datetime fields have UTC timezone."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def validate_dates(self) -> "Deprecation":
        """Validate that retirement_date is after deprecation_date."""
        if self.retirement_date <= self.deprecation_date:
            raise ValueError("retirement_date must be after deprecation_date")
        return self

    def get_hash(self) -> str:
        """Generate hash of core deprecation data (excluding last_updated)."""
        # Include all fields that identify the unique deprecation, excluding last_updated
        core_data = {
            "provider": self.provider,
            "model": self.model,
            "deprecation_date": self.deprecation_date.isoformat(),
            "retirement_date": self.retirement_date.isoformat(),
            "replacement": self.replacement,
            "notes": self.notes,
            "source_url": str(self.source_url),
        }

        # Create deterministic string representation
        data_str = str(sorted(core_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def get_identity_hash(self) -> str:
        """Generate hash for identifying same deprecation (for updates)."""
        # Only include immutable fields that identify the unique deprecation
        identity_data = {
            "provider": self.provider,
            "model": self.model,
            "deprecation_date": self.deprecation_date.isoformat(),
            "retirement_date": self.retirement_date.isoformat(),
            "source_url": str(self.source_url),
        }

        # Create deterministic string representation
        data_str = str(sorted(identity_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def same_deprecation(self, other: "Deprecation") -> bool:
        """Check if this represents the same deprecation (for updates)."""
        return self.get_identity_hash() == other.get_identity_hash()

    def __eq__(self, other: object) -> bool:
        """Compare deprecations based on core data (excluding last_updated)."""
        if not isinstance(other, Deprecation):
            return False
        return self.get_hash() == other.get_hash()

    def __hash__(self) -> int:
        """Hash based on core data for use in sets/dicts."""
        return hash(self.get_hash())

    def __str__(self) -> str:
        """String representation of deprecation."""
        return (
            f"Deprecation({self.provider} {self.model}: "
            f"{self.deprecation_date.date()} -> {self.retirement_date.date()})"
        )

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"Deprecation(provider='{self.provider}', model='{self.model}', "
            f"deprecation_date={self.deprecation_date.isoformat()}, "
            f"retirement_date={self.retirement_date.isoformat()})"
        )
