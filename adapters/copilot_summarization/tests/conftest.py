# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Shared test fixtures for copilot_summarization tests."""

from unittest.mock import Mock

import pytest

from copilot_config.load_driver_config import load_driver_config


@pytest.fixture
def mock_openai_module():
    """Provide mocked openai module for testing."""
    mock_module = Mock()
    mock_openai_class = Mock()
    mock_azure_class = Mock()
    mock_client = Mock()

    mock_openai_class.return_value = mock_client
    mock_azure_class.return_value = mock_client

    mock_module.OpenAI = mock_openai_class
    mock_module.AzureOpenAI = mock_azure_class

    return mock_module, mock_client, mock_openai_class, mock_azure_class


@pytest.fixture
def llm_driver_config():
    """Create schema-validated DriverConfig for llm_backend drivers."""

    def _make(driver: str, fields: dict | None = None):
        return load_driver_config(service=None, adapter="llm_backend", driver=driver, fields=fields or {})

    return _make
