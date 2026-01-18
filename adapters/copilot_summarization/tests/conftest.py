# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Shared test fixtures for copilot_summarization tests."""

from unittest.mock import Mock

import pytest
from copilot_config.generated.adapters.llm_backend import (
    AdapterConfig_LlmBackend,
    DriverConfig_LlmBackend_AzureOpenaiGpt,
    DriverConfig_LlmBackend_Llamacpp,
    DriverConfig_LlmBackend_Local,
    DriverConfig_LlmBackend_Mock,
    DriverConfig_LlmBackend_Openai,
)


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
    """Create typed driver config for llm_backend drivers."""

    def _make(driver: str, fields: dict | None = None):
        fields = fields or {}

        if driver == "openai":
            payload = {"openai_api_key": "test-key", "openai_model": "gpt-4"}
            payload.update(fields)
            return DriverConfig_LlmBackend_Openai(**payload)

        if driver == "azure_openai_gpt":
            payload = {
                "azure_openai_api_key": "azure-key",
                "azure_openai_endpoint": "https://test.openai.azure.com",
                "azure_openai_model": "gpt-4",
            }
            payload.update(fields)
            return DriverConfig_LlmBackend_AzureOpenaiGpt(**payload)

        if driver == "local":
            return DriverConfig_LlmBackend_Local(**fields)

        if driver == "llamacpp":
            return DriverConfig_LlmBackend_Llamacpp(**fields)

        if driver == "mock":
            return DriverConfig_LlmBackend_Mock(**fields)

        raise ValueError(f"Unknown llm_backend driver for tests: {driver}")

    return _make


@pytest.fixture
def llm_backend_config(llm_driver_config):
    """Create typed AdapterConfig_LlmBackend for llm_backend drivers."""

    def _make(driver: str, fields: dict | None = None):
        return AdapterConfig_LlmBackend(
            llm_backend_type=driver,
            driver=llm_driver_config(driver, fields=fields),
        )

    return _make
