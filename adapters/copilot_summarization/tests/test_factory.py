# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for LLM backend factory."""

from unittest.mock import patch

import pytest
from copilot_summarization.factory import create_llm_backend
from copilot_summarization.llamacpp_summarizer import LlamaCppSummarizer
from copilot_summarization.local_llm_summarizer import LocalLLMSummarizer
from copilot_summarization.mock_summarizer import MockSummarizer
from copilot_summarization.openai_summarizer import OpenAISummarizer


class TestLLMBackendFactory:
    """Tests for create_llm_backend."""

    def test_create_mock_summarizer(self, llm_backend_config):
        """Test creating a mock summarizer."""
        config = llm_backend_config("mock")
        summarizer = create_llm_backend(config)
        assert isinstance(summarizer, MockSummarizer)

    def test_driver_name_is_required(self):
        """Test that driver_name parameter is required."""
        with pytest.raises(TypeError):
            create_llm_backend()  # type: ignore[call-arg]

    def test_create_openai_summarizer(self, mock_openai_module, llm_backend_config):
        """Test creating an OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict("sys.modules", {"openai": mock_module}):
            config = llm_backend_config("openai", fields={"openai_api_key": "test-key", "openai_model": "gpt-4"})
            summarizer = create_llm_backend(config)
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.api_key == "test-key"
            assert summarizer.model == "gpt-4"

    def test_create_openai_summarizer_missing_key(self):
        """Test that OpenAI config requires API key."""
        from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_Openai

        with pytest.raises(TypeError):
            DriverConfig_LlmBackend_Openai(openai_model="gpt-4")  # type: ignore[call-arg]

    def test_create_openai_summarizer_missing_model(self):
        """Test that OpenAI config requires model."""
        from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_Openai

        with pytest.raises(TypeError):
            DriverConfig_LlmBackend_Openai(openai_api_key="test-key")  # type: ignore[call-arg]

    def test_create_azure_summarizer(self, mock_openai_module, llm_backend_config):
        """Test creating an Azure OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = create_llm_backend(
                llm_backend_config(
                    "azure_openai_gpt",
                    fields={
                        "azure_openai_api_key": "azure-key",
                        "azure_openai_endpoint": "https://test.openai.azure.com",
                        "azure_openai_model": "gpt-4",
                    },
                )
            )
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.api_key == "azure-key"
            assert summarizer.base_url == "https://test.openai.azure.com"
            assert summarizer.model == "gpt-4"
            assert summarizer.is_azure is True

    def test_create_azure_summarizer_with_deployment_name(self, mock_openai_module, llm_backend_config):
        """Test creating an Azure OpenAI summarizer with deployment name."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = create_llm_backend(
                llm_backend_config(
                    "azure_openai_gpt",
                    fields={
                        "azure_openai_api_key": "azure-key",
                        "azure_openai_endpoint": "https://test.openai.azure.com",
                        "azure_openai_model": "gpt-4",
                        "azure_openai_deployment": "gpt-4-deployment",
                        "azure_openai_api_version": "2023-12-01",
                    },
                )
            )
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.deployment_name == "gpt-4-deployment"
            assert summarizer.is_azure is True

            # Verify api_version was passed correctly to AzureOpenAI client
            mock_azure_class.assert_called_once_with(
                api_key="azure-key", api_version="2023-12-01", azure_endpoint="https://test.openai.azure.com"
            )

    def test_create_azure_summarizer_missing_key(self):
        """Test that Azure config requires API key."""
        from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_AzureOpenaiGpt

        with pytest.raises(TypeError):
            DriverConfig_LlmBackend_AzureOpenaiGpt(
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_model="gpt-4",
            )  # type: ignore[call-arg]

    def test_create_azure_summarizer_missing_endpoint(self):
        """Test that Azure config requires endpoint."""
        from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_AzureOpenaiGpt

        with pytest.raises(TypeError):
            DriverConfig_LlmBackend_AzureOpenaiGpt(
                azure_openai_api_key="test-key",
                azure_openai_model="gpt-4",
            )  # type: ignore[call-arg]

    def test_create_azure_summarizer_missing_model(self):
        """Test that Azure config requires model."""
        from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_AzureOpenaiGpt

        with pytest.raises(TypeError):
            DriverConfig_LlmBackend_AzureOpenaiGpt(
                azure_openai_api_key="test-key",
                azure_openai_endpoint="https://test.openai.azure.com",
            )  # type: ignore[call-arg]

    def test_create_local_summarizer(self, llm_backend_config):
        """Test creating a local LLM summarizer."""
        summarizer = create_llm_backend(
            llm_backend_config(
                "local",
                fields={
                    "local_llm_model": "llama2",
                    "local_llm_endpoint": "http://localhost:8080",
                },
            )
        )
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.model == "llama2"
        assert summarizer.base_url == "http://localhost:8080"
        assert summarizer.timeout == 300  # default

    def test_create_local_summarizer_with_timeout(self, llm_backend_config):
        """Test creating a local LLM summarizer with custom timeout."""
        summarizer = create_llm_backend(
            llm_backend_config(
                "local",
                fields={
                    "local_llm_model": "llama2",
                    "local_llm_endpoint": "http://localhost:8080",
                    "local_llm_timeout_seconds": 300,
                },
            )
        )
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.model == "llama2"
        assert summarizer.base_url == "http://localhost:8080"
        assert summarizer.timeout == 300

    def test_create_local_summarizer_missing_model(self, llm_backend_config):
        """Test that local LLM summarizer uses schema defaults."""
        summarizer = create_llm_backend(llm_backend_config("local"))
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.model == "mistral"
        assert summarizer.base_url == "http://ollama:11434"
        assert summarizer.timeout == 300

    def test_create_local_summarizer_missing_base_url(self, llm_backend_config):
        """Test that local LLM summarizer uses schema default endpoint."""
        summarizer = create_llm_backend(llm_backend_config("local", fields={"local_llm_model": "mistral"}))
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.base_url == "http://ollama:11434"

    def test_create_llamacpp_summarizer(self, llm_backend_config):
        """Test creating a llama.cpp summarizer."""
        summarizer = create_llm_backend(
            llm_backend_config(
                "llamacpp",
                fields={
                    "llamacpp_model": "mistral-7b-instruct-v0.2.Q4_K_M",
                    "llamacpp_endpoint": "http://llama-cpp:8080",
                },
            )
        )
        assert isinstance(summarizer, LlamaCppSummarizer)
        assert summarizer.model == "mistral-7b-instruct-v0.2.Q4_K_M"
        assert summarizer.base_url == "http://llama-cpp:8080"
        assert summarizer.timeout == 300  # default

    def test_create_llamacpp_summarizer_with_timeout(self, llm_backend_config):
        """Test creating a llama.cpp summarizer with custom timeout."""
        summarizer = create_llm_backend(
            llm_backend_config(
                "llamacpp",
                fields={
                    "llamacpp_model": "mistral-7b-instruct-v0.2.Q4_K_M",
                    "llamacpp_endpoint": "http://llama-cpp:8080",
                    "llamacpp_timeout_seconds": 600,
                },
            )
        )
        assert isinstance(summarizer, LlamaCppSummarizer)
        assert summarizer.model == "mistral-7b-instruct-v0.2.Q4_K_M"
        assert summarizer.base_url == "http://llama-cpp:8080"
        assert summarizer.timeout == 600

    def test_create_llamacpp_summarizer_missing_model(self, llm_backend_config):
        """Test that llama.cpp summarizer uses schema defaults."""
        summarizer = create_llm_backend(llm_backend_config("llamacpp"))
        assert isinstance(summarizer, LlamaCppSummarizer)
        assert summarizer.model == "mistral"
        assert summarizer.base_url == "http://llama-cpp:8081"
        assert summarizer.timeout == 300

    def test_create_llamacpp_summarizer_missing_base_url(self, llm_backend_config):
        """Test that llama.cpp summarizer uses schema default endpoint."""
        summarizer = create_llm_backend(
            llm_backend_config("llamacpp", fields={"llamacpp_model": "mistral-7b-instruct-v0.2.Q4_K_M"})
        )
        assert isinstance(summarizer, LlamaCppSummarizer)
        assert summarizer.base_url == "http://llama-cpp:8081"

    def test_unknown_provider(self, llm_backend_config):
        """Test that unknown provider raises error."""
        from copilot_config.generated.adapters.llm_backend import (
            AdapterConfig_LlmBackend,
            DriverConfig_LlmBackend_Mock,
        )

        with pytest.raises(ValueError, match="Unknown llm_backend driver"):
            create_llm_backend(
                AdapterConfig_LlmBackend(
                    llm_backend_type="unknown",  # type: ignore[arg-type]
                    driver=DriverConfig_LlmBackend_Mock(mock_latency_ms=0),
                )
            )

    def test_driver_name_parameter_is_required(self):
        """Test that driver_name parameter is required."""
        with pytest.raises(TypeError):
            create_llm_backend()  # type: ignore[call-arg]
