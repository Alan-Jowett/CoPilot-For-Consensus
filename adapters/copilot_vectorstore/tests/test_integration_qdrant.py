# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for Qdrant vector store against a real Qdrant instance."""

import os
import pytest
import time

from copilot_vectorstore import create_vector_store, SearchResult

# Check if qdrant-client is available
QDRANT_AVAILABLE = False
try:
    import qdrant_client
    QDRANT_AVAILABLE = True
except ImportError:
    pass


def get_qdrant_config():
    """Get Qdrant configuration from environment variables."""
    return {
        "host": os.getenv("QDRANT_HOST", "localhost"),
        "port": int(os.getenv("QDRANT_PORT", "6333")),
        "api_key": os.getenv("QDRANT_API_KEY"),
        "collection_name": os.getenv("QDRANT_COLLECTION", "test_embeddings"),
    }


@pytest.fixture(scope="module")
def qdrant_store():
    """Create and connect to a real Qdrant instance for integration tests."""
    if not QDRANT_AVAILABLE:
        pytest.skip("Qdrant client not installed - skipping integration tests")
    
    config = get_qdrant_config()
    
    # Try to create the store with retries
    max_retries = 5
    store = None
    last_error = None
    
    for i in range(max_retries):
        try:
            store = create_vector_store(
                backend="qdrant",
                dimension=384,
                **config
            )
            # Test connection by getting count
            store.count()
            break
        except Exception as e:
            last_error = e
            if i < max_retries - 1:
                print(f"Waiting for Qdrant... ({i+1}/{max_retries}): {e}")
                time.sleep(2)
    
    if store is None:
        pytest.skip(f"Could not connect to Qdrant - skipping integration tests. Last error: {last_error}")
    
    yield store
    
    # Cleanup - clear the collection
    try:
        store.clear()
    except Exception as e:
        print(f"Warning: Failed to clean up Qdrant collection: {e}")


@pytest.fixture
def clean_store(qdrant_store):
    """Ensure a clean store for each test."""
    # Clean up before test
    qdrant_store.clear()
    yield qdrant_store
    # Clean up after test
    qdrant_store.clear()


