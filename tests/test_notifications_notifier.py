"""Tests for notification system interface."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.errors.analyzer import ErrorReport, ErrorStats
from src.notifications.notifier import (
    NotificationChannel,
    NotificationPriority,
    NotificationRecord,
    Notifier,
    get_notifier,
)


class TestNotificationPriority:
    """Test notification priority enum."""

    def test_priority_levels(self):
        """Test priority level values."""
        assert NotificationPriority.INFO.value == "info"
        assert NotificationPriority.WARNING.value == "warning"
        assert NotificationPriority.CRITICAL.value == "critical"

    def test_priority_comparison(self):
        """Test priority level comparison."""
        assert NotificationPriority.CRITICAL.level() > NotificationPriority.WARNING.level()
        assert NotificationPriority.WARNING.level() > NotificationPriority.INFO.level()


class TestNotificationRecord:
    """Test notification record model."""

    def test_record_creation(self):
        """Test creating a notification record."""
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=NotificationPriority.CRITICAL,
            title="Test Notification",
            message="Test message",
            metadata={"test": "data"},
        )
        assert record.channel == NotificationChannel.GITHUB
        assert record.priority == NotificationPriority.CRITICAL
        assert record.title == "Test Notification"
        assert record.message == "Test message"
        assert record.metadata == {"test": "data"}
        assert isinstance(record.timestamp, datetime)
        assert record.success is None
        assert record.error_message is None

    def test_mark_success(self):
        """Test marking notification as successful."""
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=NotificationPriority.INFO,
            title="Test",
            message="Test",
        )
        record.mark_success()
        assert record.success is True
        assert record.error_message is None

    def test_mark_failure(self):
        """Test marking notification as failed."""
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=NotificationPriority.INFO,
            title="Test",
            message="Test",
        )
        record.mark_failure("Connection error")
        assert record.success is False
        assert record.error_message == "Connection error"


class TestNotifier:
    """Test main notifier class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.notifications.enabled = True
        config.notifications.throttle_minutes = 60
        config.notifications.priority_levels = ["critical", "warning", "info"]
        config.notifications.channels = ["github"]
        config.github.token = "ghp_test"
        config.github.repository = "user/repo"
        return config

    @pytest.fixture
    def mock_github_creator(self):
        """Create mock GitHub creator."""
        creator = MagicMock()
        creator.create_issue_from_report = AsyncMock(return_value={"number": 123})
        creator.create_provider_failure_issue = AsyncMock(return_value={"number": 124})
        creator.create_url_change_issue = AsyncMock(return_value={"number": 125})
        return creator

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config, mock_github_creator):
        """Test notifier initialization."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            assert notifier.config == mock_config
            assert NotificationChannel.GITHUB in notifier.channels
            assert notifier.channels[NotificationChannel.GITHUB] == mock_github_creator
            assert notifier.notification_history == []
            assert notifier._last_notification_times == {}

    @pytest.mark.asyncio
    async def test_notify_disabled(self, mock_config):
        """Test notification when disabled."""
        mock_config.notifications.enabled = False
        notifier = Notifier(config=mock_config)
        
        result = await notifier.notify(
            channel=NotificationChannel.GITHUB,
            priority=NotificationPriority.CRITICAL,
            title="Test",
            message="Test message",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_notify_throttled(self, mock_config, mock_github_creator):
        """Test notification throttling."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            # Set last notification time to recent
            key = (NotificationChannel.GITHUB, "Test")
            notifier._last_notification_times[key] = datetime.now(UTC) - timedelta(minutes=30)
            
            result = await notifier.notify(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,
                title="Test",
                message="Test message",
            )
            assert result is False  # Should be throttled

    @pytest.mark.asyncio
    async def test_notify_priority_filtered(self, mock_config, mock_github_creator):
        """Test notification priority filtering."""
        mock_config.notifications.priority_levels = ["critical", "warning"]
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            result = await notifier.notify(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,  # Below threshold
                title="Test",
                message="Test message",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_notify_error_report_success(self, mock_config, mock_github_creator):
        """Test successful error report notification."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            report = ErrorReport(
                report_id="test_report",
                generated_at=datetime.now(UTC),
                time_window_hours=24,
                stats=ErrorStats(total_count=10),
                patterns=[],
                critical_issues=["High error rate"],
                recommendations=["Check API"],
            )
            
            result = await notifier.notify_error_report(report)
            assert result is True
            mock_github_creator.create_issue_from_report.assert_called_once_with(report)
            assert len(notifier.notification_history) == 1
            assert notifier.notification_history[0].success is True

    @pytest.mark.asyncio
    async def test_notify_provider_failure(self, mock_config, mock_github_creator):
        """Test provider failure notification."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            result = await notifier.notify_provider_failure(
                provider="openai",
                error_count=5,
                error_messages=["Timeout", "Connection error"],
                urls=["https://api.openai.com"],
            )
            assert result is True
            mock_github_creator.create_provider_failure_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_url_change(self, mock_config, mock_github_creator):
        """Test URL change notification."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            result = await notifier.notify_url_change(
                provider="anthropic",
                old_url="https://old.api.com",
                suggested_url="https://new.api.com",
                error_message="404 Not Found",
            )
            assert result is True
            mock_github_creator.create_url_change_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent_notifications(self, mock_config, mock_github_creator):
        """Test getting recent notifications."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            # Add old and recent notifications
            old_record = NotificationRecord(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,
                title="Old",
                message="Old message",
                timestamp=datetime.now(UTC) - timedelta(hours=25),
            )
            recent_record = NotificationRecord(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,
                title="Recent",
                message="Recent message",
            )
            
            notifier.notification_history.append(old_record)
            notifier.notification_history.append(recent_record)
            
            recent = notifier.get_recent_notifications(hours=24)
            assert len(recent) == 1
            assert recent[0].title == "Recent"

    @pytest.mark.asyncio
    async def test_clear_old_notifications(self, mock_config, mock_github_creator):
        """Test clearing old notifications."""
        with patch("src.notifications.notifier.get_github_creator", return_value=mock_github_creator):
            notifier = Notifier(config=mock_config)
            
            # Add old and recent notifications
            old_record = NotificationRecord(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,
                title="Old",
                message="Old message",
                timestamp=datetime.now(UTC) - timedelta(days=8),
            )
            recent_record = NotificationRecord(
                channel=NotificationChannel.GITHUB,
                priority=NotificationPriority.INFO,
                title="Recent",
                message="Recent message",
            )
            
            notifier.notification_history.append(old_record)
            notifier.notification_history.append(recent_record)
            
            notifier.clear_old_notifications(days=7)
            assert len(notifier.notification_history) == 1
            assert notifier.notification_history[0].title == "Recent"


class TestGetNotifier:
    """Test notifier singleton."""

    def test_singleton_pattern(self):
        """Test that get_notifier returns the same instance."""
        notifier1 = get_notifier()
        notifier2 = get_notifier()
        assert notifier1 is notifier2