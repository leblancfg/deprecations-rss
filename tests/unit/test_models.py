"""Tests for deprecation data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus


class TestDeprecationEntry:
    """Tests for DeprecationEntry model."""

    def test_creates_valid_deprecation_entry(self) -> None:
        """It creates a valid deprecation entry with all required fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 6, 13, tzinfo=UTC),
            retirement_date=datetime(2024, 9, 13, tzinfo=UTC),
            replacement="gpt-3.5-turbo",
            notes="This model will be retired 3 months after deprecation",
            source_url="https://platform.openai.com/docs/deprecations",
        )

        assert entry.provider == "OpenAI"
        assert entry.model == "gpt-3.5-turbo-0301"
        assert entry.deprecation_date == datetime(2024, 6, 13, tzinfo=UTC)
        assert entry.retirement_date == datetime(2024, 9, 13, tzinfo=UTC)
        assert entry.replacement == "gpt-3.5-turbo"
        assert entry.notes == "This model will be retired 3 months after deprecation"
        assert entry.url == "https://platform.openai.com/docs/deprecations"

    def test_allows_optional_fields(self) -> None:
        """It allows optional fields to be None."""
        entry = DeprecationEntry(
            provider="Anthropic",
            model="claude-2",
            deprecation_date=datetime(2024, 7, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 10, 1, tzinfo=UTC),  # Now required
            replacement=None,
            notes=None,
            source_url="https://anthropic.com/deprecations",  # Now required
        )

        assert entry.provider == "Anthropic"
        assert entry.model == "claude-2"
        assert entry.retirement_date == datetime(2024, 10, 1, tzinfo=UTC)
        assert entry.replacement is None
        assert entry.notes is None
        assert str(entry.source_url) == "https://anthropic.com/deprecations"

    def test_validates_required_fields(self) -> None:
        """It validates that required fields are present."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-4",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert len(errors) >= 3  # deprecation_date, retirement_date, source_url are required
        field_names = {error["loc"][0] for error in errors}
        assert "deprecation_date" in field_names
        assert "retirement_date" in field_names
        assert "source_url" in field_names

    def test_serializes_to_dict(self) -> None:
        """It serializes to dictionary correctly."""
        entry = DeprecationEntry(
            provider="Google",
            model="palm-2",
            deprecation_date=datetime(2024, 12, 1, tzinfo=UTC),
            retirement_date=datetime(2025, 3, 1, tzinfo=UTC),
            replacement="gemini-pro",
            notes="Migrating to Gemini models",
            source_url="https://ai.google.dev/deprecations",
        )

        data = entry.model_dump()
        assert data["provider"] == "Google"
        assert data["model"] == "palm-2"
        assert isinstance(data["deprecation_date"], datetime)


class TestProviderStatus:
    """Tests for ProviderStatus model."""

    def test_creates_healthy_provider_status(self) -> None:
        """It creates a provider status for a healthy provider."""
        status = ProviderStatus(
            name="OpenAI",
            last_checked=datetime(2024, 8, 20, 12, 0, 0, tzinfo=UTC),
            is_healthy=True,
            error_message=None,
        )

        assert status.name == "OpenAI"
        assert status.last_checked == datetime(2024, 8, 20, 12, 0, 0, tzinfo=UTC)
        assert status.is_healthy is True
        assert status.error_message is None

    def test_creates_unhealthy_provider_status(self) -> None:
        """It creates a provider status for an unhealthy provider."""
        status = ProviderStatus(
            name="AWS Bedrock",
            last_checked=datetime(2024, 8, 20, 12, 0, 0, tzinfo=UTC),
            is_healthy=False,
            error_message="Connection timeout",
        )

        assert status.name == "AWS Bedrock"
        assert status.is_healthy is False
        assert status.error_message == "Connection timeout"

    def test_validates_required_fields(self) -> None:
        """It validates that required fields are present."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderStatus(
                name="Cohere",
                is_healthy=True,
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("last_checked",)


class TestFeedData:
    """Tests for FeedData model."""

    def test_creates_feed_data_with_entries(self) -> None:
        """It creates feed data with deprecation entries and provider statuses."""
        deprecation = DeprecationEntry(
            provider="OpenAI",
            model="text-davinci-003",
            deprecation_date=datetime(2024, 1, 4, tzinfo=UTC),
            retirement_date=datetime(2024, 4, 4, tzinfo=UTC),
            replacement="gpt-3.5-turbo",
            notes="Legacy model retirement",
            source_url="https://platform.openai.com/docs/deprecations",
        )

        provider_status = ProviderStatus(
            name="OpenAI",
            last_checked=datetime(2024, 8, 20, 15, 30, 0, tzinfo=UTC),
            is_healthy=True,
            error_message=None,
        )

        feed = FeedData(
            deprecations=[deprecation],
            provider_statuses=[provider_status],
            last_updated=datetime(2024, 8, 20, 15, 30, 0, tzinfo=UTC),
        )

        assert len(feed.deprecations) == 1
        assert feed.deprecations[0].model == "text-davinci-003"
        assert len(feed.provider_statuses) == 1
        assert feed.provider_statuses[0].name == "OpenAI"
        assert feed.last_updated == datetime(2024, 8, 20, 15, 30, 0, tzinfo=UTC)

    def test_creates_empty_feed_data(self) -> None:
        """It creates feed data with empty lists."""
        feed = FeedData(
            deprecations=[],
            provider_statuses=[],
            last_updated=datetime.now(UTC),
        )

        assert feed.deprecations == []
        assert feed.provider_statuses == []
        assert isinstance(feed.last_updated, datetime)

    def test_serializes_to_json(self) -> None:
        """It serializes to JSON-compatible format."""
        deprecation = DeprecationEntry(
            provider="Anthropic",
            model="claude-instant-1",
            deprecation_date=datetime(2024, 9, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 12, 1, tzinfo=UTC),
            replacement="claude-3-haiku",
            notes="Upgrading to Claude 3 family",
            source_url="https://docs.anthropic.com/deprecations",
        )

        feed = FeedData(
            deprecations=[deprecation],
            provider_statuses=[],
            last_updated=datetime(2024, 8, 20, 16, 0, 0, tzinfo=UTC),
        )

        json_data = feed.model_dump_json()
        assert isinstance(json_data, str)
        assert "claude-instant-1" in json_data
        assert "Anthropic" in json_data
