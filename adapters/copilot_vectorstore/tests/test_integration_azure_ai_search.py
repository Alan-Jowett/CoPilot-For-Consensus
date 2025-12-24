# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for Azure AI Search vector store against a real Azure AI Search instance."""

import os
import time

import pytest
from copilot_vectorstore import create_vector_store

# Check if azure-search-documents is available
AZURE_AVAILABLE = False
try:
    import azure.search.documents  # type: ignore[import]  # noqa: F401
    AZURE_AVAILABLE = True
except ImportError:
    # Azure SDK not installed - integration tests will be skipped
    pass


def get_azure_config():
    """Get Azure AI Search configuration from environment variables."""
    return {
        "endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
        "api_key": os.getenv("AZURE_SEARCH_API_KEY"),
        "index_name": os.getenv("AZURE_SEARCH_INDEX_NAME", "test_embeddings"),
        "use_managed_identity": os.getenv("AZURE_USE_MANAGED_IDENTITY", "false").lower() == "true",
    }


@pytest.fixture(scope="module")
def azure_store():
    """Create and connect to a real Azure AI Search instance for integration tests."""
    if not AZURE_AVAILABLE:
        pytest.skip("Azure Search Documents not installed - skipping integration tests")

    config = get_azure_config()

    # Check if endpoint is configured
    if not config["endpoint"]:
        pytest.skip("AZURE_SEARCH_ENDPOINT not set - skipping integration tests")

    # Check authentication
    if not config["use_managed_identity"] and not config["api_key"]:
        pytest.skip("AZURE_SEARCH_API_KEY not set and managed identity not enabled - skipping integration tests")

    # Try to create the store with retries
    max_retries = 5
    store = None
    last_error = None

    for i in range(max_retries):
        try:
            store = create_vector_store(
                backend="azure_ai_search",
                dimension=384,
                **config
            )
            # Test connection by getting count
            store.count()
            break
        except Exception as e:
            last_error = e
            if i < max_retries - 1:
                print(f"Waiting for Azure AI Search... ({i+1}/{max_retries}): {e}")
                time.sleep(2)

    if store is None:
        pytest.skip(f"Could not connect to Azure AI Search - skipping integration tests. Last error: {last_error}")

    yield store

    # Cleanup - clear the index
    try:
        store.clear()
    except Exception as e:
        print(f"Warning: Failed to clean up Azure AI Search index: {e}")


@pytest.fixture
def clean_store(azure_store):
    """Ensure a clean store for each test."""
    # Clean up before test
    azure_store.clear()
    yield azure_store
    # Clean up after test
    azure_store.clear()


