# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Logging Adapter.

A shared library for consistent, structured, and configurable logging
across microservices in the Copilot-for-Consensus system.

This module provides an abstraction layer for logging that allows plugging
in different logging backends and standardizing log formats for observability
and debugging.

Example:
    >>> from copilot_logging import create_logger
    >>>
    >>> # Create a logger with structured output
    >>> logger = create_logger("stdout", {"level": "INFO", "name": "my-service"})
    >>> logger.info("Service started", service="ingestion", version="1.0.0")
    >>>
    >>> # Create a silent logger for testing
    >>> test_logger = create_logger("silent")
    >>> test_logger.info("Test message")
"""

__version__ = "0.1.0"

from .factory import create_logger, create_stdout_logger, get_logger, set_default_logger
from .logger import Logger
from .uvicorn_config import create_uvicorn_log_config

__all__ = [
    "__version__",
    "Logger",
    "create_logger",
    "create_stdout_logger",
    "create_uvicorn_log_config",
    "get_logger",
    "set_default_logger",
]
