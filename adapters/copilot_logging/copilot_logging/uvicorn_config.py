# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Uvicorn logging configuration for structured JSON logs.

This module provides a logging configuration for Uvicorn that integrates
with the copilot_logging structured JSON logging system.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict


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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": self.logger_name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra') and record.extra:
            log_entry["extra"] = record.extra
        
        return json.dumps(log_entry, default=str)


def create_uvicorn_log_config(service_name: str, log_level: str = "INFO") -> Dict[str, Any]:
    """Create Uvicorn logging configuration with structured JSON output.
    
    This configuration:
    - Uses structured JSON logging for all Uvicorn logs
    - Sets access logs to DEBUG level to reduce noise
    - Uses INFO level for error logs
    - Integrates with copilot_logging format
    
    Args:
        service_name: Name of the service for log identification
        log_level: Default log level (DEBUG, INFO, WARNING, ERROR)
        
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
                "level": "DEBUG",  # Health checks at DEBUG level
                "propagate": False,
            },
        },
    }