@pytest.mark.integration
@pytest.mark.skipif(not AZURE_AVAILABLE, reason="Azure Search Documents not installed")
class TestAzureAISearchIntegration:
    """Integration tests for Azure AI Search vector store."""

    def test_connection(self, azure_store):
        """Test that we can connect to Azure AI Search."""
        # Should be able to get count without error
        count = azure_store.count()
        assert isinstance(count, int)

    def test_add_and_get_embedding(self, clean_store):
        """Test adding and retrieving a single embedding."""
        vector = [0.1] * 384
        metadata = {"text": "Integration test", "source": "test"}

        clean_store.add_embedding("doc1", vector, metadata)

        # Give Azure AI Search time to index
        time.sleep(1)

        result = clean_store.get("doc1")

        assert result.id == "doc1"
        assert result.metadata["text"] == "Integration test"
        assert result.metadata["source"] == "test"
        assert len(result.vector) == 384

    def test_add_embeddings_batch(self, clean_store):
        """Test adding multiple embeddings in batch."""
        vectors = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        ids = ["doc1", "doc2", "doc3"]
        metadatas = [
            {"text": "First doc"},
            {"text": "Second doc"},
            {"text": "Third doc"}
        ]

        clean_store.add_embeddings(ids, vectors, metadatas)

        # Give Azure AI Search time to index
        time.sleep(2)

        assert clean_store.count() == 3

        result = clean_store.get("doc2")
        assert result.metadata["text"] == "Second doc"

    def test_query_returns_similar_vectors(self, clean_store):
        """Test querying for similar vectors."""
        # Add some vectors
        vectors = [
            [1.0, 0.0, 0.0] + [0.0] * 381,
            [0.0, 1.0, 0.0] + [0.0] * 381,
            [0.0, 0.0, 1.0] + [0.0] * 381,
        ]
        ids = ["doc1", "doc2", "doc3"]
        metadatas = [
            {"text": "First"},
            {"text": "Second"},
            {"text": "Third"}
        ]

        clean_store.add_embeddings(ids, vectors, metadatas)

        # Give Azure AI Search time to index
        time.sleep(2)

        # Query with a vector similar to doc1
        query_vector = [0.9, 0.1, 0.0] + [0.0] * 381
        results = clean_store.query(query_vector, top_k=2)

        assert len(results) >= 1
        # The most similar should be doc1
        assert results[0].id == "doc1"

    def test_query_respects_top_k(self, clean_store):
        """Test that query respects the top_k parameter."""
        # Add 5 embeddings
        vectors = [[float(i)] * 384 for i in range(5)]
        ids = [f"doc{i}" for i in range(5)]
        metadatas = [{"index": i} for i in range(5)]

        clean_store.add_embeddings(ids, vectors, metadatas)

        # Give Azure AI Search time to index
        time.sleep(2)

        query_vector = [0.0] * 384
        results = clean_store.query(query_vector, top_k=3)

        assert len(results) <= 3

    def test_delete_embedding(self, clean_store):
        """Test deleting an embedding."""
        vector = [0.1] * 384
        metadata = {"text": "To be deleted"}

        clean_store.add_embedding("doc1", vector, metadata)

        # Give Azure AI Search time to index
        time.sleep(1)

        assert clean_store.count() == 1

        clean_store.delete("doc1")

        # Give Azure AI Search time to process deletion
        time.sleep(1)

        assert clean_store.count() == 0

        with pytest.raises(KeyError):
            clean_store.get("doc1")

    def test_clear_removes_all_embeddings(self, clean_store):
        """Test that clear removes all embeddings."""
        # Add multiple embeddings
        vectors = [[float(i)] * 384 for i in range(5)]
        ids = [f"doc{i}" for i in range(5)]
        metadatas = [{"index": i} for i in range(5)]

        clean_store.add_embeddings(ids, vectors, metadatas)

        # Give Azure AI Search time to index
        time.sleep(2)

        assert clean_store.count() == 5

        clean_store.clear()

        # Give Azure AI Search time to process
        time.sleep(2)

        assert clean_store.count() == 0

    def test_count_accuracy(self, clean_store):
        """Test that count returns accurate values."""
        assert clean_store.count() == 0

        # Add 3 embeddings
        vectors = [[float(i)] * 384 for i in range(3)]
        ids = [f"doc{i}" for i in range(3)]
        metadatas = [{"index": i} for i in range(3)]

        clean_store.add_embeddings(ids, vectors, metadatas)

        # Give Azure AI Search time to index
        time.sleep(2)

        assert clean_store.count() == 3

    def test_metadata_preservation(self, clean_store):
        """Test that metadata is preserved correctly."""
        vector = [0.1] * 384
        metadata = {
            "text": "Test document",
            "source": "integration_test",
            "tags": ["test", "integration"],
            "score": 0.95,
            "nested": {"key": "value"}
        }

        clean_store.add_embedding("doc1", vector, metadata)

        # Give Azure AI Search time to index
        time.sleep(1)

        result = clean_store.get("doc1")

        # Check all metadata fields including complex types
        assert result.metadata["text"] == metadata["text"]
        assert result.metadata["source"] == metadata["source"]
        assert result.metadata["score"] == metadata["score"]
        assert result.metadata["tags"] == metadata["tags"]
        assert result.metadata["nested"] == metadata["nested"]

    def test_query_empty_store(self, clean_store):
        """Test querying an empty store returns empty results."""
        query_vector = [0.1] * 384
        results = clean_store.query(query_vector, top_k=10)

        assert results == []

    def test_add_embedding_is_idempotent(self, clean_store):
        """Test that adding the same embedding twice is idempotent (upsert)."""
        vector1 = [0.1] * 384
        metadata1 = {"text": "First version"}

        clean_store.add_embedding("doc1", vector1, metadata1)

        # Give Azure AI Search time to index
        time.sleep(1)

        assert clean_store.count() == 1

        # Update with new vector and metadata
        vector2 = [0.2] * 384
        metadata2 = {"text": "Updated version"}

        clean_store.add_embedding("doc1", vector2, metadata2)

        # Give Azure AI Search time to index
        time.sleep(1)

        # Should still have only 1 embedding
        assert clean_store.count() == 1

        # Should have updated metadata
        result = clean_store.get("doc1")
        assert result.metadata["text"] == "Updated version"

    def test_vector_dimension_mismatch_raises_error(self, clean_store):
        """Test that vector dimension mismatch raises ValueError."""
        # Try to add vector with wrong dimension
        with pytest.raises(ValueError, match="Vector dimension"):
            clean_store.add_embedding("doc1", [0.1] * 256, {"text": "Wrong dimension"})

    def test_query_dimension_mismatch_raises_error(self, clean_store):
        """Test that query with wrong dimension raises ValueError."""
        with pytest.raises(ValueError, match="Query vector dimension"):
            clean_store.query([0.1] * 256, top_k=5)
