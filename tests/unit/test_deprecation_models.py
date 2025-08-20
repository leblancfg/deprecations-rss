"""Tests for deprecation models."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.models.deprecation import DeprecationEntry
from src.models.feed import DeprecationFeed


def describe_deprecation_entry():
    """Test suite for DeprecationEntry model."""

    def test_creates_entry_with_required_fields():
        """It creates a deprecation entry with only required fields."""
        entry = DeprecationEntry(
            provider="OpenAI",
            model_name="GPT-3",
        )

        assert entry.provider == "OpenAI"
        assert entry.model_name == "GPT-3"
        assert isinstance(entry.id, str)
        assert UUID(entry.id)  # Validates it's a valid UUID
        assert entry.deprecation_date is None
        assert entry.retirement_date is None
        assert entry.replacement is None
        assert entry.notes is None
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)

    def test_creates_entry_with_all_fields():
        """It creates a deprecation entry with all fields."""
        deprecation_date = datetime(2024, 6, 1, tzinfo=UTC)
        retirement_date = datetime(2024, 12, 31, tzinfo=UTC)

        entry = DeprecationEntry(
            provider="Anthropic",
            model_name="Claude-1",
            deprecation_date=deprecation_date,
            retirement_date=retirement_date,
            replacement="Claude-2",
            notes="Significant improvements in Claude-2",
        )

        assert entry.provider == "Anthropic"
        assert entry.model_name == "Claude-1"
        assert entry.deprecation_date == deprecation_date
        assert entry.retirement_date == retirement_date
        assert entry.replacement == "Claude-2"
        assert entry.notes == "Significant improvements in Claude-2"

    def test_validates_required_fields():
        """It raises validation error when required fields are missing."""
        with pytest.raises(ValueError):
            DeprecationEntry()  # type: ignore

        with pytest.raises(ValueError):
            DeprecationEntry(provider="OpenAI")  # type: ignore

        with pytest.raises(ValueError):
            DeprecationEntry(model_name="GPT-3")  # type: ignore

    def describe_to_rss_item():
        """Test RSS item conversion."""

        def test_converts_to_rss_format():
            """It converts deprecation entry to RSS item format."""
            deprecation_date = datetime(2024, 6, 1, tzinfo=UTC)
            retirement_date = datetime(2024, 12, 31, tzinfo=UTC)

            entry = DeprecationEntry(
                provider="OpenAI",
                model_name="GPT-3",
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                replacement="GPT-4",
                notes="Upgrade to GPT-4 for better performance",
            )

            rss_item = entry.to_rss_item()

            assert rss_item["title"] == "OpenAI: GPT-3 Deprecation"
            assert "GPT-3" in rss_item["description"]
            assert "OpenAI" in rss_item["description"]
            assert "GPT-4" in rss_item["description"]
            assert "2024-06-01" in rss_item["description"]
            assert "2024-12-31" in rss_item["description"]
            assert rss_item["guid"] == entry.id
            assert rss_item["pubDate"] == entry.created_at
            assert rss_item["link"] is not None

        def test_handles_missing_optional_fields():
            """It handles RSS conversion when optional fields are missing."""
            entry = DeprecationEntry(
                provider="Google",
                model_name="PaLM",
            )

            rss_item = entry.to_rss_item()

            assert rss_item["title"] == "Google: PaLM Deprecation"
            assert "No deprecation date announced" in rss_item["description"]
            assert "No retirement date announced" in rss_item["description"]
            assert "No replacement specified" in rss_item["description"]

    def describe_from_raw():
        """Test factory method from raw data."""

        def test_creates_from_raw_deprecation_data():
            """It creates entry from raw deprecation data."""
            raw_data = {
                "provider": "OpenAI",
                "model": "text-davinci-003",
                "deprecated_date": "2024-01-04",
                "shutdown_date": "2024-06-04",
                "replacement_model": "gpt-3.5-turbo-instruct",
                "additional_info": "Legacy model being phased out",
            }

            entry = DeprecationEntry.from_raw(raw_data)

            assert entry.provider == "OpenAI"
            assert entry.model_name == "text-davinci-003"
            assert entry.deprecation_date == datetime(2024, 1, 4, tzinfo=UTC)
            assert entry.retirement_date == datetime(2024, 6, 4, tzinfo=UTC)
            assert entry.replacement == "gpt-3.5-turbo-instruct"
            assert entry.notes == "Legacy model being phased out"

        def test_handles_various_date_formats():
            """It handles various date formats in raw data."""
            raw_data = {
                "provider": "Anthropic",
                "model": "Claude-instant-1",
                "deprecated_date": "2024-03-15T10:30:00Z",
                "shutdown_date": "June 30, 2024",
            }

            entry = DeprecationEntry.from_raw(raw_data)

            assert entry.deprecation_date == datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)
            assert entry.retirement_date == datetime(2024, 6, 30, tzinfo=UTC)

    def describe_is_active():
        """Test active status checking."""

        def test_active_when_no_retirement_date():
            """It returns True when no retirement date is set."""
            entry = DeprecationEntry(
                provider="OpenAI",
                model_name="GPT-3",
            )

            assert entry.is_active() is True

        def test_active_when_retirement_date_in_future():
            """It returns True when retirement date is in the future."""
            future_date = datetime.now(UTC) + timedelta(days=30)

            entry = DeprecationEntry(
                provider="OpenAI",
                model_name="GPT-3",
                retirement_date=future_date,
            )

            assert entry.is_active() is True

        def test_inactive_when_retirement_date_passed():
            """It returns False when retirement date has passed."""
            past_date = datetime.now(UTC) - timedelta(days=30)

            entry = DeprecationEntry(
                provider="OpenAI",
                model_name="GPT-3",
                retirement_date=past_date,
            )

            assert entry.is_active() is False

        def test_inactive_when_retirement_date_is_today():
            """It returns False when retirement date is today."""
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

            entry = DeprecationEntry(
                provider="OpenAI",
                model_name="GPT-3",
                retirement_date=today,
            )

            assert entry.is_active() is False


def describe_deprecation_feed():
    """Test suite for DeprecationFeed model."""

    def test_creates_empty_feed():
        """It creates an empty deprecation feed."""
        feed = DeprecationFeed()

        assert feed.entries == []
        assert isinstance(feed.generated_at, datetime)
        assert feed.version == "v1"

    def test_creates_feed_with_entries():
        """It creates a feed with initial entries."""
        entries = [
            DeprecationEntry(provider="OpenAI", model_name="GPT-3"),
            DeprecationEntry(provider="Anthropic", model_name="Claude-1"),
        ]

        feed = DeprecationFeed(entries=entries)

        assert len(feed.entries) == 2
        assert feed.entries[0].model_name == "GPT-3"
        assert feed.entries[1].model_name == "Claude-1"

    def describe_add_entry():
        """Test adding entries to feed."""

        def test_adds_single_entry():
            """It adds a single entry to the feed."""
            feed = DeprecationFeed()
            entry = DeprecationEntry(provider="Google", model_name="PaLM")

            feed.add_entry(entry)

            assert len(feed.entries) == 1
            assert feed.entries[0].model_name == "PaLM"

        def test_adds_multiple_entries():
            """It adds multiple entries to the feed."""
            feed = DeprecationFeed()

            feed.add_entry(DeprecationEntry(provider="OpenAI", model_name="GPT-3"))
            feed.add_entry(DeprecationEntry(provider="Google", model_name="Bard"))

            assert len(feed.entries) == 2

    def describe_get_active_entries():
        """Test filtering active entries."""

        def test_returns_only_active_entries():
            """It returns only active deprecation entries."""
            past_date = datetime.now(UTC) - timedelta(days=30)
            future_date = datetime.now(UTC) + timedelta(days=30)

            entries = [
                DeprecationEntry(provider="OpenAI", model_name="GPT-3", retirement_date=past_date),
                DeprecationEntry(provider="Google", model_name="PaLM", retirement_date=future_date),
                DeprecationEntry(provider="Anthropic", model_name="Claude-2"),
            ]

            feed = DeprecationFeed(entries=entries)
            active = feed.get_active_entries()

            assert len(active) == 2
            assert all(e.model_name in ["PaLM", "Claude-2"] for e in active)

        def test_returns_empty_list_when_no_active():
            """It returns empty list when no entries are active."""
            past_date = datetime.now(UTC) - timedelta(days=30)

            entries = [
                DeprecationEntry(provider="OpenAI", model_name="GPT-2", retirement_date=past_date),
                DeprecationEntry(provider="Google", model_name="LaMDA", retirement_date=past_date),
            ]

            feed = DeprecationFeed(entries=entries)
            active = feed.get_active_entries()

            assert active == []

    def describe_to_rss():
        """Test RSS feed generation."""

        @patch("src.models.feed.FeedGenerator")
        def test_generates_rss_xml(mock_fg_class):
            """It generates RSS XML using feedgen."""
            mock_fg = MagicMock()
            mock_fg_class.return_value = mock_fg
            mock_fg.rss_str.return_value = b"<rss>...</rss>"

            entries = [
                DeprecationEntry(provider="OpenAI", model_name="GPT-3"),
                DeprecationEntry(provider="Google", model_name="PaLM"),
            ]

            feed = DeprecationFeed(entries=entries)
            rss_xml = feed.to_rss()

            assert rss_xml == "<rss>...</rss>"
            mock_fg.title.assert_called_once_with("AI Model Deprecations")
            mock_fg.description.assert_called_once()
            mock_fg.link.assert_called_once()
            assert mock_fg.add_entry.call_count == 2

        @patch("src.models.feed.FeedGenerator")
        def test_includes_feed_metadata(mock_fg_class):
            """It includes proper feed metadata in RSS."""
            mock_fg = MagicMock()
            mock_fg_class.return_value = mock_fg
            mock_fg.rss_str.return_value = b"<rss>...</rss>"

            feed = DeprecationFeed()
            feed.to_rss()

            mock_fg.title.assert_called_with("AI Model Deprecations")
            mock_fg.description.assert_called_with(
                "Track deprecations and retirements of AI models across providers"
            )
            mock_fg.language.assert_called_with("en")

        @patch("src.models.feed.FeedGenerator")
        def test_sorts_entries_by_date(mock_fg_class):
            """It sorts entries by created date in RSS feed."""
            mock_fg = MagicMock()
            mock_fg_class.return_value = mock_fg
            mock_fg.rss_str.return_value = b"<rss>...</rss>"

            old_entry = DeprecationEntry(provider="OpenAI", model_name="GPT-2")
            old_entry.created_at = datetime.now(UTC) - timedelta(days=5)

            new_entry = DeprecationEntry(provider="Google", model_name="PaLM")
            new_entry.created_at = datetime.now(UTC)

            feed = DeprecationFeed(entries=[old_entry, new_entry])
            feed.to_rss()

            # Verify entries are added in reverse chronological order
            calls = mock_fg.add_entry.call_args_list
            assert len(calls) == 2
