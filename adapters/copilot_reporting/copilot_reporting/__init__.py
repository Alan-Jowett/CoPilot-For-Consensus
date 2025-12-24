# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Reporting Adapter.

A shared library for error reporting and diagnostics across microservices
in the Copilot-for-Consensus system.
"""

from typing import Optional

from .console_error_reporter import ConsoleErrorReporter
from .error_reporter import ErrorReporter
from .sentry_error_reporter import SentryErrorReporter
from .silent_error_reporter import SilentErrorReporter

__version__ = "0.1.0"


def create_error_reporter(
    reporter_type: str = "console",
    logger_name: str | None = None,
    dsn: str | None = None,
    environment: str = "production",
    **kwargs
) -> ErrorReporter:
    """Create an error reporter based on type.

    Args:
        reporter_type: Type of reporter ("console", "silent", "sentry")
        logger_name: Logger name for console reporter (optional)
        dsn: Sentry DSN for sentry reporter (optional)
        environment: Environment name for sentry reporter (optional)
        **kwargs: Additional reporter-specific arguments

    Returns:
        ErrorReporter instance

    Raises:
        ValueError: If reporter_type is unknown
    """
    if reporter_type == "console":
        return ConsoleErrorReporter(logger_name=logger_name)
    elif reporter_type == "silent":
        return SilentErrorReporter()
    elif reporter_type == "sentry":
        return SentryErrorReporter(dsn=dsn, environment=environment)
    else:
        raise ValueError(f"Unknown reporter type: {reporter_type}")


__all__ = [
    # Version
    "__version__",
    # Error Reporters
    "ErrorReporter",
    "ConsoleErrorReporter",
    "SilentErrorReporter",
    "SentryErrorReporter",
    "create_error_reporter",
]
