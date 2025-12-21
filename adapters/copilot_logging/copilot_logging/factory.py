# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

import os
from typing import Optional

from .logger import Logger
from .stdout_logger import StdoutLogger
from .silent_logger import SilentLogger
from .azure_monitor_logger import AzureMonitorLogger


def _default(value: Optional[str], env_var: str, fallback: str) -> str:
    """Helper to pick an explicit value, then env var, then fallback."""
    return (value or os.getenv(env_var) or fallback)


def create_logger(
    logger_type: Optional[str] = None,
    level: Optional[str] = None,
    name: Optional[str] = None,
) -> Logger:
    """Factory function to create a logger instance.
    
    Args:
        logger_type: Type of logger to create. Options: "stdout", "silent", "azuremonitor". Defaults to LOG_TYPE env or "stdout".
        level: Logging level. Options: DEBUG, INFO, WARNING, ERROR. Defaults to LOG_LEVEL env or "INFO".
        name: Logger name for identification. Defaults to LOG_NAME env or "copilot".
        
    Returns:
        Logger instance
        
    Raises:
        ValueError: If logger_type is not recognized
        
    Example:
        >>> # Create stdout logger with INFO level
        >>> logger = create_logger(logger_type="stdout", level="INFO")
        >>> 
        >>> # Create debug logger with name
        >>> logger = create_logger(logger_type="stdout", level="DEBUG", name="my-service")
        >>> 
        >>> # Create silent logger for testing
        >>> logger = create_logger(logger_type="silent", level="INFO")
        >>> 
        >>> # Create Azure Monitor logger
        >>> logger = create_logger(logger_type="azuremonitor", level="INFO", name="prod-service")
    """
    logger_type = _default(logger_type, "LOG_TYPE", "stdout").lower()
    level = _default(level, "LOG_LEVEL", "INFO").upper()
    name = _default(name, "LOG_NAME", "copilot")
    
    # Create appropriate logger
    if logger_type == "stdout":
        return StdoutLogger(level=level, name=name)
    elif logger_type == "silent":
        return SilentLogger(level=level, name=name)
    elif logger_type == "azuremonitor":
        return AzureMonitorLogger(level=level, name=name)
    else:
        raise ValueError(
            f"Unknown logger_type: {logger_type}. "
            f"Must be one of: stdout, silent, azuremonitor"
        )
