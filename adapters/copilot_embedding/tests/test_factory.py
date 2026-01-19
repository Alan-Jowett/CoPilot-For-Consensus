# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for embedding provider factory."""

import importlib.util
from unittest.mock import Mock, patch

import pytest
from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
)
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
        adapter_config = AdapterConfig_EmbeddingBackend(
            embedding_backend_type="mock",
            driver=DriverConfig_EmbeddingBackend_Mock(dimension=128),
        )
        provider = create_embedding_provider(adapter_config)

        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.dimension == 128

    def test_create_mock_provider_with_env(self):
        """Test that factory does not read configuration from environment."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

    def test_create_mock_provider_missing_dimension(self):
        """Test that creating mock provider without dimension raises error."""
        config = AdapterConfig_EmbeddingBackend(
            embedding_backend_type="mock",
            driver=DriverConfig_EmbeddingBackend_Mock(dimension=None),
        )
        with pytest.raises(ValueError, match="dimension parameter is required"):
            create_embedding_provider(config)

    def test_create_sentencetransformer_provider(self):
        """Test creating SentenceTransformer provider."""
        # Mock sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="sentencetransformers",
                    driver=DriverConfig_EmbeddingBackend_Sentencetransformers(
                        model_name="custom-model",
                        device="cpu",
                    ),
                )
            )

            assert isinstance(provider, SentenceTransformerEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_sentencetransformer_missing_model(self):
        """Test that missing optional dependencies raise ImportError."""
        if importlib.util.find_spec("sentence_transformers") is not None:
            pytest.skip("sentence_transformers is installed")

        config = AdapterConfig_EmbeddingBackend(
            embedding_backend_type="sentencetransformers",
            driver=DriverConfig_EmbeddingBackend_Sentencetransformers(
                model_name="all-MiniLM-L6-v2",
                device="cpu",
            ),
        )
        with pytest.raises(ImportError):
            create_embedding_provider(config)

    def test_create_sentencetransformer_missing_device(self):
        """Test that sentence-transformer provider is created when dependency exists."""
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_st_class.return_value = Mock()
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="sentencetransformers",
                    driver=DriverConfig_EmbeddingBackend_Sentencetransformers(
                        model_name="all-MiniLM-L6-v2",
                        device="cpu",
                    ),
                )
            )

            assert isinstance(provider, SentenceTransformerEmbeddingProvider)

    def test_create_sentencetransformer_with_env(self):
        """Test that config must be provided."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_openai_class.return_value = Mock()
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="openai",
                    driver=DriverConfig_EmbeddingBackend_Openai(
                        api_key="test-key",
                        model="custom-model",
                    ),
                )
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.model == "custom-model"
            assert provider.is_azure is False

    def test_create_openai_missing_model(self):
        """Test that OpenAI provider can be created with mocked dependency."""
        mock_openai_module = Mock()
        mock_openai_class = Mock()
        mock_openai_class.return_value = Mock()
        mock_openai_module.OpenAI = mock_openai_class
        mock_openai_module.AzureOpenAI = Mock()

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="openai",
                    driver=DriverConfig_EmbeddingBackend_Openai(
                        api_key="test-key",
                        model="text-embedding-3-small",
                    ),
                )
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_create_openai_with_env(self):
        """Test that config must be provided."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

    def test_create_azure_provider(self):
        """Test creating Azure OpenAI provider."""
        # Mock openai module
        mock_openai_module = Mock()
        mock_azure_class = Mock()
        mock_azure_class.return_value = Mock()
        mock_openai_module.OpenAI = Mock()
        mock_openai_module.AzureOpenAI = mock_azure_class

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="azure_openai",
                    driver=DriverConfig_EmbeddingBackend_AzureOpenai(
                        api_key="test-key",
                        api_base="https://test.openai.azure.com/",
                        deployment_name="test-deployment",
                    ),
                )
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.is_azure is True
            assert provider.deployment_name == "test-deployment"

    def test_create_azure_with_env(self):
        """Test that config must be provided."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

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

        with patch.dict("sys.modules", {"transformers": mock_transformers_module, "torch": mock_torch_module}):
            provider = create_embedding_provider(
                AdapterConfig_EmbeddingBackend(
                    embedding_backend_type="huggingface",
                    driver=DriverConfig_EmbeddingBackend_Huggingface(
                        model_name="custom-model",
                        device="cpu",
                    ),
                )
            )

            assert isinstance(provider, HuggingFaceEmbeddingProvider)
            assert provider.model_name == "custom-model"

    def test_create_huggingface_with_env(self):
        """Test that config must be provided."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

    def test_unknown_backend_raises(self):
        """Test that unknown backend raises ValueError."""
        cfg = AdapterConfig_EmbeddingBackend(
            embedding_backend_type="unknown",  # type: ignore[arg-type]
            driver=DriverConfig_EmbeddingBackend_Mock(dimension=128),
        )
        with pytest.raises(ValueError, match="Unknown embedding backend driver: unknown"):
            create_embedding_provider(cfg)

    def test_backend_parameter_is_required(self):
        """Test that config parameter is required."""
        with pytest.raises(ValueError, match="embedding_backend config is required"):
            create_embedding_provider(None)  # type: ignore[arg-type]

    def test_backend_case_insensitive(self):
        """Test that backend type is derived from typed config."""
        cfg = AdapterConfig_EmbeddingBackend(
            embedding_backend_type="mock",
            driver=DriverConfig_EmbeddingBackend_Mock(dimension=384),
        )
        provider = create_embedding_provider(cfg)
        assert isinstance(provider, MockEmbeddingProvider)
