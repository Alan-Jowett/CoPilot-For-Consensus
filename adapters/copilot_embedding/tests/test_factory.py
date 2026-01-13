# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for embedding provider factory."""

import os
from unittest.mock import Mock, patch

import pytest
from copilot_config import DriverConfig
from copilot_config.load_driver_config import load_driver_config
from copilot_embedding.factory import create_embedding_provider
from copilot_embedding.huggingface_provider import HuggingFaceEmbeddingProvider
from copilot_embedding.mock_provider import MockEmbeddingProvider
from copilot_embedding.openai_provider import OpenAIEmbeddingProvider
from copilot_embedding.sentence_transformer_provider import (
    SentenceTransformerEmbeddingProvider,
)


class TestCreateEmbeddingProvider:
    """Tests for create_embedding_provider factory function."""

    def test_create_mock_provider(self):
        """Test creating mock provider."""
        config = load_driver_config(
            service="embedding",
            adapter="embedding_backend",
            driver="mock",
            fields={"dimension": 128},
        )
        provider = create_embedding_provider(driver_name="mock", driver_config=config)

        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.dimension == 128

    def test_create_mock_provider_with_env(self):
        """Test that factory requires explicit driver_name parameter."""
        config = load_driver_config("embedding", "embedding_backend", "mock")
        with patch.dict(os.environ, {"EMBEDDING_BACKEND": "mock", "EMBEDDING_DIMENSION": "256"}):
            with pytest.raises(ValueError, match="driver_name parameter is required"):
                create_embedding_provider(driver_name=None, driver_config=config)

    def test_create_mock_provider_missing_dimension(self):
        """Test that creating mock provider without dimension raises error."""
        config = DriverConfig(driver_name="mock", config={}, allowed_keys={"dimension"})
        with pytest.raises(ValueError, match="dimension parameter is required"):
            create_embedding_provider(driver_name="mock", driver_config=config)

    def test_create_sentencetransformer_provider(self):
        """Test creating SentenceTransformer provider."""
        # Mock sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = create_embedding_provider(
                driver_name="sentencetransformers",
                driver_config=load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "sentencetransformers",
                    fields={"model_name": "custom-model", "device": "cpu"},
                ),
            )

            assert isinstance(provider, SentenceTransformerEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_sentencetransformer_missing_model(self):
        """Test that creating SentenceTransformer provider without model raises error."""
        config = DriverConfig(
            driver_name="sentencetransformers",
            config={"device": "cpu"},
            allowed_keys={"model_name", "device", "cache_dir"},
        )
        with pytest.raises((ValueError, ImportError)):
            create_embedding_provider(driver_name="sentencetransformers", driver_config=config)

    def test_create_sentencetransformer_missing_device(self):
        """Test that creating SentenceTransformer provider without device raises error."""
        config = DriverConfig(
            driver_name="sentencetransformers",
            config={"model_name": "all-MiniLM-L6-v2"},
            allowed_keys={"model_name", "device", "cache_dir"},
        )
        with pytest.raises((ValueError, ImportError)):
            create_embedding_provider(driver_name="sentencetransformers", driver_config=config)

    def test_create_sentencetransformer_with_env(self):
        """Test that factory doesn't read from environment automatically."""
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
                config = load_driver_config("embedding", "embedding_backend", "sentencetransformers")
                with pytest.raises(ValueError, match="driver_name parameter is required"):
                    create_embedding_provider(driver_name=None, driver_config=config)

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
                driver_name="openai",
                driver_config=load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "openai",
                    fields={"api_key": "test-key", "model": "custom-model"},
                ),
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.model == "custom-model"
            assert provider.is_azure is False

    def test_create_openai_missing_model(self):
        """Test that creating OpenAI provider without model raises error."""
        config = DriverConfig(
            driver_name="openai",
            config={"api_key": "test-key"},
            allowed_keys={"api_key", "model", "organization"},
        )
        with pytest.raises(ValueError, match="model parameter is required"):
            create_embedding_provider(driver_name="openai", driver_config=config)

    def test_create_openai_with_env(self):
        """Test that factory doesn't read from environment automatically."""
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
                config = load_driver_config("embedding", "embedding_backend", "openai")
                with pytest.raises(ValueError, match="driver_name parameter is required"):
                    create_embedding_provider(driver_name=None, driver_config=config)

    def test_create_openai_without_key_raises(self):
        """Test that creating OpenAI provider without key raises error."""
        config = DriverConfig(
            driver_name="openai",
            config={"model": "text-embedding-ada-002"},
            allowed_keys={"api_key", "model", "organization"},
        )
        with pytest.raises(ValueError, match="api_key parameter is required"):
            create_embedding_provider(driver_name="openai", driver_config=config)

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
                driver_name="azure_openai",
                driver_config=load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "azure_openai",
                    fields={
                        "api_key": "test-key",
                        "api_base": "https://test.openai.azure.com/",
                        "deployment_name": "test-deployment",
                    },
                ),
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.is_azure is True
            assert provider.deployment_name == "test-deployment"

    def test_create_azure_with_env(self):
        """Test that factory doesn't read from environment automatically."""
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
                config = load_driver_config("embedding", "embedding_backend", "azure_openai")
                with pytest.raises(ValueError, match="driver_name parameter is required"):
                    create_embedding_provider(driver_name=None, driver_config=config)

    def test_create_azure_without_key_raises(self):
        """Test that creating Azure provider without key raises error."""
        config = DriverConfig(
            driver_name="azure_openai",
            config={
                "api_base": "https://test.openai.azure.com/",
                "deployment_name": "test-deployment",
            },
            allowed_keys={"api_key", "api_base", "api_version", "deployment_name", "model"},
        )
        with pytest.raises(ValueError, match="api_key parameter is required"):
            create_embedding_provider(driver_name="azure_openai", driver_config=config)

    def test_create_azure_without_endpoint_raises(self):
        """Test that creating Azure provider without endpoint raises error."""
        config = DriverConfig(
            driver_name="azure_openai",
            config={"api_key": "test-key"},
            allowed_keys={"api_key", "api_base", "api_version", "deployment_name", "model"},
        )
        with pytest.raises(ValueError, match="api_base parameter is required"):
            create_embedding_provider(driver_name="azure_openai", driver_config=config)

    def test_create_azure_without_model_or_deployment_raises(self):
        """Test that creating Azure provider without model or deployment raises error."""
        config = DriverConfig(
            driver_name="azure_openai",
            config={
                "api_key": "test-key",
                "api_base": "https://test.openai.azure.com/",
            },
            allowed_keys={"api_key", "api_base", "api_version", "deployment_name", "model"},
        )
        with pytest.raises(ValueError, match="Either model or deployment_name parameter is required"):
            create_embedding_provider(driver_name="azure_openai", driver_config=config)

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
                driver_name="huggingface",
                driver_config=load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "huggingface",
                    fields={"model_name": "custom-model", "device": "cpu"},
                ),
            )

            assert isinstance(provider, HuggingFaceEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_huggingface_with_env(self):
        """Test that factory doesn't read from environment automatically."""
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
                config = load_driver_config("embedding", "embedding_backend", "huggingface")
                with pytest.raises(ValueError, match="driver_name parameter is required"):
                    create_embedding_provider(driver_name=None, driver_config=config)

    def test_unknown_backend_raises(self):
        """Test that unknown backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown embedding backend driver: unknown"):
            create_embedding_provider(
                driver_name="unknown",
                driver_config=DriverConfig(driver_name="unknown", config={}, allowed_keys=set()),
            )

    def test_backend_parameter_is_required(self):
        """Test that driver_name parameter is required."""
        config = load_driver_config("embedding", "embedding_backend", "mock")
        with pytest.raises(ValueError, match="driver_name parameter is required"):
            create_embedding_provider(driver_name=None, driver_config=config)

    def test_backend_case_insensitive(self):
        """Test that backend names are case-insensitive."""
        cfg = load_driver_config(
            service="embedding",
            adapter="embedding_backend",
            driver="mock",
            fields={"dimension": 384},
        )
        provider1 = create_embedding_provider(driver_name="MOCK", driver_config=cfg)
        provider2 = create_embedding_provider(driver_name="Mock", driver_config=cfg)
        provider3 = create_embedding_provider(driver_name="mock", driver_config=cfg)

        assert isinstance(provider1, MockEmbeddingProvider)
        assert isinstance(provider2, MockEmbeddingProvider)
        assert isinstance(provider3, MockEmbeddingProvider)