@pytest.mark.integration
@pytest.mark.skipif(not QDRANT_AVAILABLE, reason="Qdrant client not installed")
class TestQdrantIntegration:
    """Integration tests for Qdrant vector store."""
    
    def test_connection(self, qdrant_store):
        """Test that we can connect to Qdrant."""
        # Should be able to get count without error
        count = qdrant_store.count()
        assert isinstance(count, int)
    
    def test_add_and_get_embedding(self, clean_store):
        """Test adding and retrieving a single embedding."""
        vector = [0.1] * 384
        metadata = {"text": "Integration test", "source": "test"}
        
        clean_store.add_embedding("doc1", vector, metadata)
        
        result = clean_store.get("doc1")
        assert result.id == "doc1"
        # Vector may be normalized by Qdrant, so just check it's not empty and has correct dimension
        assert len(result.vector) == 384
        assert result.vector is not None
        assert result.metadata == metadata
        assert result.score == 1.0
    
    def test_add_embeddings_batch(self, clean_store):
        """Test adding multiple embeddings in batch."""
        ids = ["doc1", "doc2", "doc3"]
        vectors = [
            [1.0] + [0.0] * 383,
            [0.0, 1.0] + [0.0] * 382,
            [0.0, 0.0, 1.0] + [0.0] * 381,
        ]
        metadatas = [
            {"text": "first", "index": 0},
            {"text": "second", "index": 1},
            {"text": "third", "index": 2},
        ]
        
        clean_store.add_embeddings(ids, vectors, metadatas)
        
        assert clean_store.count() == 3
        
        # Verify each embedding
        for i, doc_id in enumerate(ids):
            result = clean_store.get(doc_id)
            assert result.id == doc_id
            assert result.metadata == metadatas[i]
    
    def test_query_returns_similar_vectors(self, clean_store):
        """Test that query returns most similar vectors."""
        # Add three embeddings
        ids = ["doc1", "doc2", "doc3"]
        vectors = [
            [1.0] + [0.0] * 383,  # Should be most similar to query
            [0.0, 1.0] + [0.0] * 382,
            [0.5, 0.5] + [0.0] * 382,
        ]
        metadatas = [
            {"text": "first"},
            {"text": "second"},
            {"text": "third"},
        ]
        
        clean_store.add_embeddings(ids, vectors, metadatas)
        
        # Query with vector similar to doc1
        query_vector = [0.9, 0.1] + [0.0] * 382
        results = clean_store.query(query_vector, top_k=2)
        
        assert len(results) == 2
        # First result should be doc1 (most similar)
        assert results[0].id == "doc1"
        assert results[0].score > results[1].score
        assert isinstance(results[0], SearchResult)
    
    def test_query_respects_top_k(self, clean_store):
        """Test that query respects top_k parameter."""
        # Add multiple embeddings
        ids = [f"doc{i}" for i in range(10)]
        vectors = [[i / 10.0] + [0.0] * 383 for i in range(10)]
        metadatas = [{"index": i} for i in range(10)]
        
        clean_store.add_embeddings(ids, vectors, metadatas)
        
        # Query with top_k=3
        query_vector = [0.5] + [0.0] * 383
        results = clean_store.query(query_vector, top_k=3)
        
        assert len(results) == 3
    
    def test_delete_embedding(self, clean_store):
        """Test deleting an embedding."""
        vector = [0.1] * 384
        clean_store.add_embedding("doc1", vector, {"text": "test"})
        
        assert clean_store.count() == 1
        
        clean_store.delete("doc1")
        
        assert clean_store.count() == 0
        
        # Should raise KeyError when trying to get deleted embedding
        with pytest.raises(KeyError):
            clean_store.get("doc1")
    
    def test_clear_removes_all_embeddings(self, clean_store):
        """Test that clear removes all embeddings."""
        # Add multiple embeddings
        ids = [f"doc{i}" for i in range(5)]
        vectors = [[i / 10.0] + [0.0] * 383 for i in range(5)]
        metadatas = [{"index": i} for i in range(5)]
        
        clean_store.add_embeddings(ids, vectors, metadatas)
        assert clean_store.count() == 5
        
        clean_store.clear()
        
        # Give Qdrant a moment to process the clear
        time.sleep(0.5)
        assert clean_store.count() == 0
    
    def test_count_accuracy(self, clean_store):
        """Test that count returns accurate number of embeddings."""
        assert clean_store.count() == 0
        
        # Add embeddings one by one
        for i in range(5):
            vector = [i / 10.0] + [0.0] * 383
            clean_store.add_embedding(f"doc{i}", vector, {"index": i})
            # Give Qdrant time to index
            time.sleep(0.1)
        
        assert clean_store.count() == 5
    
    def test_metadata_preservation(self, clean_store):
        """Test that metadata is correctly preserved."""
        metadata = {
            "text": "Integration test",
            "source": "test_file.txt",
            "timestamp": "2025-12-12T00:00:00Z",
            "tags": ["test", "integration"],
            "score": 0.95,
        }
        vector = [0.1] * 384
        
        clean_store.add_embedding("doc1", vector, metadata)
        
        result = clean_store.get("doc1")
        assert result.metadata == metadata
    
    def test_query_empty_store(self, clean_store):
        """Test querying an empty store returns empty results."""
        query_vector = [0.5] + [0.0] * 383
        results = clean_store.query(query_vector, top_k=5)
        
        assert results == []
    
    def test_add_embedding_is_idempotent(self, clean_store):
        """Test that adding duplicate ID uses upsert semantics (idempotent)."""
        vector1 = [0.1] * 384
        vector2 = [0.2] * 384
        
        # Add same ID twice - should not raise an error (upsert semantics)
        clean_store.add_embedding("doc1", vector1, {"text": "first"})
        
        # Give Qdrant time to index
        time.sleep(0.1)
        
        # Adding again should succeed (upsert)
        clean_store.add_embedding("doc1", vector2, {"text": "second"})
        
        # Verify the embedding was updated by querying
        results = clean_store.query(vector2, top_k=1)
        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].metadata["text"] == "second"

    
    def test_vector_dimension_mismatch_raises_error(self, clean_store):
        """Test that vector dimension mismatch raises ValueError."""
        # Try to add vector with wrong dimension
        with pytest.raises(ValueError, match="dimension"):
            clean_store.add_embedding("doc1", [0.1, 0.2, 0.3], {"text": "test"})
    
    def test_query_dimension_mismatch_raises_error(self, clean_store):
        """Test that query with wrong dimension raises ValueError."""
        # Add a valid embedding first
        vector = [0.1] * 384
        clean_store.add_embedding("doc1", vector, {"text": "test"})
        
        # Try to query with wrong dimension
        with pytest.raises(ValueError, match="dimension"):
            clean_store.query([0.1, 0.2, 0.3], top_k=1)
    
    def test_cosine_similarity_scoring(self, clean_store):
        """Test that cosine similarity scoring works correctly."""
        # Add two embeddings: one identical to query, one orthogonal
        ids = ["doc1", "doc2"]
        # Create normalized vectors for predictable cosine similarity
        vectors = [
            [1.0] + [0.0] * 383,  # Will have high similarity with query
            [0.0, 1.0] + [0.0] * 382,  # Will have low similarity with query
        ]
        metadatas = [{"text": "similar"}, {"text": "different"}]
        
        clean_store.add_embeddings(ids, vectors, metadatas)
        
        # Query with vector similar to doc1
        query_vector = [1.0] + [0.0] * 383
        results = clean_store.query(query_vector, top_k=2)
        
        # First result should be doc1 with high score
        assert results[0].id == "doc1"
        assert results[0].score > 0.95  # Very similar
        # Second result should be doc2 with low score
        assert results[1].id == "doc2"
        assert results[1].score < 0.1  # Orthogonal vectors
