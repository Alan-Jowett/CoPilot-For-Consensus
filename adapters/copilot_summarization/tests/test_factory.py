# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for SummarizerFactory."""

import os
import pytest
from copilot_summarization.factory import SummarizerFactory
from copilot_summarization.openai_summarizer import OpenAISummarizer
from copilot_summarization.mock_summarizer import MockSummarizer
from copilot_summarization.local_llm_summarizer import LocalLLMSummarizer


class TestSummarizerFactory:
    """Tests for SummarizerFactory."""
    
    def test_create_mock_summarizer(self):
        """Test creating a mock summarizer."""
        summarizer = SummarizerFactory.create_summarizer(provider="mock")
        assert isinstance(summarizer, MockSummarizer)
    
    def test_create_mock_summarizer_default(self):
        """Test that mock is the default provider."""
        # Clear environment variable if set
        old_provider = os.environ.pop("SUMMARIZER_PROVIDER", None)
        try:
            summarizer = SummarizerFactory.create_summarizer()
            assert isinstance(summarizer, MockSummarizer)
        finally:
            if old_provider:
                os.environ["SUMMARIZER_PROVIDER"] = old_provider
    
    def test_create_openai_summarizer(self):
        """Test creating an OpenAI summarizer."""
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
        # Clear environment variable if set
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="OpenAI API key required"):
                SummarizerFactory.create_summarizer(provider="openai")
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
    
    def test_create_azure_summarizer(self):
        """Test creating an Azure OpenAI summarizer."""
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
    
    def test_create_azure_summarizer_missing_key(self):
        """Test that Azure summarizer requires API key."""
        old_key = os.environ.pop("AZURE_OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Azure OpenAI API key required"):
                SummarizerFactory.create_summarizer(
                    provider="azure",
                    base_url="https://test.openai.azure.com"
                )
        finally:
            if old_key:
                os.environ["AZURE_OPENAI_API_KEY"] = old_key
    
    def test_create_azure_summarizer_missing_endpoint(self):
        """Test that Azure summarizer requires endpoint."""
        old_endpoint = os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
        try:
            with pytest.raises(ValueError, match="Azure OpenAI endpoint required"):
                SummarizerFactory.create_summarizer(
                    provider="azure",
                    api_key="test-key"
                )
        finally:
            if old_endpoint:
                os.environ["AZURE_OPENAI_ENDPOINT"] = old_endpoint
    
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
    
    def test_create_local_summarizer_defaults(self):
        """Test creating a local LLM summarizer with defaults."""
        summarizer = SummarizerFactory.create_summarizer(provider="local")
        assert isinstance(summarizer, LocalLLMSummarizer)
        assert summarizer.model == "mistral"
        assert summarizer.base_url == "http://localhost:11434"
    
    def test_unknown_provider(self):
        """Test that unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            SummarizerFactory.create_summarizer(provider="unknown")
    
    def test_provider_from_environment(self):
        """Test reading provider from environment variable."""
        old_provider = os.environ.get("SUMMARIZER_PROVIDER")
        try:
            os.environ["SUMMARIZER_PROVIDER"] = "mock"
            summarizer = SummarizerFactory.create_summarizer()
            assert isinstance(summarizer, MockSummarizer)
        finally:
            if old_provider:
                os.environ["SUMMARIZER_PROVIDER"] = old_provider
            else:
                os.environ.pop("SUMMARIZER_PROVIDER", None)
