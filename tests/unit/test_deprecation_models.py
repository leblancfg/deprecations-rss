"""Test suite for deprecation data models."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.models.deprecation import Deprecation


def describe_deprecation_model():
    """Test deprecation data model."""

    def it_creates_with_required_fields():
        """Creates deprecation with required fields."""
        deprecation_date = datetime.now(UTC)
        retirement_date = deprecation_date + timedelta(days=90)

        deprecation = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            source_url="https://example.com/deprecation-notice",
        )

        assert deprecation.provider == "OpenAI"
        assert deprecation.model == "gpt-3.5-turbo-0301"
        assert deprecation.deprecation_date == deprecation_date
        assert deprecation.retirement_date == retirement_date
        assert str(deprecation.source_url) == "https://example.com/deprecation-notice"
        assert deprecation.replacement is None
        assert deprecation.notes is None
        assert isinstance(deprecation.last_updated, datetime)
        assert deprecation.last_updated.tzinfo == UTC

    def it_creates_with_optional_fields():
        """Creates deprecation with all fields including optional ones."""
        deprecation_date = datetime.now(UTC)
        retirement_date = deprecation_date + timedelta(days=90)
        last_updated = datetime.now(UTC) - timedelta(hours=1)

        deprecation = Deprecation(
            provider="Anthropic",
            model="claude-v1",
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            replacement="claude-3-haiku",
            notes="This model is being retired in favor of Claude 3.",
            source_url="https://docs.anthropic.com/deprecations",
            last_updated=last_updated,
        )

        assert deprecation.replacement == "claude-3-haiku"
        assert deprecation.notes == "This model is being retired in favor of Claude 3."
        assert deprecation.last_updated == last_updated

    def it_requires_provider():
        """Raises ValidationError when provider is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                model="test-model",
                deprecation_date=datetime.now(UTC),
                retirement_date=datetime.now(UTC) + timedelta(days=30),
                source_url="https://example.com",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("provider",) for error in errors)

    def it_requires_model():
        """Raises ValidationError when model is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                deprecation_date=datetime.now(UTC),
                retirement_date=datetime.now(UTC) + timedelta(days=30),
                source_url="https://example.com",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("model",) for error in errors)

    def it_requires_deprecation_date():
        """Raises ValidationError when deprecation_date is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                model="test-model",
                retirement_date=datetime.now(UTC) + timedelta(days=30),
                source_url="https://example.com",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("deprecation_date",) for error in errors)

    def it_requires_retirement_date():
        """Raises ValidationError when retirement_date is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                model="test-model",
                deprecation_date=datetime.now(UTC),
                source_url="https://example.com",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("retirement_date",) for error in errors)

    def it_requires_source_url():
        """Raises ValidationError when source_url is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                model="test-model",
                deprecation_date=datetime.now(UTC),
                retirement_date=datetime.now(UTC) + timedelta(days=30),
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("source_url",) for error in errors)

    def it_validates_source_url_format():
        """Validates that source_url is a valid URL."""
        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                model="test-model",
                deprecation_date=datetime.now(UTC),
                retirement_date=datetime.now(UTC) + timedelta(days=30),
                source_url="not-a-url",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("source_url",) for error in errors)

    def it_validates_retirement_after_deprecation():
        """Validates that retirement_date is after deprecation_date."""
        deprecation_date = datetime.now(UTC)
        retirement_date = deprecation_date - timedelta(days=1)  # Before deprecation

        with pytest.raises(ValidationError) as exc_info:
            Deprecation(
                provider="TestProvider",
                model="test-model",
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                source_url="https://example.com",
            )

        errors = exc_info.value.errors()
        assert any(
            "Retirement date must be after deprecation date" in str(error["msg"])
            for error in errors
        )

    def it_serializes_to_dict():
        """Serializes deprecation to dictionary."""
        deprecation_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        retirement_date = datetime(2024, 4, 1, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

        deprecation = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            replacement="gpt-3.5-turbo",
            notes="Upgrading to newer version",
            source_url="https://example.com/notice",
            last_updated=last_updated,
        )

        data = deprecation.model_dump()

        assert data["provider"] == "OpenAI"
        assert data["model"] == "gpt-3.5-turbo-0301"
        assert data["deprecation_date"] == deprecation_date
        assert data["retirement_date"] == retirement_date
        assert data["replacement"] == "gpt-3.5-turbo"
        assert data["notes"] == "Upgrading to newer version"
        assert str(data["source_url"]) == "https://example.com/notice"
        assert data["last_updated"] == last_updated

    def it_serializes_to_json():
        """Serializes deprecation to JSON string."""
        deprecation_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        retirement_date = datetime(2024, 4, 1, 12, 0, 0, tzinfo=UTC)

        deprecation = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            source_url="https://example.com/notice",
        )

        json_str = deprecation.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["provider"] == "OpenAI"
        assert parsed["model"] == "gpt-3.5-turbo-0301"
        # Check that datetime is serialized as ISO string
        assert "2024-01-01T12:00:00" in parsed["deprecation_date"]

    def it_deserializes_from_dict():
        """Deserializes deprecation from dictionary."""
        data = {
            "provider": "Anthropic",
            "model": "claude-v1",
            "deprecation_date": "2024-01-01T12:00:00+00:00",
            "retirement_date": "2024-04-01T12:00:00+00:00",
            "replacement": "claude-3-haiku",
            "notes": "Upgrading to Claude 3",
            "source_url": "https://docs.anthropic.com",
            "last_updated": "2024-01-15T10:30:00+00:00",
        }

        deprecation = Deprecation.model_validate(data)

        assert deprecation.provider == "Anthropic"
        assert deprecation.model == "claude-v1"
        assert deprecation.deprecation_date == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert deprecation.retirement_date == datetime(2024, 4, 1, 12, 0, 0, tzinfo=UTC)
        assert deprecation.replacement == "claude-3-haiku"
        assert deprecation.notes == "Upgrading to Claude 3"
        assert str(deprecation.source_url) == "https://docs.anthropic.com"
        assert deprecation.last_updated == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def it_generates_consistent_hash():
        """Generates consistent hash for same deprecation data."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        # Same core data should generate same hash (ignoring last_updated)
        hash1 = deprecation1.get_hash()
        hash2 = deprecation2.get_hash()
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex digest length

    def it_generates_different_hash_for_different_data():
        """Generates different hash for different deprecation data."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-4",  # Different model
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        hash1 = deprecation1.get_hash()
        hash2 = deprecation2.get_hash()
        assert hash1 != hash2

    def it_supports_equality_comparison():
        """Supports equality comparison based on core fields."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            last_updated=datetime.now(UTC),
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            last_updated=datetime.now(UTC) + timedelta(hours=1),  # Different last_updated
        )

        # Should be equal despite different last_updated (core data is same)
        assert deprecation1 == deprecation2

    def it_supports_inequality_comparison():
        """Supports inequality comparison based on core fields."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        deprecation2 = Deprecation(
            provider="Anthropic",  # Different provider
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        assert deprecation1 != deprecation2

    def it_has_string_representation():
        """Has meaningful string representation."""
        deprecation = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        str_repr = str(deprecation)
        assert "OpenAI" in str_repr
        assert "gpt-3.5-turbo-0301" in str_repr
        assert "2024-01-01" in str_repr
        assert "2024-04-01" in str_repr

    def it_generates_identity_hash():
        """Generates identity hash based on immutable fields."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            notes="Original note",
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            notes="Updated note",  # Different notes
        )

        # Should have same identity hash despite different notes
        identity1 = deprecation1.get_identity_hash()
        identity2 = deprecation2.get_identity_hash()
        assert identity1 == identity2
        assert isinstance(identity1, str)
        assert len(identity1) == 64

    def it_recognizes_same_deprecation():
        """Recognizes same deprecation for updates."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            notes="Original note",
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
            notes="Updated note",
            replacement="gpt-3.5-turbo",
        )

        # Should recognize as same deprecation despite different notes/replacement
        assert deprecation1.same_deprecation(deprecation2) is True
        assert deprecation2.same_deprecation(deprecation1) is True

    def it_recognizes_different_deprecations():
        """Recognizes different deprecations."""
        deprecation1 = Deprecation(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        deprecation2 = Deprecation(
            provider="OpenAI",
            model="gpt-4",  # Different model
            deprecation_date=datetime(2024, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 1, tzinfo=UTC),
            source_url="https://example.com",
        )

        # Should recognize as different deprecations
        assert deprecation1.same_deprecation(deprecation2) is False
        assert deprecation2.same_deprecation(deprecation1) is False
