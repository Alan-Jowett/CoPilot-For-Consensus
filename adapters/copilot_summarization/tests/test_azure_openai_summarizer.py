# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure OpenAI Summarizer."""

from unittest.mock import Mock, patch

import pytest
from copilot_summarization.models import Thread
from copilot_summarization.openai_summarizer import OpenAISummarizer


class TestAzureOpenAISummarizer:
    """Tests for Azure OpenAI summarizer implementation."""

    def test_azure_openai_summarizer_creation(self, mock_openai_module):
        """Test creating an Azure OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                api_version="2023-12-01",
                deployment_name="gpt-4-deployment"
            )

            assert summarizer.api_key == "test-azure-key"
            assert summarizer.model == "gpt-4"
            assert summarizer.base_url == "https://test.openai.azure.com/"
            assert summarizer.is_azure is True
            assert summarizer.deployment_name == "gpt-4-deployment"

            # Verify AzureOpenAI client was created with correct parameters
            mock_azure_class.assert_called_once_with(
                api_key="test-azure-key",
                api_version="2023-12-01",
                azure_endpoint="https://test.openai.azure.com/"
            )

    def test_azure_openai_summarizer_default_api_version(self, mock_openai_module):
        """Test that Azure OpenAI summarizer uses default API version."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/"
            )

            # With only base_url provided and no Azure-specific args, this is treated as
            # an OpenAI-compatible base URL (not Azure).
            assert summarizer.is_azure is False

    def test_azure_openai_summarizer_deployment_name_defaults_to_model(self, mock_openai_module):
        """Test that deployment_name defaults to model if not provided."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                api_version="2023-12-01"
            )

            assert summarizer.deployment_name == "gpt-4"

    def test_azure_openai_summarize(self, mock_openai_module):
        """Test Azure OpenAI summarize with real API call structure."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock the API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is a test summary from Azure OpenAI."))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20)

        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                deployment_name="gpt-4-deployment",
                api_version="2023-12-01"
            )

            thread = Thread(
                thread_id="test-thread-456",
                messages=["Message 1 content", "Message 2 content"]
            )

            summary = summarizer.summarize(thread)

            # Verify API call was made with correct parameters
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args

            assert call_args[1]["model"] == "gpt-4-deployment"
            assert call_args[1]["max_tokens"] == thread.context_window_tokens
            assert len(call_args[1]["messages"]) == 1
            assert call_args[1]["messages"][0]["role"] == "user"

            # Verify summary metadata
            assert summary.thread_id == "test-thread-456"
            assert summary.summary_markdown == "This is a test summary from Azure OpenAI."
            assert summary.llm_backend == "azure"
            assert summary.llm_model == "gpt-4-deployment"
            assert summary.tokens_prompt == 100
            assert summary.tokens_completion == 20
            assert summary.latency_ms >= 0

    def test_azure_openai_summarize_error_handling(self, mock_openai_module):
        """Test Azure OpenAI summarize error handling with various exception types."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                deployment_name="gpt-4-deployment",
                api_version="2023-12-01"
            )

            thread = Thread(
                thread_id="test-thread-789",
                messages=["Message 1 content"]
            )

            # Test IndexError/AttributeError from malformed API response (empty choices)
            mock_client.chat.completions.create = Mock(return_value=Mock(choices=[]))
            with pytest.raises((IndexError, AttributeError)):
                summarizer.summarize(thread)

            # Test AttributeError from missing response attributes
            mock_response = Mock(spec=[])  # Mock with no attributes
            mock_client.chat.completions.create = Mock(return_value=mock_response)
            with pytest.raises(AttributeError):
                summarizer.summarize(thread)

            # Test generic exception propagation (network errors, API errors, etc.)
            mock_client.chat.completions.create = Mock(side_effect=RuntimeError("Network timeout"))
            with pytest.raises(RuntimeError, match="Network timeout"):
                summarizer.summarize(thread)

    def test_azure_openai_initialization_without_library(self):
        """Test that initialization fails without openai library."""
        with patch.dict('sys.modules', {'openai': None}):
            with pytest.raises(ImportError) as exc_info:
                OpenAISummarizer(
                    api_key="test-key",
                    model="gpt-4",
                    base_url="https://test.openai.azure.com/"
                )

            assert "openai is required" in str(exc_info.value)
    def test_azure_deployment_name_without_api_version_raises_error(self, mock_openai_module, llm_driver_config):
        """Test that deployment_name without api_version raises ValueError."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            config = llm_driver_config(
                "azure",
                fields={
                    "azure_openai_api_key": "test-key",
                    "azure_openai_model": "gpt-4",
                    "azure_openai_endpoint": "https://test.openai.azure.com/",
                    "azure_openai_deployment": "test-deployment",
                    # Intentionally omit azure_openai_api_version to trigger validation error
                }
            )
            with pytest.raises(ValueError, match="requires 'api_version'"):
                OpenAISummarizer.from_config(config)

    def test_azure_with_api_version_enables_azure_mode(self, mock_openai_module, llm_driver_config):
        """Test that api_version alone enables Azure mode."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict('sys.modules', {'openai': mock_module}):
            config = llm_driver_config(
                "azure",
                fields={
                    "azure_openai_api_key": "test-key",
                    "azure_openai_model": "gpt-4",
                    "azure_openai_endpoint": "https://test.openai.azure.com/",
                    "azure_openai_api_version": "2024-02-15-preview",
                }
            )
            summarizer = OpenAISummarizer.from_config(config)
            assert summarizer.is_azure is True