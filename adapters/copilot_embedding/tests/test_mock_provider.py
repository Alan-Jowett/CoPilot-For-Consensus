# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for MockEmbeddingProvider."""

import pytest
from copilot_config.generated.adapters.embedding_backend import DriverConfig_EmbeddingBackend_Mock
from copilot_embedding.mock_provider import MockEmbeddingProvider


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider."""

    def test_initialization(self):
        """Test mock provider initialization."""
        provider = MockEmbeddingProvider(dimension=128)
        assert provider.dimension == 128

    def test_default_dimension(self):
        """Test default dimension is 384."""
        cfg = DriverConfig_EmbeddingBackend_Mock()
        provider = MockEmbeddingProvider.from_config(cfg)
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
        provider = MockEmbeddingProvider(dimension=384)

        with pytest.raises(ValueError) as exc_info:
            provider.embed(None)

        assert "cannot be None" in str(exc_info.value)

    def test_embed_with_empty_string_raises(self):
        """Test that embedding with empty string raises ValueError."""
        provider = MockEmbeddingProvider(dimension=384)

        with pytest.raises(ValueError) as exc_info:
            provider.embed("")

        assert "cannot be empty" in str(exc_info.value)

    def test_embed_with_whitespace_only_raises(self):
        """Test that embedding with whitespace-only string raises ValueError."""
        provider = MockEmbeddingProvider(dimension=384)

        with pytest.raises(ValueError) as exc_info:
            provider.embed("   ")

        assert "cannot be empty" in str(exc_info.value)

    def test_embed_with_non_string_raises(self):
        """Test that embedding with non-string input raises ValueError."""
        provider = MockEmbeddingProvider(dimension=384)

        with pytest.raises(ValueError) as exc_info:
            provider.embed(123)

        assert "must be a string" in str(exc_info.value)
