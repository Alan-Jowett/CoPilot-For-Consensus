# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for SummarizerFactory."""

import os
import pytest
from unittest.mock import Mock, patch

from copilot_summarization.factory import SummarizerFactory
from copilot_summarization.openai_summarizer import OpenAISummarizer
from copilot_summarization.mock_summarizer import MockSummarizer
from copilot_summarization.local_llm_summarizer import LocalLLMSummarizer
from copilot_summarization.llamacpp_summarizer import LlamaCppSummarizer


class TestSummarizerFactory:
    """Tests for SummarizerFactory."""
    
    def test_create_mock_summarizer(self):
        """Test creating a mock summarizer."""
        summarizer = SummarizerFactory.create_summarizer(provider="mock")
        assert isinstance(summarizer, MockSummarizer)
    
    def test_create_mock_summarizer_default(self):
        """Test that provider parameter is required."""
        # Provider is now required, no default
        with pytest.raises(ValueError, match="provider parameter is required"):
            SummarizerFactory.create_summarizer()
    
    def test_create_openai_summarizer(self, mock_openai_module):
        """Test creating an OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module
        
        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = SummarizerFactory.create_summarizer(
                provider="openai",
                api_key="test-key",
                model="gpt-4"
            )
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.api_key == "test-key"
            assert summarizer.model == "gpt-4"
    
    def test_create_openai_summarizer_missing_key(self):
        """Test that OpenAI summarizer requires API key."""
        with pytest.raises(ValueError, match="api_key parameter is required"):
            SummarizerFactory.create_summarizer(provider="openai", model="gpt-4")

    def test_create_openai_summarizer_missing_model(self):
        """Test that OpenAI summarizer requires model."""
        with pytest.raises(ValueError, match="model parameter is required"):
            SummarizerFactory.create_summarizer(provider="openai", api_key="test-key")
    
    def test_create_azure_summarizer(self, mock_openai_module):
        """Test creating an Azure OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module
        
        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = SummarizerFactory.create_summarizer(
                provider="azure",
                api_key="azure-key",
                base_url="https://test.openai.azure.com",
                model="gpt-4"
            )
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.api_key == "azure-key"
            assert summarizer.base_url == "https://test.openai.azure.com"
            assert summarizer.model == "gpt-4"
            assert summarizer.is_azure is True
    
    def test_create_azure_summarizer_with_deployment_name(self, mock_openai_module):
        """Test creating an Azure OpenAI summarizer with deployment name."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module
        
        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = SummarizerFactory.create_summarizer(
                provider="azure",
                api_key="azure-key",
                base_url="https://test.openai.azure.com",
                model="gpt-4",
                deployment_name="gpt-4-deployment",
                api_version="2023-12-01"
            )
            assert isinstance(summarizer, OpenAISummarizer)
            assert summarizer.deployment_name == "gpt-4-deployment"
    
    def test_create_azure_summarizer_missing_key(self):
        """Test that Azure summarizer requires API key."""
        with pytest.raises(ValueError, match="api_key parameter is required"):
            SummarizerFactory.create_summarizer(
                provider="azure",
                base_url="https://test.openai.azure.com",
                model="gpt-4"
            )
    
    def test_create_azure_summarizer_missing_endpoint(self):
        """Test that Azure summarizer requires endpoint."""
        with pytest.raises(ValueError, match="base_url parameter is required"):
            SummarizerFactory.create_summarizer(
                provider="azure",
                api_key="test-key",
                model="gpt-4"
            )

    def test_create_azure_summarizer_missing_model(self):
        """Test that Azure summarizer requires model."""
        with pytest.raises(ValueError, match="model parameter is required"):
            SummarizerFactory.create_summarizer(
                provider="azure",
                api_key="test-key",
                base_url="https://test.openai.azure.com"
            )
    
    def test_create_local_summarizer(self):
        """Test creating a local LLM summarizer."""
        summarizer = SummarizerFactory.create_summarizer(
            provider="local",
            model="llama2",
            base_url="http://localhost:8080"
        )
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.model == "llama2"
        assert summarizer.base_url == "http://localhost:8080"
    
    def test_create_local_summarizer_missing_model(self):
        """Test that local LLM summarizer requires model."""
        with pytest.raises(ValueError, match="model parameter is required"):
            SummarizerFactory.create_summarizer(provider="local", base_url="http://localhost:8080")

    def test_create_local_summarizer_missing_base_url(self):
        """Test that local LLM summarizer requires base_url."""
        with pytest.raises(ValueError, match="base_url parameter is required"):
            SummarizerFactory.create_summarizer(provider="local", model="mistral")
    
    def test_create_llamacpp_summarizer(self):
        """Test creating a llama.cpp summarizer."""
        summarizer = SummarizerFactory.create_summarizer(
            provider="llamacpp",
            model="mistral-7b-instruct-v0.2.Q4_K_M",
            base_url="http://llama-cpp:8080"
        )
        assert isinstance(summarizer, LlamaCppSummarizer)
        assert summarizer.model == "mistral-7b-instruct-v0.2.Q4_K_M"
        assert summarizer.base_url == "http://llama-cpp:8080"
    
    def test_create_llamacpp_summarizer_missing_model(self):
        """Test that llama.cpp summarizer requires model."""
        with pytest.raises(ValueError, match="model parameter is required"):
            SummarizerFactory.create_summarizer(provider="llamacpp", base_url="http://llama-cpp:8080")
    
    def test_create_llamacpp_summarizer_missing_base_url(self):
        """Test that llama.cpp summarizer requires base_url."""
        with pytest.raises(ValueError, match="base_url parameter is required"):
            SummarizerFactory.create_summarizer(provider="llamacpp", model="mistral-7b-instruct-v0.2.Q4_K_M")
    
    def test_unknown_provider(self):
        """Test that unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            SummarizerFactory.create_summarizer(provider="unknown")
    
    def test_provider_parameter_is_required(self):
        """Test that provider parameter is required."""
        with pytest.raises(ValueError, match="provider parameter is required"):
            SummarizerFactory.create_summarizer()
