# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Error Reporting Adapter.

A shared library for error reporting and diagnostics across microservices
in the Copilot-for-Consensus system.
"""

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.error_reporter import AdapterConfig_ErrorReporter

from .error_reporter import ErrorReporter

__version__ = "0.1.0"

def create_error_reporter(config: AdapterConfig_ErrorReporter) -> ErrorReporter:
    """Create an error reporter from typed configuration.

    Args:
        config: Typed adapter configuration for error_reporter.

    Returns:
        ErrorReporter instance.

    Raises:
        ValueError: If config is missing or error_reporter_type is not recognized.
    """
    from .console_error_reporter import ConsoleErrorReporter  # local import to keep class internal
    from .sentry_error_reporter import SentryErrorReporter  # local import to keep class internal
    from .silent_error_reporter import SilentErrorReporter  # local import to keep class internal

    return create_adapter(
        config,
        adapter_name="error_reporter",
        get_driver_type=lambda c: c.error_reporter_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "console": ConsoleErrorReporter.from_config,
            "silent": SilentErrorReporter.from_config,
            "sentry": SentryErrorReporter.from_config,
        },
    )


__all__ = [
    # Version
    "__version__",
    # Error Reporters
    "ErrorReporter",
    "create_error_reporter",
]
