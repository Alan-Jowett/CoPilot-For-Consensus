# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Silent logger implementation for testing."""

from typing import Any, List, Dict

from .logger import Logger


class SilentLogger(Logger):
    """Logger that stores log messages in memory without output.
    
    Useful for testing to verify logging behavior without cluttering test output.
    """

    def __init__(self):
        """Initialize silent logger."""
        self.logs: List[Dict[str, Any]] = []

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal method to store log message.
        
        Args:
            level: Log level
            message: The log message
            **kwargs: Additional structured data to log
        """
        log_entry = {
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

    def get_logs(self, level: str = None) -> List[Dict[str, Any]]:
        """Get stored log messages, optionally filtered by level.
        
        Args:
            level: Optional log level to filter by (DEBUG, INFO, WARNING, ERROR)
            
        Returns:
            List of log entries
        """
        if level is None:
            return self.logs
        return [log for log in self.logs if log["level"] == level]

    def has_log(self, message: str, level: str = None) -> bool:
        """Check if a specific log message exists.
        
        Args:
            message: Message to search for (substring match)
            level: Optional log level to filter by
            
        Returns:
            True if message is found, False otherwise
        """
        logs_to_search = self.get_logs(level) if level else self.logs
        return any(message in log["message"] for log in logs_to_search)
