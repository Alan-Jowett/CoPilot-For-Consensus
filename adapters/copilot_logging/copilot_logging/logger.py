# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract logger interface."""

from abc import ABC, abstractmethod
from typing import Any


class Logger(ABC):
    """Abstract base class for loggers."""

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        pass

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        pass

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        pass

    @abstractmethod
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an exception-level message.

        Intended for logging an error message in an exception handler.

        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        pass
