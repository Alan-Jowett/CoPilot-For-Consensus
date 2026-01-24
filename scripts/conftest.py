# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration for scripts tests."""

import sys
from unittest.mock import MagicMock

# Create a mock copilot_logging module to avoid import errors in tests
mock_logging = MagicMock()


def create_stdout_logger(level="INFO", name=None):
    """Create a mock logger that behaves like copilot_logging.create_stdout_logger."""
    mock_logger = MagicMock()
    return mock_logger


mock_logging.create_stdout_logger = create_stdout_logger

# Install the mock before any imports
sys.modules["copilot_logging"] = mock_logging
