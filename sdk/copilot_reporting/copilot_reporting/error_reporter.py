# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract error reporter interface for structured error reporting."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ErrorReporter(ABC):
    """Abstract base class for error reporting.
    
    This interface allows services to emit structured error events to different
    backends (e.g., Sentry, console, file logs) and support consistent error
    tracking across environments.
    """

    @abstractmethod
    def report(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Report an exception with optional context.
        
        Args:
            error: The exception to report
            context: Optional dictionary with additional context (user_id, request_id, etc.)
        """
        pass

    @abstractmethod
    def capture_message(
        self,
        message: str,
        level: str = "error",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Capture a message without an exception.
        
        Args:
            message: The message to capture
            level: Severity level (debug, info, warning, error, critical)
            context: Optional dictionary with additional context
        """
        pass
