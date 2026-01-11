# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for SentenceTransformerEmbeddingProvider."""

from unittest.mock import Mock, patch

import pytest
from copilot_embedding.sentence_transformer_provider import (
    SentenceTransformerEmbeddingProvider,
)


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
