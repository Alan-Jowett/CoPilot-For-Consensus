# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure OpenAI Summarizer."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from copilot_summarization.openai_summarizer import OpenAISummarizer
from copilot_summarization.models import Thread


class TestAzureOpenAISummarizer:
    """Tests for Azure OpenAI summarizer implementation."""
    
    def test_azure_openai_summarizer_creation(self):
        """Test creating an Azure OpenAI summarizer."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
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
    
    def test_azure_openai_summarizer_default_api_version(self):
        """Test that Azure OpenAI summarizer uses default API version."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/"
            )
            
            # Verify default API version was used
            mock_azure_class.assert_called_once_with(
                api_key="test-azure-key",
                api_version="2023-12-01",
                azure_endpoint="https://test.openai.azure.com/"
            )
    
    def test_azure_openai_summarizer_deployment_name_defaults_to_model(self):
        """Test that deployment_name defaults to model if not provided."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/"
            )
            
            assert summarizer.deployment_name == "gpt-4"
    
    def test_azure_openai_summarize(self):
        """Test Azure OpenAI summarize with real API call structure."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        
        # Mock the API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is a test summary from Azure OpenAI."))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20)
        
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                deployment_name="gpt-4-deployment"
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
    
    def test_azure_openai_summarize_error_handling(self):
        """Test Azure OpenAI summarize error handling."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        
        # Mock API error
        mock_client.chat.completions.create = Mock(side_effect=Exception("API Error"))
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            summarizer = OpenAISummarizer(
                api_key="test-azure-key",
                model="gpt-4",
                base_url="https://test.openai.azure.com/",
                deployment_name="gpt-4-deployment"
            )
            
            thread = Thread(
                thread_id="test-thread-789",
                messages=["Message 1 content"]
            )
            
            # Verify that exception is propagated
            with pytest.raises(Exception, match="API Error"):
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
