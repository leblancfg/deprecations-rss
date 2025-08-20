"""Main notification system interface."""

from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.errors.analyzer import ErrorReport
from src.notifications.github_issues import get_github_creator


class NotificationChannel(Enum):
    """Available notification channels."""

    GITHUB = "github"
    # Future: SLACK = "slack"
    # Future: EMAIL = "email"


class NotificationPriority(Enum):
    """Notification priority levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            NotificationPriority.INFO: 1,
            NotificationPriority.WARNING: 2,
            NotificationPriority.CRITICAL: 3,
        }
        return levels[self]


class NotificationRecord(BaseModel):
    """Record of a sent notification."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    channel: NotificationChannel
    priority: NotificationPriority
    title: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    success: bool | None = None
    error_message: str | None = None

    def mark_success(self) -> None:
        """Mark notification as successful."""
        self.success = True
        self.error_message = None

    def mark_failure(self, error: str) -> None:
        """Mark notification as failed."""
        self.success = False
        self.error_message = error


class Notifier:
    """Main notification system interface."""

    def __init__(self, config: Settings | None = None) -> None:
        """Initialize notifier."""
        self.config = config or get_settings()
        self.channels: dict[NotificationChannel, Any] = {}
        self.notification_history: list[NotificationRecord] = []
        self._last_notification_times: dict[tuple[NotificationChannel, str], datetime] = {}

        # Initialize available channels
        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize notification channels based on configuration."""
        if "github" in self.config.notifications.channels:
            github_creator = get_github_creator()
            if github_creator:
                self.channels[NotificationChannel.GITHUB] = github_creator

    def _is_throttled(self, channel: NotificationChannel, title: str) -> bool:
        """Check if notification should be throttled."""
        key = (channel, title)
        if key not in self._last_notification_times:
            return False

        last_time = self._last_notification_times[key]
        throttle_delta = timedelta(minutes=self.config.notifications.throttle_minutes)

        return datetime.now(UTC) - last_time < throttle_delta

    def _should_notify(self, priority: NotificationPriority) -> bool:
        """Check if notification should be sent based on priority."""
        if not self.config.notifications.enabled:
            return False

        allowed_priorities = self.config.notifications.priority_levels
        return priority.value in allowed_priorities

    async def notify(
        self,
        channel: NotificationChannel,
        priority: NotificationPriority,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification through the specified channel."""
        # Check if notifications are enabled
        if not self._should_notify(priority):
            return False

        # Check throttling
        if self._is_throttled(channel, title):
            return False

        # Check if channel is available
        if channel not in self.channels:
            return False

        # Create notification record
        record = NotificationRecord(
            channel=channel,
            priority=priority,
            title=title,
            message=message,
            metadata=metadata or {},
        )

        # Send notification based on channel
        try:
            if channel == NotificationChannel.GITHUB:
                # GitHub notifications are handled through specific methods
                # This is a generic fallback
                record.mark_success()

            # Update throttling
            self._last_notification_times[(channel, title)] = datetime.now(UTC)

            # Add to history
            self.notification_history.append(record)

            return record.success or False

        except Exception as e:
            record.mark_failure(str(e))
            self.notification_history.append(record)
            return False

    async def notify_error_report(self, report: ErrorReport) -> bool:
        """Send notification for an error report."""
        if NotificationChannel.GITHUB not in self.channels:
            return False

        github_creator = self.channels[NotificationChannel.GITHUB]

        # Determine priority based on critical issues
        priority = (
            NotificationPriority.CRITICAL
            if report.critical_issues
            else NotificationPriority.WARNING
        )

        # Check if should notify
        if not self._should_notify(priority):
            return False

        # Generate title
        if report.critical_issues:
            title = f"Critical: {report.critical_issues[0][:50]}"
        else:
            title = f"Error Report: {report.stats.total_count} errors"

        # Check throttling
        if self._is_throttled(NotificationChannel.GITHUB, title):
            return False

        # Create notification record
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=priority,
            title=title,
            message=f"Error report with {report.stats.total_count} errors",
            metadata={"report_id": report.report_id},
        )

        try:
            # Create GitHub issue
            result = await github_creator.create_issue_from_report(report)
            if result:
                record.mark_success()
                record.metadata["issue_number"] = result.get("number")
                record.metadata["issue_url"] = result.get("html_url")
            else:
                record.mark_failure("Failed to create issue or duplicate detected")

            # Update throttling
            self._last_notification_times[(NotificationChannel.GITHUB, title)] = datetime.now(UTC)

        except Exception as e:
            record.mark_failure(str(e))

        self.notification_history.append(record)
        return record.success or False

    async def notify_provider_failure(
        self,
        provider: str,
        error_count: int,
        error_messages: list[str],
        urls: list[str],
    ) -> bool:
        """Send notification for provider failure."""
        if NotificationChannel.GITHUB not in self.channels:
            return False

        github_creator = self.channels[NotificationChannel.GITHUB]

        priority = NotificationPriority.CRITICAL
        title = f"Provider Failure: {provider}"

        # Check if should notify
        if not self._should_notify(priority):
            return False

        # Check throttling
        if self._is_throttled(NotificationChannel.GITHUB, title):
            return False

        # Create notification record
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=priority,
            title=title,
            message=f"{error_count} errors detected for {provider}",
            metadata={"provider": provider, "error_count": error_count},
        )

        try:
            # Create GitHub issue
            result = await github_creator.create_provider_failure_issue(
                provider=provider,
                error_count=error_count,
                error_messages=error_messages,
                urls=urls,
            )
            if result:
                record.mark_success()
                record.metadata["issue_number"] = result.get("number")
                record.metadata["issue_url"] = result.get("html_url")
            else:
                record.mark_failure("Failed to create issue or duplicate detected")

            # Update throttling
            self._last_notification_times[(NotificationChannel.GITHUB, title)] = datetime.now(UTC)

        except Exception as e:
            record.mark_failure(str(e))

        self.notification_history.append(record)
        return record.success or False

    async def notify_url_change(
        self,
        provider: str,
        old_url: str,
        suggested_url: str | None,
        error_message: str,
    ) -> bool:
        """Send notification for URL change detection."""
        if NotificationChannel.GITHUB not in self.channels:
            return False

        github_creator = self.channels[NotificationChannel.GITHUB]

        priority = NotificationPriority.WARNING
        title = f"URL Change: {provider}"

        # Check if should notify
        if not self._should_notify(priority):
            return False

        # Check throttling
        if self._is_throttled(NotificationChannel.GITHUB, title):
            return False

        # Create notification record
        record = NotificationRecord(
            channel=NotificationChannel.GITHUB,
            priority=priority,
            title=title,
            message=f"URL change detected for {provider}",
            metadata={"provider": provider, "old_url": old_url},
        )

        try:
            # Create GitHub issue
            result = await github_creator.create_url_change_issue(
                provider=provider,
                old_url=old_url,
                suggested_url=suggested_url,
                error_message=error_message,
            )
            if result:
                record.mark_success()
                record.metadata["issue_number"] = result.get("number")
                record.metadata["issue_url"] = result.get("html_url")
            else:
                record.mark_failure("Failed to create issue or duplicate detected")

            # Update throttling
            self._last_notification_times[(NotificationChannel.GITHUB, title)] = datetime.now(UTC)

        except Exception as e:
            record.mark_failure(str(e))

        self.notification_history.append(record)
        return record.success or False

    def get_recent_notifications(self, hours: int = 24) -> list[NotificationRecord]:
        """Get notifications from the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return [n for n in self.notification_history if n.timestamp >= cutoff]

    def clear_old_notifications(self, days: int = 7) -> None:
        """Clear notifications older than specified days."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        self.notification_history = [
            n for n in self.notification_history if n.timestamp >= cutoff
        ]


@lru_cache(maxsize=1)
def get_notifier() -> Notifier:
    """Get the singleton notifier instance."""
    return Notifier()
