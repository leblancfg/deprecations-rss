"""Tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import (
    ErrorHandlingConfig,
    GitHubConfig,
    LoggingConfig,
    NotificationConfig,
    Settings,
    get_settings,
)


class TestLoggingConfig:
    """Test logging configuration."""

    def test_default_values(self):
        """Test default logging configuration values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.log_dir == Path("logs")
        assert config.max_bytes == 10_485_760  # 10MB
        assert config.backup_count == 5

    def test_custom_values(self):
        """Test custom logging configuration values."""
        config = LoggingConfig(
            level="DEBUG",
            format="text",
            log_dir=Path("/var/log/app"),
            max_bytes=5_000_000,
            backup_count=10,
        )
        assert config.level == "DEBUG"
        assert config.format == "text"
        assert config.log_dir == Path("/var/log/app")
        assert config.max_bytes == 5_000_000
        assert config.backup_count == 10


class TestErrorHandlingConfig:
    """Test error handling configuration."""

    def test_default_values(self):
        """Test default error handling configuration values."""
        config = ErrorHandlingConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 60
        assert config.failure_threshold == 3
        assert config.threshold_window_hours == 24
        assert config.recovery_check_interval == 3600

    def test_custom_values(self):
        """Test custom error handling configuration values."""
        config = ErrorHandlingConfig(
            max_retries=5,
            retry_delay=30,
            failure_threshold=5,
            threshold_window_hours=12,
            recovery_check_interval=1800,
        )
        assert config.max_retries == 5
        assert config.retry_delay == 30
        assert config.failure_threshold == 5
        assert config.threshold_window_hours == 12
        assert config.recovery_check_interval == 1800


class TestGitHubConfig:
    """Test GitHub configuration."""

    def test_default_values(self):
        """Test default GitHub configuration values."""
        config = GitHubConfig()
        assert config.token is None
        assert config.repository is None
        assert config.labels == ["bug", "automated"]

    def test_custom_values(self):
        """Test custom GitHub configuration values."""
        config = GitHubConfig(
            token="ghp_test123",
            repository="user/repo",
            labels=["error", "critical"],
        )
        assert config.token == "ghp_test123"
        assert config.repository == "user/repo"
        assert config.labels == ["error", "critical"]

    def test_from_environment(self):
        """Test loading GitHub configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "ghp_env123",
                "GITHUB_REPOSITORY": "env/repo",
            },
        ):
            config = GitHubConfig()
            assert config.token == "ghp_env123"
            assert config.repository == "env/repo"


class TestNotificationConfig:
    """Test notification configuration."""

    def test_default_values(self):
        """Test default notification configuration values."""
        config = NotificationConfig()
        assert config.enabled is True
        assert config.throttle_minutes == 60
        assert config.priority_levels == ["critical", "warning", "info"]
        assert config.channels == ["github"]

    def test_custom_values(self):
        """Test custom notification configuration values."""
        config = NotificationConfig(
            enabled=False,
            throttle_minutes=30,
            priority_levels=["critical"],
            channels=["github", "slack"],
        )
        assert config.enabled is False
        assert config.throttle_minutes == 30
        assert config.priority_levels == ["critical"]
        assert config.channels == ["github", "slack"]


class TestSettings:
    """Test main settings configuration."""

    def test_default_settings(self):
        """Test default settings configuration."""
        settings = Settings()
        assert isinstance(settings.logging, LoggingConfig)
        assert isinstance(settings.error_handling, ErrorHandlingConfig)
        assert isinstance(settings.github, GitHubConfig)
        assert isinstance(settings.notifications, NotificationConfig)

    def test_custom_settings(self):
        """Test custom settings configuration."""
        settings = Settings(
            logging=LoggingConfig(level="DEBUG"),
            error_handling=ErrorHandlingConfig(max_retries=5),
            github=GitHubConfig(token="test"),
            notifications=NotificationConfig(enabled=False),
        )
        assert settings.logging.level == "DEBUG"
        assert settings.error_handling.max_retries == 5
        assert settings.github.token == "test"
        assert settings.notifications.enabled is False

    def test_from_env_file(self, tmp_path):
        """Test loading settings from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            """
LOG_LEVEL=DEBUG
ERROR_MAX_RETRIES=10
GITHUB_TOKEN=ghp_file123
NOTIFICATION_ENABLED=false
"""
        )
        with patch.dict(os.environ, {"ENV_FILE": str(env_file)}):
            settings = Settings()
            assert settings.logging.level == "DEBUG"
            assert settings.error_handling.max_retries == 10
            assert settings.github.token == "ghp_file123"
            assert settings.notifications.enabled is False


class TestGetSettings:
    """Test settings singleton."""

    def test_singleton_pattern(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reset_settings(self):
        """Test resetting the settings singleton."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()
        assert settings1 is not settings2