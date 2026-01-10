# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Stdout logger implementation with structured JSON output."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from copilot_config import DriverConfig

from .logger import Logger


class StdoutLogger(Logger):
    """Logger that outputs structured JSON logs to stdout."""

    def __init__(self, level: str = "INFO", name: str | None = None):
        """Initialize stdout logger.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            name: Optional logger name for identification
        """
        self.level = level.upper()
        self.name = name or "copilot"

        # Map string levels to Python logging levels
        self._level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }

        # Validate level
        if self.level not in self._level_map:
            raise ValueError(f"Invalid log level: {level}. Must be one of {list(self._level_map.keys())}")

        # Configure a stdlib logger so caplog and handlers can capture records
        self._stdlib_logger = logging.getLogger(self.name)
        # Use NOTSET to inherit the root level; filtering happens in _log using self.level
        self._stdlib_logger.setLevel(logging.NOTSET)

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "StdoutLogger":
        """Create a StdoutLogger from driver configuration.
        
        Args:
            driver_config: DriverConfig with level and name attributes.
                          Defaults are provided by the schema.
        
        Returns:
            Configured StdoutLogger instance
        
        Raises:
            TypeError: If driver_config is not a DriverConfig instance
        """
        # Required field with schema default
        level = driver_config.level
        
        # Optional field
        name = driver_config.name
        
        return cls(level=level, name=name)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal method to format and output log message.

        Args:
            level: Log level
            message: The log message
            **kwargs: Additional structured data to log
        """
        # Check if we should log at this level for stdout output
        if self._level_map[level] < self._level_map[self.level]:
            return

        # Extract exc_info (bool or tuple) to pass correctly to stdlib logger
        exc_info = kwargs.pop("exc_info", None)

        # Build structured log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "logger": self.name,
            "message": message,
        }

        # Add any extra fields
        if kwargs:
            log_entry["extra"] = kwargs

        # Output as JSON
        try:
            json_output = json.dumps(log_entry, default=str)
            print(json_output, file=sys.stdout, flush=True)
        except Exception as e:
            # Fallback to plain text if JSON serialization fails
            print(f"{level}: {message} (JSON serialization failed: {e})", file=sys.stderr, flush=True)

        # Also emit via stdlib logging so test harnesses (caplog) can capture
        extra = {"extra": kwargs} if kwargs else None
        self._stdlib_logger.log(self._level_map[level], message, exc_info=exc_info, extra=extra)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        self._log("ERROR", message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message with exception context."""
        kwargs.setdefault("exc_info", True)
        self._log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        self._log("DEBUG", message, **kwargs)
