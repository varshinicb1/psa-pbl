"""
Centralized structured logging configuration for the Grid Digital Twin.

Provides JSON-formatted logging with correlation IDs for production observability.
"""

import json
import logging
import logging.handlers
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Optional

# Context variable for correlation ID (for tracing requests/operations)
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": _correlation_id.get(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__

        # Add custom fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    return logger


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console: bool = True,
) -> None:
    """
    Configure root logger with JSON formatting.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to write logs to file
        console: If True, also write to console (stderr)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers = []

    formatter = JSONFormatter()

    # Console handler (stderr)
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=100 * 1024 * 1024, backupCount=5  # 100MB per file, keep 5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for request tracing.

    Args:
        correlation_id: Correlation ID (generated if None)

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_id.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return _correlation_id.get()


def log_with_context(logger: logging.Logger, level: str, message: str, **extra: Any) -> None:
    """
    Log message with additional context fields.

    Args:
        logger: Logger instance
        level: Log level (info, warning, error, debug, critical)
        message: Log message
        **extra: Additional fields to include in JSON log
    """
    record = logging.LogRecord(
        name=logger.name,
        level=getattr(logging, level.upper()),
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.extra_fields = extra
    logger.handle(record)
