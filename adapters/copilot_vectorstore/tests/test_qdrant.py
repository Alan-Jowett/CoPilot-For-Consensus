# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for QdrantVectorStore implementation."""

import pytest
from unittest.mock import Mock, MagicMock, patch

# Check if qdrant-client is available
try:
    from copilot_vectorstore import QdrantVectorStore
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


@pytest.mark.skipif(not QDRANT_AVAILABLE, reason="Qdrant client not installed")
class TestQdrantVectorStore:
    """Unit tests for QdrantVectorStore."""
    
    @patch('qdrant_client.QdrantClient')
    def test_initialization(self, mock_client_class):
        """Test that store initializes with correct parameters."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        store = QdrantVectorStore(
            host="testhost",
            port=6334,
            collection_name="test_collection",
            vector_size=128,
            distance="cosine",
        )
        
        # Verify client was created with correct parameters
        mock_client_class.assert_called_once_with(
            host="testhost",
            port=6334,
            api_key=None,
            timeout=30,
        )
        
        # Verify collection creation was attempted
        mock_client.get_collections.assert_called()
    
    @patch('qdrant_client.QdrantClient')
    def test_invalid_distance_raises_error(self, mock_client_class):
        """Test that invalid distance metric raises ValueError."""
        with pytest.raises(ValueError, match="Invalid distance metric"):
            QdrantVectorStore(distance="invalid")
    
    @patch('qdrant_client.QdrantClient')
    def test_invalid_vector_size_raises_error(self, mock_client_class):
        """Test that invalid vector size raises ValueError."""
        with pytest.raises(ValueError, match="Vector size must be positive"):
            QdrantVectorStore(vector_size=0)
        
        with pytest.raises(ValueError, match="Vector size must be positive"):
            QdrantVectorStore(vector_size=-10)
    
    @patch('qdrant_client.QdrantClient')
    def test_add_embedding_validates_dimension(self, mock_client_class):
        """Test that add_embedding validates vector dimension."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        mock_client.retrieve.return_value = []
        
        store = QdrantVectorStore(vector_size=3)
        
        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="Vector dimension"):
            store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})
    
    @patch('qdrant_client.QdrantClient')
    def test_add_embedding_success(self, mock_client_class):
        """Test successful add_embedding."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        mock_client.retrieve.return_value = []
        
        store = QdrantVectorStore(vector_size=3)
        
        store.add_embedding("doc1", [1.0, 0.0, 0.0], {"text": "hello"})
        
        # Verify upsert was called
        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        assert call_args[1]['collection_name'] == 'embeddings'
        assert len(call_args[1]['points']) == 1
    
    @patch('qdrant_client.QdrantClient')
    def test_add_embeddings_validates_lengths(self, mock_client_class):
        """Test that add_embeddings validates input lengths."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        store = QdrantVectorStore(vector_size=3)
        
        # Should raise error for mismatched lengths
        with pytest.raises(ValueError, match="same length"):
            store.add_embeddings(
                ids=["doc1", "doc2"],
                vectors=[[1.0, 0.0, 0.0]],
                metadatas=[{"text": "hello"}]
            )
    
    @patch('qdrant_client.QdrantClient')
    def test_add_embeddings_validates_dimensions(self, mock_client_class):
        """Test that add_embeddings validates vector dimensions."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        mock_client.retrieve.return_value = []
        
        store = QdrantVectorStore(vector_size=3)
        
        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="dimension"):
            store.add_embeddings(
                ids=["doc1", "doc2"],
                vectors=[[1.0, 0.0, 0.0], [1.0, 0.0]],  # Second vector wrong size
                metadatas=[{}, {}]
            )
    
    @patch('qdrant_client.QdrantClient')
    def test_add_embeddings_detects_duplicates(self, mock_client_class):
        """Test that add_embeddings detects duplicate IDs in batch."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        store = QdrantVectorStore(vector_size=3)
        
        # Should raise error for duplicate IDs
        with pytest.raises(ValueError, match="Duplicate IDs"):
            store.add_embeddings(
                ids=["doc1", "doc1"],
                vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                metadatas=[{}, {}]
            )
    
    @patch('qdrant_client.QdrantClient')
    def test_query_validates_dimension(self, mock_client_class):
        """Test that query validates vector dimension."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        store = QdrantVectorStore(vector_size=3)
        
        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="Query vector dimension"):
            store.query([1.0, 0.0], top_k=5)
    
    @patch('qdrant_client.QdrantClient')
    def test_query_returns_results(self, mock_client_class):
        """Test that query returns properly formatted results."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        # Mock search results
        mock_result = Mock()
        mock_result.id = "doc1"
        mock_result.score = 0.95
        mock_result.vector = [1.0, 0.0, 0.0]
        mock_result.payload = {"text": "hello"}
        mock_client.search.return_value = [mock_result]
        
        store = QdrantVectorStore(vector_size=3)
        results = store.query([1.0, 0.0, 0.0], top_k=5)
        
        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].metadata == {"text": "hello"}
    
    @patch('qdrant_client.QdrantClient')
    def test_delete_nonexistent_raises_error(self, mock_client_class):
        """Test that deleting nonexistent ID raises KeyError."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        mock_client.retrieve.return_value = []
        
        store = QdrantVectorStore(vector_size=3)
        
        with pytest.raises(KeyError, match="not found"):
            store.delete("nonexistent")
    
    @patch('qdrant_client.QdrantClient')
    def test_get_nonexistent_raises_error(self, mock_client_class):
        """Test that getting nonexistent ID raises KeyError."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        mock_client.retrieve.return_value = []
        
        store = QdrantVectorStore(vector_size=3)
        
        with pytest.raises(KeyError, match="not found"):
            store.get("nonexistent")
    
    @patch('qdrant_client.QdrantClient')
    def test_count_returns_collection_size(self, mock_client_class):
        """Test that count returns the correct number of points."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        # Mock collection info
        mock_collection_info = Mock()
        mock_collection_info.points_count = 42
        mock_client.get_collection.return_value = mock_collection_info
        
        store = QdrantVectorStore(vector_size=3)
        count = store.count()
        
        assert count == 42
    
    @patch('qdrant_client.QdrantClient')
    def test_clear_recreates_collection(self, mock_client_class):
        """Test that clear deletes and recreates the collection."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])
        
        store = QdrantVectorStore(vector_size=3, collection_name="test_collection")
        store.clear()
        
        # Verify delete was called
        mock_client.delete_collection.assert_called_with(collection_name="test_collection")


def test_qdrant_not_available_raises_import_error():
    """Test that importing without qdrant-client raises ImportError."""
    with patch.dict('sys.modules', {'qdrant_client': None}):
        with pytest.raises(ImportError, match="qdrant-client is not installed"):
            # Force reimport by using the module path directly
            from copilot_vectorstore.qdrant_store import QdrantVectorStore
            QdrantVectorStore()
