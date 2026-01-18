# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for OpenAIEmbeddingProvider."""

from unittest.mock import Mock, patch

import pytest
from copilot_embedding.openai_provider import OpenAIEmbeddingProvider


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    def test_initialization_without_library(self):
        """Test that initialization fails without openai library."""
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError) as exc_info:
                OpenAIEmbeddingProvider(api_key="test-key")

            assert "openai is required" in str(exc_info.value)

    def test_initialization_openai(self):
        """Test OpenAI provider initialization."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-ada-002")

            assert provider.model == "text-embedding-ada-002"
            assert provider.is_azure is False
            mock_openai_class.assert_called_once_with(api_key="test-key")

    def test_initialization_azure(self):
        """Test Azure OpenAI provider initialization."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key",
                model="text-embedding-ada-002",
                api_base="https://test.openai.azure.com/",
                api_version="2023-05-15",
                deployment_name="test-deployment",
            )

            assert provider.is_azure is True
            assert provider.deployment_name == "test-deployment"
            mock_azure_class.assert_called_once_with(
                api_key="test-key", api_version="2023-05-15", azure_endpoint="https://test.openai.azure.com/"
            )

    def test_embed_openai(self):
        """Test embedding generation with OpenAI."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            embedding = provider.embed("test text")

            assert embedding == [0.1, 0.2, 0.3]
            mock_client.embeddings.create.assert_called_once_with(input="test text", model="text-embedding-ada-002")

    def test_embed_azure(self):
        """Test embedding generation with Azure OpenAI."""
        # Mock the openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
        mock_client.embeddings.create.return_value = mock_response
        mock_azure_class.return_value = mock_client
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key", api_base="https://test.openai.azure.com/", deployment_name="test-deployment"
            )
            embedding = provider.embed("test text")

            assert embedding == [0.4, 0.5, 0.6]
            mock_client.embeddings.create.assert_called_once_with(input="test text", model="test-deployment")
