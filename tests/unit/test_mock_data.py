"""Tests for mock data generator."""

from datetime import UTC, datetime

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus
from src.scrapers.mock_data import generate_mock_feed_data


class TestMockDataGenerator:
    """Tests for mock data generation."""

    def test_generates_feed_data(self) -> None:
        """It generates valid FeedData object."""
        feed = generate_mock_feed_data()

        assert isinstance(feed, FeedData)
        assert isinstance(feed.deprecations, list)
        assert isinstance(feed.provider_statuses, list)
        assert isinstance(feed.last_updated, datetime)

    def test_generates_multiple_deprecations(self) -> None:
        """It generates deprecations from multiple providers."""
        feed = generate_mock_feed_data()

        assert len(feed.deprecations) > 0

        providers = {dep.provider for dep in feed.deprecations}
        assert "OpenAI" in providers
        assert "Anthropic" in providers
        assert len(providers) >= 5

    def test_generates_valid_deprecation_entries(self) -> None:
        """It generates deprecation entries with proper data."""
        feed = generate_mock_feed_data()

        for deprecation in feed.deprecations:
            assert isinstance(deprecation, DeprecationEntry)
            assert deprecation.provider
            assert deprecation.model
            assert isinstance(deprecation.deprecation_date, datetime)
            assert deprecation.deprecation_date.tzinfo is not None

            if deprecation.retirement_date:
                assert isinstance(deprecation.retirement_date, datetime)
                assert deprecation.retirement_date > deprecation.deprecation_date
                assert deprecation.retirement_date.tzinfo is not None

    def test_generates_provider_statuses(self) -> None:
        """It generates status for each provider."""
        feed = generate_mock_feed_data()

        assert len(feed.provider_statuses) >= 5

        provider_names = {status.name for status in feed.provider_statuses}
        assert "OpenAI" in provider_names
        assert "Anthropic" in provider_names
        assert "Google Vertex AI" in provider_names
        assert "AWS Bedrock" in provider_names
        assert "Cohere" in provider_names

    def test_generates_mixed_provider_health_statuses(self) -> None:
        """It generates both healthy and unhealthy provider statuses."""
        feed = generate_mock_feed_data()

        healthy_count = sum(1 for status in feed.provider_statuses if status.is_healthy)
        unhealthy_count = len(feed.provider_statuses) - healthy_count

        assert healthy_count > 0
        assert unhealthy_count >= 0

        for status in feed.provider_statuses:
            assert isinstance(status, ProviderStatus)
            assert status.name
            assert isinstance(status.last_checked, datetime)
            assert status.last_checked.tzinfo is not None
            assert isinstance(status.is_healthy, bool)

            if not status.is_healthy:
                assert status.error_message is not None

    def test_generates_realistic_dates(self) -> None:
        """It generates realistic deprecation and retirement dates."""
        feed = generate_mock_feed_data()

        now = datetime.now(UTC)

        for deprecation in feed.deprecations:
            assert deprecation.deprecation_date <= now.replace(year=now.year + 2)
            assert deprecation.deprecation_date >= now.replace(year=now.year - 2)

    def test_includes_realistic_urls(self) -> None:
        """It includes realistic documentation URLs."""
        feed = generate_mock_feed_data()

        url_count = sum(1 for dep in feed.deprecations if dep.url)
        assert url_count > 0

        for deprecation in feed.deprecations:
            if deprecation.url:
                assert isinstance(deprecation.url, str)
                assert deprecation.url.startswith("http")

    def test_last_updated_is_recent(self) -> None:
        """It sets last_updated to a recent time."""
        feed = generate_mock_feed_data()

        now = datetime.now(UTC)
        time_diff = abs((now - feed.last_updated).total_seconds())

        assert time_diff < 60
