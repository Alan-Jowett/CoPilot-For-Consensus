# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for InMemoryVectorStore implementation."""

import pytest
from copilot_vectorstore.inmemory import InMemoryVectorStore
from copilot_vectorstore.interface import SearchResult


class TestInMemoryVectorStore:
    """Tests for InMemoryVectorStore."""

    def test_initialization(self):
        """Test that store initializes empty."""
        store = InMemoryVectorStore()
        assert store.count() == 0

    def test_add_single_embedding(self):
        """Test adding a single embedding."""
        store = InMemoryVectorStore()

        store.add_embedding(id="doc1", vector=[1.0, 0.0, 0.0], metadata={"text": "hello"})

        assert store.count() == 1

    def test_add_duplicate_id_raises_error(self):
        """Test that adding duplicate ID raises ValueError."""
        store = InMemoryVectorStore()

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})

        with pytest.raises(ValueError, match="already exists"):
            store.add_embedding("doc1", [0.0, 1.0], {"text": "world"})

    def test_add_empty_vector_raises_error(self):
        """Test that adding empty vector raises ValueError."""
        store = InMemoryVectorStore()

        with pytest.raises(ValueError, match="cannot be empty"):
            store.add_embedding("doc1", [], {})

    def test_add_embeddings_batch(self):
        """Test adding multiple embeddings in batch."""
        store = InMemoryVectorStore()

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"],
            vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            metadatas=[{"text": "first"}, {"text": "second"}, {"text": "third"}],
        )

        assert store.count() == 3

    def test_add_embeddings_mismatched_lengths_raises_error(self):
        """Test that mismatched lengths raise ValueError."""
        store = InMemoryVectorStore()

        with pytest.raises(ValueError, match="same length"):
            store.add_embeddings(ids=["doc1", "doc2"], vectors=[[1.0, 0.0]], metadatas=[{"text": "first"}])

    def test_query_empty_store(self):
        """Test querying an empty store returns empty list."""
        store = InMemoryVectorStore()

        results = store.query([1.0, 0.0, 0.0], top_k=5)

        assert results == []

    def test_query_returns_similar_vectors(self):
        """Test that query returns most similar vectors."""
        store = InMemoryVectorStore()

        # Add three vectors
        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"],
            vectors=[
                [1.0, 0.0, 0.0],  # Should be most similar to query
                [0.0, 1.0, 0.0],
                [0.5, 0.5, 0.0],
            ],
            metadatas=[{"text": "first"}, {"text": "second"}, {"text": "third"}],
        )

        # Query with vector similar to doc1
        results = store.query([0.9, 0.1, 0.0], top_k=2)

        assert len(results) == 2
        assert results[0].id == "doc1"  # Most similar
        assert results[0].score > results[1].score
        assert isinstance(results[0], SearchResult)

    def test_query_respects_top_k(self):
        """Test that query respects top_k parameter."""
        store = InMemoryVectorStore()

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3", "doc4"],
            vectors=[[1.0, 0.0], [0.9, 0.1], [0.8, 0.2], [0.7, 0.3]],
            metadatas=[{} for _ in range(4)],
        )

        results = store.query([1.0, 0.0], top_k=2)

        assert len(results) == 2

    def test_query_dimension_mismatch_raises_error(self):
        """Test that query with wrong dimension raises ValueError."""
        store = InMemoryVectorStore()

        store.add_embedding("doc1", [1.0, 0.0, 0.0], {})

        with pytest.raises(ValueError, match="dimension"):
            store.query([1.0, 0.0], top_k=1)  # Wrong dimension

    def test_delete_existing_id(self):
        """Test deleting an existing embedding."""
        store = InMemoryVectorStore()

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})
        assert store.count() == 1

        store.delete("doc1")
        assert store.count() == 0

    def test_delete_nonexistent_id_raises_error(self):
        """Test that deleting nonexistent ID raises KeyError."""
        store = InMemoryVectorStore()

        with pytest.raises(KeyError, match="not found"):
            store.delete("nonexistent")

    def test_clear(self):
        """Test clearing all embeddings."""
        store = InMemoryVectorStore()

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"], vectors=[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]], metadatas=[{}, {}, {}]
        )

        assert store.count() == 3

        store.clear()
        assert store.count() == 0

    def test_get_existing_id(self):
        """Test retrieving an embedding by ID."""
        store = InMemoryVectorStore()

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})

        result = store.get("doc1")

        assert result.id == "doc1"
        assert result.vector == [1.0, 0.0]
        assert result.metadata == {"text": "hello"}
        assert result.score == 1.0

    def test_get_nonexistent_id_raises_error(self):
        """Test that getting nonexistent ID raises KeyError."""
        store = InMemoryVectorStore()

        with pytest.raises(KeyError, match="not found"):
            store.get("nonexistent")

    def test_metadata_is_copied(self):
        """Test that metadata is copied, not referenced."""
        store = InMemoryVectorStore()

        metadata = {"text": "hello"}
        store.add_embedding("doc1", [1.0, 0.0], metadata)

        # Modify original metadata
        metadata["text"] = "modified"

        # Retrieved metadata should be unchanged
        result = store.get("doc1")
        assert result.metadata["text"] == "hello"

    def test_cosine_similarity_calculation(self):
        """Test that cosine similarity is calculated correctly."""
        store = InMemoryVectorStore()

        # Add orthogonal vectors
        store.add_embeddings(ids=["doc1", "doc2"], vectors=[[1.0, 0.0], [0.0, 1.0]], metadatas=[{}, {}])

        # Query with doc1's vector - should have perfect similarity with doc1
        results = store.query([1.0, 0.0], top_k=2)

        assert results[0].id == "doc1"
        assert abs(results[0].score - 1.0) < 0.001  # Should be very close to 1.0
        assert results[1].score < 0.1  # Orthogonal vectors should have low similarity
