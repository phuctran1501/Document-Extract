"""Structured logging configuration with JSON formatting and correlation ID tracking."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings, get_settings
from app.core.correlation import get_correlation_id

STANDARD_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter injecting correlation ID and structured metadata."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).isoformat()
        log_data: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Include custom extra fields if provided
        for key, val in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                log_data[key] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class StructuredTextFormatter(logging.Formatter):
    """Human-readable text log formatter with correlation ID for local development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        correlation_id = get_correlation_id() or "-"
        msg = record.getMessage()

        level = f"{record.levelname:<7}"
        base = f"{timestamp} [{level}] [{correlation_id}] {record.name}: {msg}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(settings: Settings | None = None) -> None:
    """Configure root and framework loggers with structured output."""
    if settings is None:
        settings = get_settings()

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter: logging.Formatter
    if settings.log_json_format:
        formatter = StructuredJsonFormatter()
    else:
        formatter = StructuredTextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Align Uvicorn loggers to use the same output handler
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.handlers.clear()
        u_logger.propagate = True
