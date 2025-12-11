# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for embedding provider factory."""

import os
import pytest
from unittest.mock import patch, Mock

from copilot_embedding.factory import create_embedding_provider
from copilot_embedding.providers import (
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
)


class TestCreateEmbeddingProvider:
    """Tests for create_embedding_provider factory function."""

    def test_create_mock_provider(self):
        """Test creating mock provider."""
        provider = create_embedding_provider(backend="mock", dimension=128)
        
        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.dimension == 128

    def test_create_mock_provider_with_env(self):
        """Test creating mock provider with environment variables."""
        with patch.dict(os.environ, {"EMBEDDING_BACKEND": "mock", "EMBEDDING_DIMENSION": "256"}):
            provider = create_embedding_provider()
            
            assert isinstance(provider, MockEmbeddingProvider)
            assert provider.dimension == 256

    def test_create_sentencetransformer_provider(self):
        """Test creating SentenceTransformer provider."""
        # Mock sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class
        
        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = create_embedding_provider(
                backend="sentencetransformers",
                model="custom-model"
            )
            
            assert isinstance(provider, SentenceTransformerEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_sentencetransformer_with_env(self):
        """Test creating SentenceTransformer provider with env vars."""
        # Mock sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class
        
        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            with patch.dict(os.environ, {
                "EMBEDDING_BACKEND": "sentencetransformers",
                "EMBEDDING_MODEL": "env-model",
                "DEVICE": "cuda"
            }):
                provider = create_embedding_provider()
                
                assert isinstance(provider, SentenceTransformerEmbeddingProvider)
                assert provider.model_name == "env-model"
                assert provider.device == "cuda"

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_openai_class.return_value = Mock()
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = create_embedding_provider(
                backend="openai",
                api_key="test-key",
                model="custom-model"
            )
            
            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.model == "custom-model"
            assert provider.is_azure is False

    def test_create_openai_with_env(self):
        """Test creating OpenAI provider with env vars."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_openai_class.return_value = Mock()
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            with patch.dict(os.environ, {
                "EMBEDDING_BACKEND": "openai",
                "OPENAI_API_KEY": "env-key",
                "EMBEDDING_MODEL": "env-model"
            }):
                provider = create_embedding_provider()
                
                assert isinstance(provider, OpenAIEmbeddingProvider)
                assert provider.model == "env-model"

    def test_create_openai_without_key_raises(self):
        """Test that creating OpenAI provider without key raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider(backend="openai")
        
        assert "api_key parameter or OPENAI_API_KEY environment variable is required" in str(exc_info.value)

    def test_create_azure_provider(self):
        """Test creating Azure OpenAI provider."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_azure_class.return_value = Mock()
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = create_embedding_provider(
                backend="azure",
                api_key="test-key",
                api_base="https://test.openai.azure.com/",
                deployment_name="test-deployment"
            )
            
            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.is_azure is True
            assert provider.deployment_name == "test-deployment"

    def test_create_azure_with_env(self):
        """Test creating Azure provider with env vars."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_azure_class.return_value = Mock()
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class
        
        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            with patch.dict(os.environ, {
                "EMBEDDING_BACKEND": "azure",
                "AZURE_OPENAI_KEY": "env-key",
                "AZURE_OPENAI_ENDPOINT": "https://env.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "env-deployment"
            }):
                provider = create_embedding_provider()
                
                assert isinstance(provider, OpenAIEmbeddingProvider)
                assert provider.is_azure is True
                assert provider.deployment_name == "env-deployment"

    def test_create_azure_without_key_raises(self):
        """Test that creating Azure provider without key raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider(
                backend="azure",
                api_base="https://test.openai.azure.com/"
            )
        
        assert "api_key parameter or AZURE_OPENAI_KEY environment variable is required" in str(exc_info.value)

    def test_create_azure_without_endpoint_raises(self):
        """Test that creating Azure provider without endpoint raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider(
                backend="azure",
                api_key="test-key"
            )
        
        assert "api_base parameter or AZURE_OPENAI_ENDPOINT environment variable is required" in str(exc_info.value)

    def test_create_huggingface_provider(self):
        """Test creating HuggingFace provider."""
        # Mock transformers and torch modules
        mock_transformers_module = Mock()
        mock_tokenizer_class = Mock()
        mock_model_class = Mock()
        mock_tokenizer_class.from_pretrained.return_value = Mock()
        mock_model_instance = Mock()
        mock_model_instance.to.return_value = mock_model_instance
        mock_model_class.from_pretrained.return_value = mock_model_instance
        mock_transformers_module.AutoTokenizer = mock_tokenizer_class
        mock_transformers_module.AutoModel = mock_model_class
        mock_torch_module = Mock()
        
        with patch.dict('sys.modules', {'transformers': mock_transformers_module, 'torch': mock_torch_module}):
            provider = create_embedding_provider(
                backend="huggingface",
                model="custom-model"
            )
            
            assert isinstance(provider, HuggingFaceEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_huggingface_with_env(self):
        """Test creating HuggingFace provider with env vars."""
        # Mock transformers and torch modules
        mock_transformers_module = Mock()
        mock_tokenizer_class = Mock()
        mock_model_class = Mock()
        mock_tokenizer_class.from_pretrained.return_value = Mock()
        mock_model_instance = Mock()
        mock_model_instance.to.return_value = mock_model_instance
        mock_model_class.from_pretrained.return_value = mock_model_instance
        mock_transformers_module.AutoTokenizer = mock_tokenizer_class
        mock_transformers_module.AutoModel = mock_model_class
        mock_torch_module = Mock()
        
        with patch.dict('sys.modules', {'transformers': mock_transformers_module, 'torch': mock_torch_module}):
            with patch.dict(os.environ, {
                "EMBEDDING_BACKEND": "huggingface",
                "EMBEDDING_MODEL": "env-model",
                "DEVICE": "cuda"
            }):
                provider = create_embedding_provider()
                
                assert isinstance(provider, HuggingFaceEmbeddingProvider)
                assert provider.model_name == "env-model"
                assert provider.device == "cuda"

    def test_unknown_backend_raises(self):
        """Test that unknown backend raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider(backend="unknown")
        
        assert "Unknown embedding backend: unknown" in str(exc_info.value)

    def test_default_backend_is_sentencetransformers(self):
        """Test that default backend is sentencetransformers."""
        # Mock sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class
        
        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = create_embedding_provider()
            
            assert isinstance(provider, SentenceTransformerEmbeddingProvider)

    def test_backend_case_insensitive(self):
        """Test that backend names are case-insensitive."""
        provider1 = create_embedding_provider(backend="MOCK")
        provider2 = create_embedding_provider(backend="Mock")
        provider3 = create_embedding_provider(backend="mock")
        
        assert isinstance(provider1, MockEmbeddingProvider)
        assert isinstance(provider2, MockEmbeddingProvider)
        assert isinstance(provider3, MockEmbeddingProvider)
