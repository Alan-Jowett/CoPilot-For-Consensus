# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Error Reporting Adapter.

A shared library for error reporting and diagnostics across microservices
in the Copilot-for-Consensus system.
"""

from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.error_reporter import (
    AdapterConfig_ErrorReporter,
    DriverConfig_ErrorReporter_Console,
    DriverConfig_ErrorReporter_Sentry,
    DriverConfig_ErrorReporter_Silent,
)

from .error_reporter import ErrorReporter

__version__ = "0.1.0"

_DriverConfig: TypeAlias = (
    DriverConfig_ErrorReporter_Console
    | DriverConfig_ErrorReporter_Sentry
    | DriverConfig_ErrorReporter_Silent
)


def _build_console(config: _DriverConfig) -> ErrorReporter:
    from .console_error_reporter import ConsoleErrorReporter

    if not isinstance(config, DriverConfig_ErrorReporter_Console):
        raise TypeError("driver config must be DriverConfig_ErrorReporter_Console")
    return ConsoleErrorReporter.from_config(config)


def _build_silent(config: _DriverConfig) -> ErrorReporter:
    from .silent_error_reporter import SilentErrorReporter

    if not isinstance(config, DriverConfig_ErrorReporter_Silent):
        raise TypeError("driver config must be DriverConfig_ErrorReporter_Silent")
    return SilentErrorReporter.from_config(config)


def _build_sentry(config: _DriverConfig) -> ErrorReporter:
    from .sentry_error_reporter import SentryErrorReporter

    if not isinstance(config, DriverConfig_ErrorReporter_Sentry):
        raise TypeError("driver config must be DriverConfig_ErrorReporter_Sentry")
    return SentryErrorReporter.from_config(config)

def create_error_reporter(config: AdapterConfig_ErrorReporter) -> ErrorReporter:
    """Create an error reporter from typed configuration.

    Args:
        config: Typed adapter configuration for error_reporter.

    Returns:
        ErrorReporter instance.

    Raises:
        ValueError: If config is missing or error_reporter_type is not recognized.
    """
    return create_adapter(
        config,
        adapter_name="error_reporter",
        get_driver_type=lambda c: c.error_reporter_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "console": _build_console,
            "silent": _build_silent,
            "sentry": _build_sentry,
        },
    )


__all__ = [
    # Version
    "__version__",
    # Error Reporters
    "ErrorReporter",
    "create_error_reporter",
]
