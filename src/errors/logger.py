"""Structured error logging system."""

import json
import logging
import logging.handlers
import traceback
import uuid
from datetime import UTC, datetime
from enum import Enum
from functools import cache
from typing import Any

from pydantic import BaseModel, Field

from src.config import Settings, get_settings


class ErrorSeverity(Enum):
    """Error severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def to_log_level(self) -> int:
        """Convert severity to Python logging level."""
        mapping = {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }
        return mapping[self]


class ErrorCategory(Enum):
    """Error categories for classification."""

    NETWORK = "network"
    PARSING = "parsing"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PROVIDER = "provider"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class StructuredError(BaseModel):
    """Structured error model for consistent logging."""

    error_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    provider: str | None = None
    url: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    traceback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "provider": self.provider,
            "url": self.url,
            "error_code": self.error_code,
            "metadata": self.metadata,
            "traceback": self.traceback,
        }


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        if hasattr(record, "structured_error"):
            log_data = record.structured_error
        else:
            log_data = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
        return json.dumps(log_data)


class StructuredLogger:
    """Logger for structured error logging."""

    def __init__(self, name: str, config: Settings | None = None) -> None:
        """Initialize structured logger."""
        self.name = name
        self.config = config or get_settings()
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Set up the logger with appropriate handlers."""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.config.logging.level))

        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()

        # Create log directory if it doesn't exist
        log_dir = self.config.logging.log_dir
        log_dir.mkdir(exist_ok=True, parents=True)

        # Set up file handler with rotation
        log_file = log_dir / f"{self.name}.log"
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.config.logging.max_bytes,
            backupCount=self.config.logging.backup_count,
        )

        # Set formatter based on config
        if self.config.logging.format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )

        logger.addHandler(handler)
        return logger

    def log_error(self, error: StructuredError) -> None:
        """Log a structured error."""
        level = error.severity.to_log_level()

        if self.config.logging.format == "json":
            # For JSON format, attach the error dict to the record
            extra = {"structured_error": error.to_dict()}
            self.logger.log(level, error.message, extra=extra)
        else:
            # For text format, format the error as a readable string
            message = (
                f"[{error.severity.value.upper()}] {error.message} | "
                f"Category: {error.category.value}"
            )
            if error.provider:
                message += f" | Provider: {error.provider}"
            if error.url:
                message += f" | URL: {error.url}"
            if error.error_code:
                message += f" | Code: {error.error_code}"
            if error.metadata:
                message += f" | Metadata: {json.dumps(error.metadata)}"

            self.logger.log(level, message)

    def create_error_from_exception(
        self,
        exception: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity | None = None,
        provider: str | None = None,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StructuredError:
        """Create a structured error from an exception."""
        return StructuredError(
            message=str(exception),
            category=category,
            severity=severity or ErrorSeverity.ERROR,
            provider=provider,
            url=url,
            error_code=exception.__class__.__name__,
            metadata=metadata or {},
            traceback=traceback.format_exc(),
        )


@cache
def get_logger(name: str = "deprecations_rss") -> StructuredLogger:
    """Get or create a logger instance."""
    return StructuredLogger(name)
