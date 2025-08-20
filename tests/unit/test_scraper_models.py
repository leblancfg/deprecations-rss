"""Tests for scraper models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.scraper import RawDeprecation


def describe_raw_deprecation():
    """Tests for RawDeprecation model."""

    def describe_creation():
        """Tests for model creation."""

        def test_creates_with_valid_data():
            """Should create model with all valid fields."""
            data = {
                "provider": "OpenAI",
                "model_name": "gpt-3.5-turbo-0301",
                "deprecation_date": datetime(2024, 1, 1, tzinfo=UTC),
                "retirement_date": datetime(2024, 6, 1, tzinfo=UTC),
                "replacement": "gpt-3.5-turbo",
                "notes": "Model being retired due to new version",
                "source_url": "https://platform.openai.com/docs/deprecations",
            }

            deprecation = RawDeprecation(**data)

            assert deprecation.provider == "OpenAI"
            assert deprecation.model_name == "gpt-3.5-turbo-0301"
            assert deprecation.deprecation_date == datetime(2024, 1, 1, tzinfo=UTC)
            assert deprecation.retirement_date == datetime(2024, 6, 1, tzinfo=UTC)
            assert deprecation.replacement == "gpt-3.5-turbo"
            assert deprecation.notes == "Model being retired due to new version"
            assert str(deprecation.source_url) == "https://platform.openai.com/docs/deprecations"
            assert deprecation.scraped_at is not None
            assert isinstance(deprecation.scraped_at, datetime)

        def test_creates_with_minimal_data():
            """Should create model with only required fields."""
            data = {
                "provider": "Anthropic",
                "model_name": "claude-1",
            }

            deprecation = RawDeprecation(**data)

            assert deprecation.provider == "Anthropic"
            assert deprecation.model_name == "claude-1"
            assert deprecation.deprecation_date is None
            assert deprecation.retirement_date is None
            assert deprecation.replacement is None
            assert deprecation.notes is None
            assert deprecation.source_url is None
            assert deprecation.scraped_at is not None

        def test_auto_sets_scraped_at():
            """Should automatically set scraped_at to current time."""
            before = datetime.now(UTC)
            deprecation = RawDeprecation(provider="Google Vertex AI", model_name="text-bison")
            after = datetime.now(UTC)

            assert before <= deprecation.scraped_at <= after

    def describe_validation():
        """Tests for validation logic."""

        def test_validates_provider_enum():
            """Should only accept valid provider values."""
            valid_providers = [
                "OpenAI",
                "Anthropic",
                "Google Vertex AI",
                "AWS Bedrock",
                "Cohere",
                "Azure OpenAI",
            ]

            for provider in valid_providers:
                deprecation = RawDeprecation(provider=provider, model_name="test-model")
                assert deprecation.provider == provider

        def test_rejects_invalid_provider():
            """Should reject invalid provider values."""
            with pytest.raises(ValidationError) as exc_info:
                RawDeprecation(provider="InvalidProvider", model_name="test-model")

            errors = exc_info.value.errors()
            assert len(errors) == 1
            assert "provider" in str(errors[0]["loc"])

        def test_validates_retirement_after_deprecation():
            """Should validate retirement_date is after deprecation_date."""
            with pytest.raises(ValidationError) as exc_info:
                RawDeprecation(
                    provider="OpenAI",
                    model_name="test-model",
                    deprecation_date=datetime(2024, 6, 1, tzinfo=UTC),
                    retirement_date=datetime(2024, 1, 1, tzinfo=UTC),
                )

            errors = exc_info.value.errors()
            assert len(errors) == 1
            assert "retirement_date must be after deprecation_date" in str(errors[0]["msg"])

        def test_allows_retirement_without_deprecation():
            """Should allow retirement_date without deprecation_date."""
            deprecation = RawDeprecation(
                provider="Cohere",
                model_name="command-light",
                retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
            )

            assert deprecation.retirement_date == datetime(2024, 6, 1, tzinfo=UTC)
            assert deprecation.deprecation_date is None

        def test_validates_url_format():
            """Should validate source_url is a valid URL."""
            with pytest.raises(ValidationError) as exc_info:
                RawDeprecation(
                    provider="AWS Bedrock", model_name="claude-v1", source_url="not-a-url"
                )

            errors = exc_info.value.errors()
            assert len(errors) == 1
            assert "source_url" in str(errors[0]["loc"])

    def describe_serialization():
        """Tests for serialization."""

        def test_to_dict_with_full_data():
            """Should serialize all fields to dict."""
            deprecation = RawDeprecation(
                provider="Azure OpenAI",
                model_name="gpt-35-turbo-0301",
                deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
                retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
                replacement="gpt-35-turbo",
                notes="Deprecating old version",
                source_url="https://azure.microsoft.com/updates",
            )

            data = deprecation.to_dict()

            assert data["provider"] == "Azure OpenAI"
            assert data["model_name"] == "gpt-35-turbo-0301"
            assert data["deprecation_date"] == datetime(2024, 1, 1, tzinfo=UTC)
            assert data["retirement_date"] == datetime(2024, 6, 1, tzinfo=UTC)
            assert data["replacement"] == "gpt-35-turbo"
            assert data["notes"] == "Deprecating old version"
            assert data["source_url"] == "https://azure.microsoft.com/updates"
            assert "scraped_at" in data

        def test_to_dict_with_minimal_data():
            """Should serialize with None values for optional fields."""
            deprecation = RawDeprecation(
                provider="OpenAI",
                model_name="babbage-002",
            )

            data = deprecation.to_dict()

            assert data["provider"] == "OpenAI"
            assert data["model_name"] == "babbage-002"
            assert data["deprecation_date"] is None
            assert data["retirement_date"] is None
            assert data["replacement"] is None
            assert data["notes"] is None
            assert data["source_url"] is None
            assert "scraped_at" in data
