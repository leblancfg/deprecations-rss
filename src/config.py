"""Configuration management for error handling and notifications."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Log format (json or text)")
    log_dir: Path = Field(default=Path("logs"), description="Directory for log files")
    max_bytes: int = Field(default=10_485_760, description="Max size of log file in bytes")
    backup_count: int = Field(default=5, description="Number of backup log files to keep")

    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable overrides."""
        data["level"] = os.environ.get("LOG_LEVEL", data.get("level", "INFO"))
        data["format"] = os.environ.get("LOG_FORMAT", data.get("format", "json"))
        if log_dir := os.environ.get("LOG_DIR"):
            data["log_dir"] = Path(log_dir)
        if max_bytes := os.environ.get("LOG_MAX_BYTES"):
            data["max_bytes"] = int(max_bytes)
        if backup_count := os.environ.get("LOG_BACKUP_COUNT"):
            data["backup_count"] = int(backup_count)
        super().__init__(**data)


class ErrorHandlingConfig(BaseModel):
    """Error handling configuration."""

    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    retry_delay: int = Field(default=60, description="Delay between retries in seconds")
    failure_threshold: int = Field(
        default=3, description="Number of failures before triggering notification"
    )
    threshold_window_hours: int = Field(
        default=24, description="Time window for counting failures in hours"
    )
    recovery_check_interval: int = Field(
        default=3600, description="Interval between recovery checks in seconds"
    )

    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable overrides."""
        if max_retries := os.environ.get("ERROR_MAX_RETRIES"):
            data["max_retries"] = int(max_retries)
        if retry_delay := os.environ.get("ERROR_RETRY_DELAY"):
            data["retry_delay"] = int(retry_delay)
        if failure_threshold := os.environ.get("ERROR_FAILURE_THRESHOLD"):
            data["failure_threshold"] = int(failure_threshold)
        if threshold_window := os.environ.get("ERROR_THRESHOLD_WINDOW_HOURS"):
            data["threshold_window_hours"] = int(threshold_window)
        if recovery_interval := os.environ.get("ERROR_RECOVERY_CHECK_INTERVAL"):
            data["recovery_check_interval"] = int(recovery_interval)
        super().__init__(**data)


class GitHubConfig(BaseModel):
    """GitHub configuration for issue creation."""

    token: str | None = Field(default=None, description="GitHub API token")
    repository: str | None = Field(default=None, description="Repository name (owner/repo)")
    labels: list[str] = Field(
        default_factory=lambda: ["bug", "automated"], description="Labels for created issues"
    )

    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable overrides."""
        data["token"] = os.environ.get("GITHUB_TOKEN", data.get("token"))
        data["repository"] = os.environ.get("GITHUB_REPOSITORY", data.get("repository"))
        if labels := os.environ.get("GITHUB_LABELS"):
            data["labels"] = [label.strip() for label in labels.split(",")]
        super().__init__(**data)


class NotificationConfig(BaseModel):
    """Notification configuration."""

    enabled: bool = Field(default=True, description="Whether notifications are enabled")
    throttle_minutes: int = Field(
        default=60, description="Minimum time between notifications in minutes"
    )
    priority_levels: list[str] = Field(
        default_factory=lambda: ["critical", "warning", "info"],
        description="Notification priority levels",
    )
    channels: list[str] = Field(
        default_factory=lambda: ["github"], description="Notification channels to use"
    )

    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable overrides."""
        if enabled := os.environ.get("NOTIFICATION_ENABLED"):
            data["enabled"] = enabled.lower() in ("true", "1", "yes")
        if throttle := os.environ.get("NOTIFICATION_THROTTLE_MINUTES"):
            data["throttle_minutes"] = int(throttle)
        if priority_levels := os.environ.get("NOTIFICATION_PRIORITY_LEVELS"):
            data["priority_levels"] = [level.strip() for level in priority_levels.split(",")]
        if channels := os.environ.get("NOTIFICATION_CHANNELS"):
            data["channels"] = [channel.strip() for channel in channels.split(",")]
        super().__init__(**data)


class Settings(BaseModel):
    """Main application settings."""

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    def __init__(self, **data: Any) -> None:
        """Initialize settings, optionally loading from .env file."""
        if env_file := os.environ.get("ENV_FILE"):
            self._load_env_file(Path(env_file))
        super().__init__(**data)

    def _load_env_file(self, env_file: Path) -> None:
        """Load environment variables from .env file."""
        if not env_file.exists():
            return

        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton settings instance."""
    return Settings()
