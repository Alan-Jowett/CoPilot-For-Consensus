# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

from copilot_config import DriverConfig

from .azure_monitor_logger import AzureMonitorLogger
from .logger import Logger
from .silent_logger import SilentLogger
from .stdout_logger import StdoutLogger

# Global logger registry (similar to logging.getLogger)
_logger_registry: dict[str, Logger] = {}
_default_logger: Logger | None = None


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
    config_dict: dict[str, str] = {"level": level}
    if name is not None:
        config_dict["name"] = name

    driver_config = DriverConfig(
        driver_name="stdout",
        config=config_dict,
        allowed_keys=["level", "name"]
    )

    # Delegate to the main factory to keep initialization logic consistent.
    return create_logger("stdout", driver_config)


def set_default_logger(logger: Logger) -> None:
    """Set the default logger for the application.

    This should be called during service initialization after the configuration
    is loaded. Once set, any module can use get_logger() to retrieve loggers.

    When a new default logger is set, the logger registry is cleared so that
    subsequent get_logger() calls receive the new default.

    Args:
        logger: The logger instance to use as default

    Example:
        >>> from copilot_logging import create_logger, set_default_logger
        >>> # In main.py or startup
        >>> logger = create_logger("stdout", config.logger.driver_config)
        >>> set_default_logger(logger)
    """
    global _default_logger, _logger_registry
    _default_logger = logger
    # Clear the registry so existing cached loggers are invalidated
    _logger_registry = {}


def get_logger(name: str | None = None) -> Logger:
    """Get a logger instance by name, similar to logging.getLogger().

    If a default logger has been set via set_default_logger(), returns either
    a cached named instance or the default logger. If no default is set,
    creates a basic stdout logger as a fallback.

    Args:
        name: Optional logger name (e.g., __name__). Used for namespacing
              in the logger registry.

    Returns:
        Logger instance

    Example:
        >>> from copilot_logging import get_logger
        >>>
        >>> # In any module after set_default_logger() was called
        >>> logger = get_logger(__name__)
        >>> logger.info("Message", key="value")
    """
    global _default_logger, _logger_registry

    # If name is provided and we have a cached instance, return it
    if name and name in _logger_registry:
        return _logger_registry[name]

    # If we have a default logger, use it (optionally cache by name)
    if _default_logger:
        if name:
            _logger_registry[name] = _default_logger
        return _default_logger

    # Fallback: create a basic stdout logger if no default is set
    # This ensures get_logger() never fails, similar to logging.getLogger()
    fallback = create_stdout_logger(level="INFO", name=name)
    if name:
        _logger_registry[name] = fallback
    return fallback
