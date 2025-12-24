# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for embedding providers."""

from unittest.mock import Mock, patch

import pytest
from copilot_embedding.providers import (
    EmbeddingProvider,
    HuggingFaceEmbeddingProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)


class TestEmbeddingProvider:
    """Tests for EmbeddingProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract base class cannot be instantiated."""
        with pytest.raises(TypeError):
            EmbeddingProvider()


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider."""

    def test_initialization(self):
        """Test mock provider initialization."""
        provider = MockEmbeddingProvider(dimension=128)
        assert provider.dimension == 128

    def test_default_dimension(self):
        """Test default dimension is 384."""
        provider = MockEmbeddingProvider()
        assert provider.dimension == 384

    def test_embed_returns_list(self):
        """Test that embed returns a list of floats."""
        provider = MockEmbeddingProvider(dimension=10)
        embedding = provider.embed("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 10
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_deterministic(self):
        """Test that same text produces same embeddings."""
        provider = MockEmbeddingProvider(dimension=10)

        embedding1 = provider.embed("test text")
        embedding2 = provider.embed("test text")

        assert embedding1 == embedding2

    def test_embed_different_texts(self):
        """Test that different texts produce different embeddings."""
        provider = MockEmbeddingProvider(dimension=10)

        embedding1 = provider.embed("text one")
        embedding2 = provider.embed("text two")

        assert embedding1 != embedding2

    def test_embed_with_none_raises(self):
        """Test that embedding with None input raises ValueError."""
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError) as exc_info:
            provider.embed(None)

        assert "cannot be None" in str(exc_info.value)

    def test_embed_with_empty_string_raises(self):
        """Test that embedding with empty string raises ValueError."""
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError) as exc_info:
            provider.embed("")

        assert "cannot be empty" in str(exc_info.value)

    def test_embed_with_whitespace_only_raises(self):
        """Test that embedding with whitespace-only string raises ValueError."""
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError) as exc_info:
            provider.embed("   ")

        assert "cannot be empty" in str(exc_info.value)

    def test_embed_with_non_string_raises(self):
        """Test that embedding with non-string input raises ValueError."""
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError) as exc_info:
            provider.embed(123)

        assert "must be a string" in str(exc_info.value)


class TestSentenceTransformerEmbeddingProvider:
    """Tests for SentenceTransformerEmbeddingProvider."""

    def test_initialization_without_library(self):
        """Test that initialization fails without sentence-transformers."""
        with patch.dict('sys.modules', {'sentence_transformers': None}):
            with pytest.raises(ImportError) as exc_info:
                SentenceTransformerEmbeddingProvider()

            assert "sentence-transformers is required" in str(exc_info.value)

    def test_initialization_with_defaults(self):
        """Test provider initialization with default parameters."""
        # Mock the sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_model = Mock()
        mock_st_class.return_value = mock_model
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = SentenceTransformerEmbeddingProvider()

            assert provider.model_name == "all-MiniLM-L6-v2"
            assert provider.device == "cpu"
            assert provider.cache_dir is None
            mock_st_class.assert_called_once_with(
                "all-MiniLM-L6-v2",
                device="cpu",
                cache_folder=None
            )

    def test_initialization_with_custom_params(self):
        """Test provider initialization with custom parameters."""
        # Mock the sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_model = Mock()
        mock_st_class.return_value = mock_model
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = SentenceTransformerEmbeddingProvider(
                model_name="custom-model",
                device="cuda",
                cache_dir="/tmp/cache"
            )

            assert provider.model_name == "custom-model"
            assert provider.device == "cuda"
            assert provider.cache_dir == "/tmp/cache"
            mock_st_class.assert_called_once_with(
                "custom-model",
                device="cuda",
                cache_folder="/tmp/cache"
            )

    def test_embed(self):
        """Test embedding generation."""
        # Mock the sentence_transformers module
        mock_st_module = Mock()
        mock_st_class = Mock()
        mock_model = Mock()
        mock_embedding = Mock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_embedding
        mock_st_class.return_value = mock_model
        mock_st_module.SentenceTransformer = mock_st_class

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            provider = SentenceTransformerEmbeddingProvider()
            embedding = provider.embed("test text")

            assert embedding == [0.1, 0.2, 0.3]
            mock_model.encode.assert_called_once_with("test text", convert_to_numpy=True)


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    def test_initialization_without_library(self):
        """Test that initialization fails without openai library."""
        with patch.dict('sys.modules', {'openai': None}):
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

        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key",
                model="text-embedding-ada-002"
            )

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

        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key",
                model="text-embedding-ada-002",
                api_base="https://test.openai.azure.com/",
                api_version="2023-05-15",
                deployment_name="test-deployment"
            )

            assert provider.is_azure is True
            assert provider.deployment_name == "test-deployment"
            mock_azure_class.assert_called_once_with(
                api_key="test-key",
                api_version="2023-05-15",
                azure_endpoint="https://test.openai.azure.com/"
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

        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            embedding = provider.embed("test text")

            assert embedding == [0.1, 0.2, 0.3]
            mock_client.embeddings.create.assert_called_once_with(
                input="test text",
                model="text-embedding-ada-002"
            )

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

        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key",
                api_base="https://test.openai.azure.com/",
                deployment_name="test-deployment"
            )
            embedding = provider.embed("test text")

            assert embedding == [0.4, 0.5, 0.6]
            mock_client.embeddings.create.assert_called_once_with(
                input="test text",
                model="test-deployment"
            )


class TestHuggingFaceEmbeddingProvider:
    """Tests for HuggingFaceEmbeddingProvider."""

    def test_initialization_without_libraries(self):
        """Test that initialization fails without required libraries."""
        with patch.dict('sys.modules', {'transformers': None, 'torch': None}):
            with pytest.raises(ImportError) as exc_info:
                HuggingFaceEmbeddingProvider()

            assert "transformers and torch are required" in str(exc_info.value)

    def test_initialization_with_defaults(self):
        """Test provider initialization with default parameters."""
        # Mock the transformers and torch modules
        mock_transformers_module = Mock()
        mock_tokenizer_class = Mock()
        mock_model_class = Mock()
        mock_tokenizer = Mock()
        mock_model = Mock()
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        mock_model_class.from_pretrained.return_value = mock_model
        mock_model.to.return_value = mock_model
        mock_transformers_module.AutoTokenizer = mock_tokenizer_class
        mock_transformers_module.AutoModel = mock_model_class

        mock_torch_module = Mock()

        with patch.dict('sys.modules', {'transformers': mock_transformers_module, 'torch': mock_torch_module}):
            provider = HuggingFaceEmbeddingProvider()

            assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
            assert provider.device == "cpu"
            mock_tokenizer_class.from_pretrained.assert_called_once()
            mock_model_class.from_pretrained.assert_called_once()

    def test_embed(self):
        """Test embedding generation."""
        # Mock the transformers and torch modules
        mock_transformers_module = Mock()
        mock_tokenizer_class = Mock()
        mock_model_class = Mock()
        mock_tokenizer = Mock()
        mock_model = Mock()
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        mock_model_class.from_pretrained.return_value = mock_model
        mock_model.to.return_value = mock_model
        mock_transformers_module.AutoTokenizer = mock_tokenizer_class
        mock_transformers_module.AutoModel = mock_model_class

        # Mock tokenizer output - needs to behave like a dict for **inputs
        mock_inputs = {'input_ids': Mock(), 'attention_mask': Mock()}
        mock_inputs_object = Mock()
        mock_inputs_object.to.return_value = mock_inputs
        mock_tokenizer.return_value = mock_inputs_object

        # Mock model output
        mock_outputs = Mock()
        mock_hidden_state = Mock()
        mock_mean = Mock()
        mock_cpu = Mock()

        # Create a mock numpy array
        mock_numpy_array = Mock()
        mock_item = Mock()
        mock_item.tolist.return_value = [0.1, 0.2, 0.3]
        mock_numpy_array.__getitem__ = Mock(return_value=mock_item)

        mock_cpu.numpy.return_value = mock_numpy_array
        mock_mean.cpu.return_value = mock_cpu
        mock_hidden_state.mean.return_value = mock_mean
        mock_outputs.last_hidden_state = mock_hidden_state
        mock_model.return_value = mock_outputs

        # Mock torch module with no_grad context manager
        mock_torch_module = Mock()

        # Create a proper context manager mock
        class MockNoGrad:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        mock_torch_module.no_grad = MockNoGrad

        with patch.dict('sys.modules', {'transformers': mock_transformers_module, 'torch': mock_torch_module}):
            provider = HuggingFaceEmbeddingProvider()
            embedding = provider.embed("test text")

            assert embedding == [0.1, 0.2, 0.3]
