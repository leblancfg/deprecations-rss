"""Tests for deprecation model."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.deprecation import DeprecationEntry


class DescribeDeprecationEntry:
    """Tests for DeprecationEntry model."""

    def it_creates_valid_entry_with_required_fields(self) -> None:
        """Test creating entry with only required fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://openai.com/blog",
        )

        assert entry.provider == "OpenAI"
        assert entry.model == "gpt-3.5-turbo"
        assert entry.deprecation_date == datetime(2024, 1, 1)
        assert entry.retirement_date == datetime(2024, 6, 1)
        assert entry.replacement is None
        assert entry.notes is None
        assert entry.source_url == "https://openai.com/blog"

    def it_creates_valid_entry_with_all_fields(self) -> None:
        """Test creating entry with all fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement="gpt-4-turbo",
            notes="Model being retired due to newer version availability",
            source_url="https://openai.com/blog/deprecation",
        )

        assert entry.provider == "OpenAI"
        assert entry.model == "gpt-3.5-turbo"
        assert entry.replacement == "gpt-4-turbo"
        assert entry.notes == "Model being retired due to newer version availability"
        assert entry.source_url == "https://openai.com/blog/deprecation"

    def it_validates_retirement_date_after_deprecation(self) -> None:
        """Test that retirement date must be after deprecation date."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-3.5-turbo",
                deprecation_date=datetime(2024, 6, 1),
                retirement_date=datetime(2024, 1, 1),
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Retirement date must be after deprecation date" in errors[0]["msg"]

    def it_validates_retirement_date_not_equal_to_deprecation(self) -> None:
        """Test that retirement date cannot equal deprecation date."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-3.5-turbo",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 1, 1),
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Retirement date must be after deprecation date" in errors[0]["msg"]

    def it_validates_non_empty_provider(self) -> None:
        """Test that provider must be non-empty."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="",
                model="gpt-3.5-turbo",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
            )

        errors = exc_info.value.errors()
        assert any("Field must be a non-empty string" in e["msg"] for e in errors)

    def it_validates_non_empty_model(self) -> None:
        """Test that model must be non-empty."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="OpenAI",
                model="   ",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
            )

        errors = exc_info.value.errors()
        assert any("Field must be a non-empty string" in e["msg"] for e in errors)

    def it_validates_url_format(self) -> None:
        """Test URL validation."""
        with pytest.raises(ValidationError) as exc_info:
            DeprecationEntry(
                provider="OpenAI",
                model="gpt-3.5-turbo",
                deprecation_date=datetime(2024, 1, 1),
                retirement_date=datetime(2024, 6, 1),
                source_url="not-a-url",
            )

        errors = exc_info.value.errors()
        assert any("URL must start with http:// or https://" in e["msg"] for e in errors)

    def it_accepts_valid_urls(self) -> None:
        """Test that valid URLs are accepted."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="https://example.com/deprecation",
        )
        assert entry.source_url == "https://example.com/deprecation"

        entry2 = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            source_url="http://example.com/deprecation",
        )
        assert entry2.source_url == "http://example.com/deprecation"

    def it_strips_whitespace_from_strings(self) -> None:
        """Test that string fields are stripped of whitespace."""
        entry = DeprecationEntry(
            provider="  OpenAI  ",
            model="  gpt-3.5-turbo  ",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
        )

        assert entry.provider == "OpenAI"
        assert entry.model == "gpt-3.5-turbo"


class DescribeDeprecationEntryRSSConversion:
    """Tests for RSS conversion methods."""

    def it_converts_to_rss_item_with_required_fields(self) -> None:
        """Test conversion to RSS item with only required fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1, 12, 0, 0),
            retirement_date=datetime(2024, 6, 1, 12, 0, 0),
        )

        rss_item = entry.to_rss_item()

        assert rss_item["title"] == "OpenAI - gpt-3.5-turbo Deprecation"
        assert "Provider: OpenAI" in rss_item["description"]
        assert "Model: gpt-3.5-turbo" in rss_item["description"]
        assert "Deprecation Date: 2024-01-01T12:00:00" in rss_item["description"]
        assert "Retirement Date: 2024-06-01T12:00:00" in rss_item["description"]
        assert rss_item["link"] == ""
        assert rss_item["guid"] == "OpenAI-gpt-3.5-turbo-2024-01-01T12:00:00"
        assert rss_item["pubDate"] == datetime(2024, 1, 1, 12, 0, 0)

    def it_converts_to_rss_item_with_all_fields(self) -> None:
        """Test conversion to RSS item with all fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement="gpt-4-turbo",
            notes="Upgrade recommended",
            source_url="https://openai.com/blog",
        )

        rss_item = entry.to_rss_item()

        assert "Replacement: gpt-4-turbo" in rss_item["description"]
        assert "Notes: Upgrade recommended" in rss_item["description"]
        assert rss_item["link"] == "https://openai.com/blog"

    def it_generates_unique_guid_for_same_model_different_dates(self) -> None:
        """Test that GUID is unique for same model deprecated at different times."""
        entry1 = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
        )

        entry2 = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 2, 1),
            retirement_date=datetime(2024, 7, 1),
            source_url="https://example.com",
        )

        assert entry1.to_rss_item()["guid"] != entry2.to_rss_item()["guid"]


class DescribeDeprecationEntryJSONConversion:
    """Tests for JSON conversion methods."""

    def it_converts_to_json_dict_with_required_fields(self) -> None:
        """Test conversion to JSON dict with only required fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1, 12, 0, 0),
            retirement_date=datetime(2024, 6, 1, 12, 0, 0),
        )

        json_dict = entry.to_json_dict()

        assert json_dict == {
            "provider": "OpenAI",
            "model": "gpt-3.5-turbo",
            "deprecation_date": "2024-01-01T12:00:00",
            "retirement_date": "2024-06-01T12:00:00",
            "replacement": None,
            "notes": None,
            "source_url": "https://openai.com/blog",
        }

    def it_converts_to_json_dict_with_all_fields(self) -> None:
        """Test conversion to JSON dict with all fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement="gpt-4-turbo",
            notes="Upgrade recommended",
            source_url="https://openai.com/blog",
        )

        json_dict = entry.to_json_dict()

        assert json_dict["replacement"] == "gpt-4-turbo"
        assert json_dict["notes"] == "Upgrade recommended"
        assert json_dict["source_url"] == "https://openai.com/blog"

    def it_produces_serializable_output(self) -> None:
        """Test that JSON dict can be serialized."""
        import json

        entry = DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo",
            deprecation_date=datetime(2024, 1, 1),
            retirement_date=datetime(2024, 6, 1),
            replacement="gpt-4-turbo",
        )

        json_dict = entry.to_json_dict()
        json_str = json.dumps(json_dict)
        parsed = json.loads(json_str)

        assert parsed["provider"] == "OpenAI"
        assert parsed["model"] == "gpt-3.5-turbo"
        assert parsed["replacement"] == "gpt-4-turbo"
