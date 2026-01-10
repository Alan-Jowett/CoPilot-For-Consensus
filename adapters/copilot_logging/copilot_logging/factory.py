# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

from copilot_config import DriverConfig

from .azure_monitor_logger import AzureMonitorLogger
from .logger import Logger
from .silent_logger import SilentLogger
from .stdout_logger import StdoutLogger


def create_logger(
    driver_name: str,
    driver_config: DriverConfig,
) -> Logger:
    """Create a logger instance based on driver type and configuration.

    This factory is typically called by service configuration loaders that provide
    DriverConfig objects with attribute access. Configuration properties are accessed
    via attributes (config.level, config.name) with defaults defined in schemas.

    Args:
        driver_name: Logger driver type. Options: 'stdout', 'silent', 'azuremonitor'
        driver_config: DriverConfig with driver-specific attributes.
                      Expected attributes (with schema-provided defaults):
                      - level: Logging level (DEBUG, INFO, WARNING, ERROR)
                      - name: Logger name for identification
                      - instrumentation_key: Azure Monitor key (azuremonitor only)
                      - console_log: Also log to console (azuremonitor only)

    Returns:
        Logger instance

    Raises:
        ValueError: If driver_name is not recognized
        TypeError: If driver_config is not a DriverConfig instance

    Example:
        >>> # Typically called by config loader:
        >>> from copilot_config import load_service_config
        >>> config = load_service_config("my-service")
        >>> logger_adapter = config.get_adapter("logger")
        >>> logger = create_logger(
        ...     logger_adapter.driver_name,
        ...     logger_adapter.driver_config
        ... )
    """
    driver_lower = driver_name.lower()

    if driver_lower == "stdout":
        return StdoutLogger.from_config(driver_config)
    elif driver_lower == "silent":
        return SilentLogger.from_config(driver_config)
    elif driver_lower == "azuremonitor":
        return AzureMonitorLogger.from_config(driver_config)
    else:
        raise ValueError(
            f"Unknown logger driver: {driver_name}. "
            f"Must be one of: stdout, silent, azuremonitor"
        )


def create_stdout_logger(
    level: str = "INFO",
    name: str | None = None
) -> StdoutLogger:
    """Create a stdout logger for early initialization before config is loaded.
    
    This is a convenience function for services that need logging before
    their configuration system is fully initialized. It uses the same
    DriverConfig-based factory path as other loggers to ensure consistent
    initialization behavior.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
        name: Optional logger name for identification.
    
    Returns:
        StdoutLogger instance
    
    Example:
        >>> from copilot_logging import create_stdout_logger
        >>> logger = create_stdout_logger(level="DEBUG", name="startup")
        >>> logger.info("Service initializing...")
    """
    # Build complete config dict before creating DriverConfig
    config = {"level": level}
    if name is not None:
        config["name"] = name
    
    driver_config = DriverConfig(
        driver_name="stdout",
        config=config,
        allowed_keys=["level", "name"]
    )
    
    # Delegate to the main factory to keep initialization logic consistent.
    return create_logger("stdout", driver_config)
