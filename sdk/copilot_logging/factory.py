# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating logger instances."""

import os
from typing import Optional

from .logger import Logger
from .stdout_logger import StdoutLogger
from .silent_logger import SilentLogger


def create_logger(
    logger_type: Optional[str] = None,
    level: Optional[str] = None,
    name: Optional[str] = None,
) -> Logger:
    """Factory function to create a logger instance.
    
    Args:
        logger_type: Type of logger to create ("stdout", "silent").
                    If None, reads from LOG_TYPE environment variable.
                    Defaults to "stdout" if not specified.
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
              If None, reads from LOG_LEVEL environment variable.
              Defaults to "INFO" if not specified.
        name: Optional logger name for identification.
              If None, reads from LOG_NAME environment variable.
        
    Returns:
        Logger instance
        
    Raises:
        ValueError: If logger_type is not recognized
        
    Example:
        >>> # Create logger from environment variables
        >>> logger = create_logger()
        >>> 
        >>> # Create specific logger type
        >>> logger = create_logger(logger_type="stdout", level="DEBUG")
        >>> 
        >>> # Create silent logger for testing
        >>> logger = create_logger(logger_type="silent")
    """
    # Determine logger type from environment or parameter
    if logger_type is None:
        logger_type = os.getenv("LOG_TYPE", "stdout").lower()
    else:
        logger_type = logger_type.lower()
    
    # Determine log level from environment or parameter
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    else:
        level = level.upper()
    
    # Determine logger name from environment or parameter
    if name is None:
        name = os.getenv("LOG_NAME")
    
    # Create appropriate logger
    if logger_type == "stdout":
        return StdoutLogger(level=level, name=name)
    elif logger_type == "silent":
        return SilentLogger()
    else:
        raise ValueError(
            f"Unknown logger_type: {logger_type}. "
            f"Must be one of: stdout, silent"
        )
