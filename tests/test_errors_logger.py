"""Tests for structured error logging."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.errors.logger import (
    ErrorCategory,
    ErrorSeverity,
    StructuredError,
    StructuredLogger,
    get_logger,
)


class TestErrorSeverity:
    """Test error severity enum."""

    def test_severity_levels(self):
        """Test that severity levels are defined correctly."""
        assert ErrorSeverity.DEBUG.value == "debug"
        assert ErrorSeverity.INFO.value == "info"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_severity_to_log_level(self):
        """Test mapping severity to Python log levels."""
        assert ErrorSeverity.DEBUG.to_log_level() == logging.DEBUG
        assert ErrorSeverity.INFO.to_log_level() == logging.INFO
        assert ErrorSeverity.WARNING.to_log_level() == logging.WARNING
        assert ErrorSeverity.ERROR.to_log_level() == logging.ERROR
        assert ErrorSeverity.CRITICAL.to_log_level() == logging.CRITICAL


class TestErrorCategory:
    """Test error category enum."""

    def test_categories(self):
        """Test that error categories are defined correctly."""
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.PARSING.value == "parsing"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.PROVIDER.value == "provider"
        assert ErrorCategory.SYSTEM.value == "system"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestStructuredError:
    """Test structured error model."""

    def test_create_basic_error(self):
        """Test creating a basic structured error."""
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
        )
        assert error.message == "Test error"
        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.ERROR
        assert error.provider is None
        assert error.url is None
        assert error.error_code is None
        assert error.metadata == {}
        assert error.traceback is None

    def test_create_full_error(self):
        """Test creating a structured error with all fields."""
        error = StructuredError(
            message="API request failed",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.CRITICAL,
            provider="openai",
            url="https://api.openai.com/v1/models",
            error_code="TIMEOUT",
            metadata={"retry_count": 3, "response_time": 30.5},
            traceback="Traceback (most recent call last):\n...",
        )
        assert error.provider == "openai"
        assert error.url == "https://api.openai.com/v1/models"
        assert error.error_code == "TIMEOUT"
        assert error.metadata == {"retry_count": 3, "response_time": 30.5}
        assert error.traceback == "Traceback (most recent call last):\n..."

    def test_to_dict(self):
        """Test converting structured error to dictionary."""
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.WARNING,
            provider="anthropic",
            metadata={"line": 42},
        )
        error_dict = error.to_dict()
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "parsing"
        assert error_dict["severity"] == "warning"
        assert error_dict["provider"] == "anthropic"
        assert error_dict["metadata"] == {"line": 42}
        assert "timestamp" in error_dict
        assert "error_id" in error_dict


class TestStructuredLogger:
    """Test structured logger."""

    @pytest.fixture
    def temp_log_dir(self, tmp_path):
        """Create a temporary log directory."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        return log_dir

    @pytest.fixture
    def mock_config(self, temp_log_dir):
        """Create a mock configuration."""
        config = MagicMock()
        config.logging.log_dir = temp_log_dir
        config.logging.format = "json"
        config.logging.level = "INFO"
        config.logging.max_bytes = 10485760
        config.logging.backup_count = 5
        return config

    def test_initialization(self, mock_config):
        """Test logger initialization."""
        logger = StructuredLogger(name="test", config=mock_config)
        assert logger.name == "test"
        assert logger.config == mock_config
        assert isinstance(logger.logger, logging.Logger)

    def test_log_error_json_format(self, mock_config, temp_log_dir):
        """Test logging error in JSON format."""
        logger = StructuredLogger(name="test", config=mock_config)
        
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
        )
        
        logger.log_error(error)
        
        # Check that log file was created
        log_files = list(temp_log_dir.glob("*.log"))
        assert len(log_files) > 0
        
        # Read and parse the log entry
        with open(log_files[0]) as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            assert log_data["message"] == "Test error"
            assert log_data["category"] == "network"
            assert log_data["severity"] == "error"

    def test_log_error_text_format(self, mock_config, temp_log_dir):
        """Test logging error in text format."""
        mock_config.logging.format = "text"
        logger = StructuredLogger(name="test", config=mock_config)
        
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.WARNING,
        )
        
        logger.log_error(error)
        
        # Check that log file was created
        log_files = list(temp_log_dir.glob("*.log"))
        assert len(log_files) > 0
        
        # Read the log entry
        with open(log_files[0]) as f:
            log_content = f.read()
            assert "Test error" in log_content
            assert "parsing" in log_content.lower()

    def test_log_error_with_exception(self, mock_config):
        """Test logging error with exception details."""
        logger = StructuredLogger(name="test", config=mock_config)
        
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            error = logger.create_error_from_exception(
                e,
                category=ErrorCategory.VALIDATION,
                provider="test_provider",
            )
            assert error.message == "Test exception"
            assert error.category == ErrorCategory.VALIDATION
            assert error.provider == "test_provider"
            assert error.traceback is not None
            assert "ValueError: Test exception" in error.traceback

    def test_log_levels(self, mock_config):
        """Test different log levels."""
        logger = StructuredLogger(name="test", config=mock_config)
        
        # Test debug (should not be logged with INFO level)
        debug_error = StructuredError(
            message="Debug message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.DEBUG,
        )
        logger.log_error(debug_error)
        
        # Test info
        info_error = StructuredError(
            message="Info message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.INFO,
        )
        logger.log_error(info_error)
        
        # Test critical
        critical_error = StructuredError(
            message="Critical message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
        )
        logger.log_error(critical_error)


class TestGetLogger:
    """Test logger factory function."""

    def test_singleton_pattern(self):
        """Test that get_logger returns the same instance for the same name."""
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")
        assert logger1 is logger2

    def test_different_names(self):
        """Test that different names return different logger instances."""
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")
        assert logger1 is not logger2

    def test_default_name(self):
        """Test default logger name."""
        logger = get_logger()
        assert logger.name == "deprecations_rss"