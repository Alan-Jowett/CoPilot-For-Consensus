# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Logging SDK.

A shared library for consistent, structured, and configurable logging
across microservices in the Copilot-for-Consensus system.

This module provides an abstraction layer for logging that allows plugging
in different logging backends and standardizing log formats for observability
and debugging.

Example:
    >>> from copilot_logging import create_logger
    >>> 
    >>> # Create a logger with structured JSON output
    >>> logger = create_logger(logger_type="stdout", level="INFO")
    >>> logger.info("Service started", service="ingestion", version="1.0.0")
    >>> 
    >>> # Create a silent logger for testing
    >>> test_logger = create_logger(logger_type="silent")
    >>> test_logger.info("Test message")
    >>> assert test_logger.has_log("Test message")
"""

__version__ = "0.1.0"

from .logger import Logger
from .stdout_logger import StdoutLogger
from .silent_logger import SilentLogger
from .factory import create_logger

__all__ = [
    # Version
    "__version__",
    # Core interface
    "Logger",
    # Implementations
    "StdoutLogger",
    "SilentLogger",
    # Factory
    "create_logger",
]
