"""Deprecation model for AI model deprecation tracking."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class DeprecationEntry(BaseModel):
    """Model representing an AI model deprecation entry."""

    provider: str = Field(..., description="Provider name (e.g., OpenAI, Anthropic)")
    model: str = Field(..., description="Model name or identifier")
    deprecation_date: datetime = Field(..., description="Date when deprecation was announced")
    retirement_date: datetime = Field(..., description="Date when model stops working")
    replacement: str | None = Field(None, description="Suggested alternative model")
    notes: str | None = Field(None, description="Additional context or information")
    source_url: str = Field(..., description="Link to official announcement")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this entry was last updated",
    )

    @field_validator("provider", "model")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure provider and model are non-empty strings."""
        if not v or not v.strip():
            raise ValueError("Field must be a non-empty string")
        return v.strip()

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "DeprecationEntry":
        """Ensure retirement date is after deprecation date."""
        if self.retirement_date <= self.deprecation_date:
            raise ValueError("Retirement date must be after deprecation date")
        return self

    def to_rss_item(self) -> dict[str, str | datetime]:
        """Convert to RSS item dictionary."""
        description_parts = [
            f"Provider: {self.provider}",
            f"Model: {self.model}",
            f"Deprecation Date: {self.deprecation_date.isoformat()}",
            f"Retirement Date: {self.retirement_date.isoformat()}",
        ]

        if self.replacement:
            description_parts.append(f"Replacement: {self.replacement}")

        if self.notes:
            description_parts.append(f"Notes: {self.notes}")

        description = "\n".join(description_parts)

        title = f"{self.provider} - {self.model} Deprecation"

        return {
            "title": title,
            "description": description,
            "link": self.source_url,
            "guid": f"{self.provider}-{self.model}-{self.deprecation_date.isoformat()}",
            "pubDate": self.deprecation_date,
        }

    def to_json_dict(self) -> dict[str, str | None]:
        """Convert to JSON-serializable dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "deprecation_date": self.deprecation_date.isoformat(),
            "retirement_date": self.retirement_date.isoformat(),
            "replacement": self.replacement,
            "notes": self.notes,
            "source_url": self.source_url,
        }

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }

    # Compatibility methods for main branch
    def is_active(self) -> bool:
        """Check if deprecation is still active (not yet retired)."""
        now = datetime.now(UTC)
        return self.retirement_date > now

    def get_hash(self) -> str:
        """Generate hash for core deprecation data."""
        import hashlib

        core_data = {
            "provider": self.provider,
            "model": self.model,
            "deprecation_date": self.deprecation_date.isoformat(),
            "retirement_date": self.retirement_date.isoformat(),
            "replacement": self.replacement,
            "notes": self.notes,
            "source_url": self.source_url,
        }
        data_str = str(sorted(core_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def get_identity_hash(self) -> str:
        """Generate hash for identifying same deprecation."""
        import hashlib

        identity_data = {
            "provider": self.provider,
            "model": self.model,
            "deprecation_date": self.deprecation_date.isoformat(),
            "retirement_date": self.retirement_date.isoformat(),
            "source_url": self.source_url,
        }
        data_str = str(sorted(identity_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def same_deprecation(self, other: "DeprecationEntry") -> bool:
        """Check if this represents the same deprecation."""
        return self.get_identity_hash() == other.get_identity_hash()

    @property
    def created_at(self) -> datetime:
        """Alias for compatibility with main branch."""
        return self.deprecation_date


# Alias for compatibility with other branches that may use Deprecation
Deprecation = DeprecationEntry
