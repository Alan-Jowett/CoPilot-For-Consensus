# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for HuggingFaceEmbeddingProvider."""

from unittest.mock import Mock, patch

import pytest
from copilot_config.load_driver_config import load_driver_config
from copilot_embedding.huggingface_provider import HuggingFaceEmbeddingProvider


class TestHuggingFaceEmbeddingProvider:
    """Tests for HuggingFaceEmbeddingProvider."""

    def test_initialization_without_libraries(self):
        """Test that initialization fails without required libraries."""
        with patch.dict('sys.modules', {'transformers': None, 'torch': None}):
            with pytest.raises(ImportError) as exc_info:
                HuggingFaceEmbeddingProvider.from_config(
                    load_driver_config(
                        "embedding",
                        "embedding_backend",
                        "huggingface",
                        fields={"model_name": "sentence-transformers/all-MiniLM-L6-v2", "device": "cpu"},
                    )
                )

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
            provider = HuggingFaceEmbeddingProvider.from_config(
                load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "huggingface",
                    fields={"model_name": "sentence-transformers/all-MiniLM-L6-v2", "device": "cpu"},
                )
            )

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
            provider = HuggingFaceEmbeddingProvider.from_config(
                load_driver_config(
                    "embedding",
                    "embedding_backend",
                    "huggingface",
                    fields={"model_name": "sentence-transformers/all-MiniLM-L6-v2", "device": "cpu"},
                )
            )
            embedding = provider.embed("test text")

            assert embedding == [0.1, 0.2, 0.3]
