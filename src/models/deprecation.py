"""Deprecation model for AI model deprecation tracking."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class DeprecationEntry(BaseModel):
    """Model representing an AI model deprecation entry."""

    provider: str = Field(..., description="Provider name (e.g., OpenAI, Anthropic)")
    model: str = Field(..., description="Model name or identifier")
    deprecation_date: datetime = Field(..., description="Date when deprecation was announced")
    retirement_date: datetime = Field(..., description="Date when model stops working")
    replacement: str | None = Field(None, description="Suggested alternative model")
    notes: str | None = Field(None, description="Additional context or information")
    source_url: str | None = Field(None, description="Link to official announcement")

    @field_validator("provider", "model")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure provider and model are non-empty strings."""
        if not v or not v.strip():
            raise ValueError("Field must be a non-empty string")
        return v.strip()

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Basic URL validation."""
        if v is None:
            return None
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
            "link": self.source_url or "",
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


# Alias for compatibility with other branches that may use Deprecation
Deprecation = DeprecationEntry