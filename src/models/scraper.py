"""Pydantic models for scraping deprecation data from AI providers."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Provider(str, Enum):
    """Supported AI providers."""

    OPENAI = "OpenAI"
    ANTHROPIC = "Anthropic"
    GOOGLE_VERTEX_AI = "Google Vertex AI"
    AWS_BEDROCK = "AWS Bedrock"
    COHERE = "Cohere"
    AZURE_OPENAI = "Azure OpenAI"


class RawDeprecation(BaseModel):
    """Model for scraped deprecation data."""

    provider: Provider
    model_name: str
    deprecation_date: datetime | None = None
    retirement_date: datetime | None = None
    replacement: str | None = None
    notes: str | None = None
    source_url: HttpUrl | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_dates(self) -> "RawDeprecation":
        """Ensure retirement_date is after deprecation_date if both are present."""
        if self.deprecation_date and self.retirement_date and self.retirement_date <= self.deprecation_date:
            raise ValueError("retirement_date must be after deprecation_date")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary for serialization."""
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "deprecation_date": self.deprecation_date,
            "retirement_date": self.retirement_date,
            "replacement": self.replacement,
            "notes": self.notes,
            "source_url": str(self.source_url) if self.source_url else None,
            "scraped_at": self.scraped_at,
        }
