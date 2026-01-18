# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Uvicorn logging configuration for structured JSON logs.

This module provides a logging configuration for Uvicorn that integrates
with the copilot_logging structured JSON logging system.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""

    def __init__(self, logger_name: str = "uvicorn"):
        """Initialize JSON formatter.

        Args:
            logger_name: Name to use in the logger field of JSON output
        """
        super().__init__()
        self.logger_name = logger_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        # Use record.created for accurate event timestamp
        event_time = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_entry: dict[str, Any] = {
            "timestamp": event_time.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": self.logger_name,
            "message": record.getMessage(),
        }

        # Add extra fields from record.__dict__ if present
        # Standard LogRecord attributes to exclude
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
            "getMessage",
            "taskName",
        }

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_attrs and not key.startswith("_")
        }

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


def create_uvicorn_log_config(service_name: str, log_level: str = "INFO") -> dict[str, Any]:
    """Create Uvicorn logging configuration with structured JSON output.

    This configuration:
    - Uses structured JSON logging for all Uvicorn logs
    - Suppresses access logs (INFO level) to reduce noise (health checks, normal requests)
    - Only logs uvicorn errors at the configured log_level
    - Integrates with copilot_logging format

    Args:
        service_name: Name of the service for log identification
        log_level: Default log level for errors (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Dictionary compatible with Uvicorn's log_config parameter

    Example:
        >>> from copilot_logging import create_uvicorn_log_config
        >>> import uvicorn
        >>>
        >>> log_config = create_uvicorn_log_config("parsing", "INFO")
        >>> uvicorn.run(app, host="0.0.0.0", port=8000, log_config=log_config)
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
                "logger_name": service_name,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "WARNING",  # Suppress INFO and DEBUG access logs (health checks, normal requests)
                "propagate": False,
            },
        },
    }
