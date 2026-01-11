# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Silent error reporter implementation for testing."""

from typing import Any

from copilot_config import DriverConfig

from .error_reporter import ErrorReporter


class SilentErrorReporter(ErrorReporter):
    """Silent error reporter that stores errors in memory for testing.

    This implementation is useful for unit tests where you want to verify
    error reporting behavior without producing actual logs or side effects.
    """

    def __init__(self):
        """Initialize silent error reporter."""
        self.reported_errors: list[dict[str, Any]] = []
        self.captured_messages: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, config: DriverConfig) -> "SilentErrorReporter":
        """Create SilentErrorReporter from DriverConfig.

        Args:
            config: DriverConfig (ignored, no configuration needed)

        Returns:
            SilentErrorReporter instance
        """
        return cls()

    def report(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """Report an exception with optional context.

        Args:
            error: The exception to report
            context: Optional dictionary with additional context
        """
        self.reported_errors.append({
            "error": error,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
        })

    def capture_message(
        self,
        message: str,
        level: str = "error",
        context: dict[str, Any] | None = None
    ) -> None:
        """Capture a message without an exception.

        Args:
            message: The message to capture
            level: Severity level (debug, info, warning, error, critical)
            context: Optional dictionary with additional context
        """
        self.captured_messages.append({
            "message": message,
            "level": level,
            "context": context or {},
        })

    def get_errors(self, error_type: str | None = None) -> list[dict[str, Any]]:
        """Get all reported errors, optionally filtered by type.

        Args:
            error_type: Optional error type to filter by

        Returns:
            List of reported error dictionaries
        """
        if error_type:
            return [e for e in self.reported_errors if e["error_type"] == error_type]
        return self.reported_errors

    def get_messages(self, level: str | None = None) -> list[dict[str, Any]]:
        """Get all captured messages, optionally filtered by level.

        Args:
            level: Optional level to filter by

        Returns:
            List of captured message dictionaries
        """
        if level:
            return [m for m in self.captured_messages if m["level"] == level]
        return self.captured_messages

    def clear(self) -> None:
        """Clear all stored errors and messages."""
        self.reported_errors.clear()
        self.captured_messages.clear()

    def has_errors(self) -> bool:
        """Check if any errors have been reported.

        Returns:
            True if errors have been reported, False otherwise
        """
        return len(self.reported_errors) > 0

    def has_messages(self, level: str | None = None) -> bool:
        """Check if any messages have been captured.

        Args:
            level: Optional level to filter by

        Returns:
            True if messages have been captured, False otherwise
        """
        if level:
            return any(m["level"] == level for m in self.captured_messages)
        return len(self.captured_messages) > 0
