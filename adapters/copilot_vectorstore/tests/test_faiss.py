# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for FAISSVectorStore implementation."""

import random

import pytest

try:
    import faiss  # type: ignore[import]  # noqa: F401
    from copilot_vectorstore.faiss_store import FAISSVectorStore
    from copilot_vectorstore.interface import SearchResult
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


@pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
class TestFAISSVectorStore:
    """Tests for FAISSVectorStore."""

    def test_initialization_flat_index(self):
        """Test initialization with flat index."""
        store = FAISSVectorStore(dimension=128, index_type="flat")
        assert store.count() == 0

    def test_initialization_invalid_dimension(self):
        """Test that invalid dimension raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            FAISSVectorStore(dimension=0)

        with pytest.raises(ValueError, match="must be positive"):
            FAISSVectorStore(dimension=-1)

    def test_initialization_invalid_index_type(self):
        """Test that invalid index type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid index_type"):
            FAISSVectorStore(dimension=128, index_type="invalid")

    def test_add_single_embedding(self):
        """Test adding a single embedding."""
        store = FAISSVectorStore(dimension=3)

        store.add_embedding(
            id="doc1",
            vector=[1.0, 0.0, 0.0],
            metadata={"text": "hello"}
        )

        assert store.count() == 1

    def test_add_duplicate_id_raises_error(self):
        """Test that adding duplicate ID raises ValueError."""
        store = FAISSVectorStore(dimension=2)

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})

        with pytest.raises(ValueError, match="already exists"):
            store.add_embedding("doc1", [0.0, 1.0], {"text": "world"})

    def test_add_wrong_dimension_raises_error(self):
        """Test that adding vector with wrong dimension raises ValueError."""
        store = FAISSVectorStore(dimension=3)

        with pytest.raises(ValueError, match="dimension"):
            store.add_embedding("doc1", [1.0, 0.0], {})  # Wrong dimension

    def test_add_embeddings_batch(self):
        """Test adding multiple embeddings in batch."""
        store = FAISSVectorStore(dimension=3)

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"],
            vectors=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0]
            ],
            metadatas=[
                {"text": "first"},
                {"text": "second"},
                {"text": "third"}
            ]
        )

        assert store.count() == 3

    def test_add_embeddings_mismatched_lengths_raises_error(self):
        """Test that mismatched lengths raise ValueError."""
        store = FAISSVectorStore(dimension=2)

        with pytest.raises(ValueError, match="same length"):
            store.add_embeddings(
                ids=["doc1", "doc2"],
                vectors=[[1.0, 0.0]],
                metadatas=[{"text": "first"}]
            )

    def test_query_empty_store(self):
        """Test querying an empty store returns empty list."""
        store = FAISSVectorStore(dimension=3)

        results = store.query([1.0, 0.0, 0.0], top_k=5)

        assert results == []

    def test_query_returns_similar_vectors(self):
        """Test that query returns most similar vectors."""
        store = FAISSVectorStore(dimension=3)

        # Add three vectors
        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"],
            vectors=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.9, 0.1, 0.0]
            ],
            metadatas=[
                {"text": "first"},
                {"text": "second"},
                {"text": "third"}
            ]
        )

        # Query with vector similar to doc1
        results = store.query([1.0, 0.0, 0.0], top_k=2)

        assert len(results) == 2
        assert results[0].id == "doc1"  # Most similar (exact match)
        assert results[0].score > results[1].score
        assert isinstance(results[0], SearchResult)

    def test_query_respects_top_k(self):
        """Test that query respects top_k parameter."""
        store = FAISSVectorStore(dimension=2)

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3", "doc4"],
            vectors=[
                [1.0, 0.0],
                [0.9, 0.1],
                [0.8, 0.2],
                [0.7, 0.3]
            ],
            metadatas=[{} for _ in range(4)]
        )

        results = store.query([1.0, 0.0], top_k=2)

        assert len(results) == 2

    def test_query_dimension_mismatch_raises_error(self):
        """Test that query with wrong dimension raises ValueError."""
        store = FAISSVectorStore(dimension=3)

        store.add_embedding("doc1", [1.0, 0.0, 0.0], {})

        with pytest.raises(ValueError, match="dimension"):
            store.query([1.0, 0.0], top_k=1)  # Wrong dimension

    def test_delete_existing_id(self):
        """Test deleting an existing embedding."""
        store = FAISSVectorStore(dimension=2)

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})
        assert store.count() == 1

        store.delete("doc1")
        assert store.count() == 0

    def test_delete_nonexistent_id_raises_error(self):
        """Test that deleting nonexistent ID raises KeyError."""
        store = FAISSVectorStore(dimension=2)

        with pytest.raises(KeyError, match="not found"):
            store.delete("nonexistent")

    def test_clear(self):
        """Test clearing all embeddings."""
        store = FAISSVectorStore(dimension=2)

        store.add_embeddings(
            ids=["doc1", "doc2", "doc3"],
            vectors=[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
            metadatas=[{}, {}, {}]
        )

        assert store.count() == 3

        store.clear()
        assert store.count() == 0

    def test_get_existing_id(self):
        """Test retrieving an embedding by ID."""
        store = FAISSVectorStore(dimension=2)

        store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})

        result = store.get("doc1")

        assert result.id == "doc1"
        assert result.vector == [1.0, 0.0]
        assert result.metadata == {"text": "hello"}
        assert result.score == 1.0

    def test_get_nonexistent_id_raises_error(self):
        """Test that getting nonexistent ID raises KeyError."""
        store = FAISSVectorStore(dimension=2)

        with pytest.raises(KeyError, match="not found"):
            store.get("nonexistent")

    def test_metadata_is_copied(self):
        """Test that metadata is copied, not referenced."""
        store = FAISSVectorStore(dimension=2)

        metadata = {"text": "hello"}
        store.add_embedding("doc1", [1.0, 0.0], metadata)

        # Modify original metadata
        metadata["text"] = "modified"

        # Retrieved metadata should be unchanged
        result = store.get("doc1")
        assert result.metadata["text"] == "hello"

    def test_distance_to_similarity_conversion(self):
        """Test that L2 distance is converted to similarity score."""
        store = FAISSVectorStore(dimension=2)

        store.add_embedding("doc1", [1.0, 0.0], {})

        # Query with exact match - should have distance 0, similarity 1.0
        results = store.query([1.0, 0.0], top_k=1)

        assert len(results) == 1
        # With L2 distance 0, score = 1/(1+0) = 1.0
        assert abs(results[0].score - 1.0) < 0.001

    def test_ivf_index_type(self):
        """Test initialization with IVF index type."""
        store = FAISSVectorStore(dimension=128, index_type="ivf")

        # Add some embeddings
        random.seed(42)  # For reproducibility
        ids = [f"doc{i}" for i in range(10)]
        vectors = [[random.random() for _ in range(128)] for _ in range(10)]
        metadatas = [{"idx": i} for i in range(10)]

        store.add_embeddings(ids, vectors, metadatas)

        assert store.count() == 10

        # Query should still work (IVF may not return all results with small dataset)
        results = store.query(vectors[0], top_k=3)
        assert len(results) >= 1  # At least one result
        assert results[0].id == "doc0"  # Should find the exact match

    def test_save_and_load(self):
        """Test saving and loading FAISS index."""
        import os
        import tempfile

        # Create a temporary file for the index
        with tempfile.NamedTemporaryFile(suffix='.faiss', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Create a store and add some data
            store = FAISSVectorStore(dimension=128, index_type="flat", persist_path=tmp_path)
            store.add_embedding("id1", [1.0] * 128, {"key": "value1"})
            store.add_embedding("id2", [2.0] * 128, {"key": "value2"})

            # Save the index
            store.save()

            # Verify file was created
            assert os.path.exists(tmp_path)

            # Create a new store and load the index
            new_store = FAISSVectorStore(dimension=128, index_type="flat", persist_path=tmp_path)
            new_store.load()

            # The index should be loaded, but metadata is not persisted
            # So count should show the FAISS index size, but queries won't work
            # without metadata
            assert new_store._index.ntotal == 2

        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_save_without_path_raises_error(self):
        """Test that save without path raises ValueError."""
        store = FAISSVectorStore(dimension=128)

        with pytest.raises(ValueError, match="No path provided"):
            store.save()

    def test_load_without_path_raises_error(self):
        """Test that load without path raises ValueError."""
        store = FAISSVectorStore(dimension=128)

        with pytest.raises(ValueError, match="No path provided"):
            store.load()
