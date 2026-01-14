# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

from typing import cast

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_AzureMonitor,
    DriverConfig_Logger_Silent,
    DriverConfig_Logger_Stdout,
)

from .azure_monitor_logger import AzureMonitorLogger
from .logger import Logger
from .silent_logger import SilentLogger
from .stdout_logger import StdoutLogger

# Global logger registry (similar to logging.getLogger)
_logger_registry: dict[str, Logger] = {}
_default_logger: Logger | None = None


def create_logger(
    config: AdapterConfig_Logger,
) -> Logger:
    """Create a logger instance from typed adapter configuration.

    Args:
        config: Typed adapter configuration for logger.

    Returns:
        Logger instance.

    Raises:
        ValueError: If config is missing or logger_type is not recognized.
    """
    return create_adapter(
        config,
        adapter_name="logger",
        get_driver_type=lambda c: c.logger_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "stdout": StdoutLogger.from_config,
            "silent": SilentLogger.from_config,
            "azure_monitor": AzureMonitorLogger.from_config,
        },
    )


def create_stdout_logger(
    level: str | None = None,
    name: str | None = None,
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
    driver_config = DriverConfig_Logger_Stdout()
    if level is not None:
        driver_config.level = level
    if name is not None:
        driver_config.name = name

    logger = create_logger(
        AdapterConfig_Logger(
            logger_type="stdout",
            driver=driver_config,
        )
    )
    return cast(StdoutLogger, logger)


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
