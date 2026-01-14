# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Silent logger implementation for testing."""

from typing import Any, cast

from copilot_config.generated.adapters.logger import DriverConfig_Logger_Silent

from .logger import Logger


class SilentLogger(Logger):
    """Logger that stores log messages in memory without output.

    Useful for testing to verify logging behavior without cluttering test output.
    Note: SilentLogger does not filter logs by level - all logs are captured for testing.
    """

    def __init__(self, level: str = "INFO", name: str | None = None):
        """Initialize silent logger.

        Args:
            level: Logging level (stored but not used for filtering in silent mode)
            name: Optional logger name for identification
        """
        self.level = level.upper()
        self.name = name or "copilot"
        self.logs: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, driver_config: DriverConfig_Logger_Silent) -> "SilentLogger":
        """Create a SilentLogger from driver configuration.

        Args:
            driver_config: DriverConfig with level and name attributes.
                          Defaults are provided by the schema.

        Returns:
            Configured SilentLogger instance

        Raises:
            TypeError: If driver_config is not a DriverConfig instance
        """
        level = cast(str, driver_config.level)
        return cls(level=level, name=driver_config.name)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal method to store log message.

        Args:
            level: Log level
            message: The log message
            **kwargs: Additional structured data to log
        """
        log_entry: dict[str, Any] = {
            "level": level,
            "message": message,
        }

        if kwargs:
            log_entry["extra"] = kwargs

        self.logs.append(log_entry)

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

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        self._log("DEBUG", message, **kwargs)

    def clear_logs(self) -> None:
        """Clear all stored log messages (useful for testing)."""
        self.logs.clear()

    def get_logs(self, level: str | None = None) -> list[dict[str, Any]]:
        """Get stored log messages, optionally filtered by level.

        Args:
            level: Optional log level to filter by (DEBUG, INFO, WARNING, ERROR)

        Returns:
            List of log entries
        """
        if level is None:
            return self.logs
        return [log for log in self.logs if log["level"] == level]

    def has_log(self, message: str, level: str | None = None) -> bool:
        """Check if a specific log message exists.

        Args:
            message: Message to search for (substring match)
            level: Optional log level to filter by

        Returns:
            True if message is found, False otherwise
        """
        logs_to_search = self.get_logs(level) if level else self.logs
        return any(message in log["message"] for log in logs_to_search)
