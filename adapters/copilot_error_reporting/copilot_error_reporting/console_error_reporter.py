# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Console-based error reporter implementation."""

import logging
import traceback
from typing import Any

from copilot_config import DriverConfig

from .error_reporter import ErrorReporter

logger = logging.getLogger(__name__)


class ConsoleErrorReporter(ErrorReporter):
    """Console error reporter that logs errors to stdout.

    This is the default error reporter implementation that writes structured
    error information to the console using Python's logging system.
    """

    def __init__(self, logger_name: str | None = None):
        """Initialize console error reporter.

        Args:
            logger_name: Optional logger name to use (defaults to module logger)
        """
        self.logger = logging.getLogger(logger_name) if logger_name else logger

    @classmethod
    def from_config(cls, config: DriverConfig) -> "ConsoleErrorReporter":
        """Create ConsoleErrorReporter from DriverConfig.
        
        Args:
            config: DriverConfig with optional logger_name attribute.
        
        Returns:
            ConsoleErrorReporter instance
        """
        # ConsoleErrorReporter has optional logger_name configuration
        logger_name = config.config.get("logger_name")
        return cls(logger_name=logger_name)

    def report(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """Report an exception with optional context.

        Args:
            error: The exception to report
            context: Optional dictionary with additional context
        """
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        log_message = f"Exception occurred: {error_type}: {error_message}"

        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            log_message += f" | Context: {context_str}"

        self.logger.error(log_message)
        self.logger.debug(f"Stack trace:\n{stack_trace}")

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
        log_message = message

        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            log_message += f" | Context: {context_str}"

        # Map level string to logging level
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }

        log_level = level_map.get(level.lower(), logging.ERROR)
        self.logger.log(log_level, log_message)
