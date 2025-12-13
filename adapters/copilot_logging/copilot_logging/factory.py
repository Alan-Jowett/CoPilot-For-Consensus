# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

import os
from typing import Optional

from .logger import Logger
from .stdout_logger import StdoutLogger
from .silent_logger import SilentLogger


def create_logger(
    logger_type: str,
    level: str,
    name: Optional[str] = None,
) -> Logger:
    """Factory function to create a logger instance.
    
    Args:
        logger_type: Type of logger to create (required). Options: "stdout", "silent"
        level: Logging level (required). Options: DEBUG, INFO, WARNING, ERROR
        name: Optional logger name for identification.
        
    Returns:
        Logger instance
        
    Raises:
        ValueError: If logger_type is not recognized or required parameters are missing
        
    Example:
        >>> # Create stdout logger with INFO level
        >>> logger = create_logger(logger_type="stdout", level="INFO")
        >>> 
        >>> # Create debug logger with name
        >>> logger = create_logger(logger_type="stdout", level="DEBUG", name="my-service")
        >>> 
        >>> # Create silent logger for testing
        >>> logger = create_logger(logger_type="silent", level="INFO")
    """
    if not logger_type:
        raise ValueError(
            "logger_type parameter is required. "
            "Must be one of: stdout, silent"
        )
    
    if not level:
        raise ValueError(
            "level parameter is required. "
            "Must be one of: DEBUG, INFO, WARNING, ERROR"
        )
    
    logger_type = logger_type.lower()
    level = level.upper()
    
    # Create appropriate logger
    if logger_type == "stdout":
        return StdoutLogger(level=level, name=name)
    elif logger_type == "silent":
        return SilentLogger(level=level, name=name)
    else:
        raise ValueError(
            f"Unknown logger_type: {logger_type}. "
            f"Must be one of: stdout, silent"
        )
