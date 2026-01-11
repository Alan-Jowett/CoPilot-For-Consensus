# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Error Reporting Adapter.

A shared library for error reporting and diagnostics across microservices
in the Copilot-for-Consensus system.
"""

from copilot_config import DriverConfig

from .error_reporter import ErrorReporter

__version__ = "0.1.0"


def create_error_reporter(
    driver_name: str,
    driver_config: DriverConfig,
) -> ErrorReporter:
    """Create an error reporter based on driver name and config (factory pattern).

    This factory is typically called by service configuration loaders that provide
    DriverConfig objects with attribute access. Configuration properties are accessed
    via attributes with defaults defined in schemas.

    Args:
        driver_name: Reporter driver ("console", "silent", "sentry")
        driver_config: DriverConfig with driver-specific attributes.
                      Expected attributes vary by reporter:
                      - console: logger_name (optional)
                      - silent: no configuration needed
                      - sentry: dsn (required), environment (optional)

    Returns:
        ErrorReporter instance

    Raises:
        ValueError: If driver_name is unknown
        TypeError: If driver_config is not a DriverConfig instance

    Example:
        >>> # Typically called by config loader:
        >>> from copilot_config import load_service_config
        >>> config = load_service_config("my-service")
        >>> error_adapter = config.get_adapter("error_reporter")
        >>> reporter = create_error_reporter(
        ...     error_adapter.driver_name,
        ...     error_adapter.driver_config
        ... )
    """
    driver_lower = driver_name.lower()

    if driver_lower == "console":
        from .console_error_reporter import ConsoleErrorReporter  # local import to keep class internal
        return ConsoleErrorReporter.from_config(driver_config)
    if driver_lower == "silent":
        from .silent_error_reporter import SilentErrorReporter  # local import to keep class internal
        return SilentErrorReporter.from_config(driver_config)
    if driver_lower == "sentry":
        from .sentry_error_reporter import SentryErrorReporter  # local import to keep class internal
        return SentryErrorReporter.from_config(driver_config)

    raise ValueError(f"Unknown reporter driver: {driver_name}")


__all__ = [
    # Version
    "__version__",
    # Error Reporters
    "ErrorReporter",
    "create_error_reporter",
]
