# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for AzureAISearchVectorStore implementation."""

import os
from unittest.mock import Mock, patch

import pytest

# Check if azure-search-documents SDK is available
AZURE_AVAILABLE = False
try:
    import azure.search.documents  # type: ignore[import]  # noqa: F401
    from copilot_vectorstore.azure_ai_search_store import AzureAISearchVectorStore  # noqa: F401

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


@pytest.mark.skipif(not AZURE_AVAILABLE, reason="Azure Search Documents not installed")
class TestAzureAISearchVectorStore:
    """Unit tests for AzureAISearchVectorStore."""

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_initialization(self, mock_index_client_class, mock_search_client_class):
        """Test that store initializes with correct parameters."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=128)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            index_name="test_index",
            vector_size=128,
        )

        # Verify clients were created
        assert store._endpoint == "https://test.search.windows.net"
        assert store._index_name == "test_index"
        assert store._vector_size == 128

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_missing_endpoint_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that missing endpoint raises ValueError."""
        with pytest.raises(ValueError, match="endpoint parameter is required"):
            AzureAISearchVectorStore(
                endpoint="",
                api_key="test-key",
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_invalid_endpoint_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that invalid endpoint raises ValueError."""
        with pytest.raises(ValueError, match="Must start with 'https://'"):
            AzureAISearchVectorStore(
                endpoint="http://test.search.windows.net",
                api_key="test-key",
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_missing_auth_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that missing authentication raises ValueError."""
        with pytest.raises(ValueError, match="Either api_key must be provided"):
            AzureAISearchVectorStore(
                endpoint="https://test.search.windows.net",
                api_key=None,
                use_managed_identity=False,
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_invalid_vector_size_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that invalid vector size raises ValueError."""
        with pytest.raises(ValueError, match="Vector size must be positive"):
            AzureAISearchVectorStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                vector_size=0,
            )

        with pytest.raises(ValueError, match="Vector size must be positive"):
            AzureAISearchVectorStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                vector_size=-10,
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_add_embedding_validates_dimension(self, mock_index_client_class, mock_search_client_class):
        """Test that add_embedding validates vector dimension."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="Vector dimension"):
            store.add_embedding("doc1", [1.0, 0.0], {"text": "hello"})

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_add_embedding_success(self, mock_index_client_class, mock_search_client_class):
        """Test successful add_embedding."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        store.add_embedding("doc1", [1.0, 0.0, 0.0], {"text": "hello"})

        # Verify upload_documents was called
        mock_search_client.upload_documents.assert_called_once()
        call_args = mock_search_client.upload_documents.call_args
        assert len(call_args[1]['documents']) == 1
        assert call_args[1]['documents'][0]['id'] == 'doc1'

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_add_embeddings_validates_lengths(self, mock_index_client_class, mock_search_client_class):
        """Test that add_embeddings validates input lengths."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        # Should raise error for mismatched lengths
        with pytest.raises(ValueError, match="must have the same length"):
            store.add_embeddings(
                ids=["doc1", "doc2"],
                vectors=[[1.0, 0.0, 0.0]],
                metadatas=[{"text": "hello"}]
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_add_embeddings_validates_dimensions(self, mock_index_client_class, mock_search_client_class):
        """Test that add_embeddings validates vector dimensions."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="expected 3"):
            store.add_embeddings(
                ids=["doc1", "doc2"],
                vectors=[[1.0, 0.0, 0.0], [1.0, 0.0]],  # Wrong dimension for doc2
                metadatas=[{"text": "hello"}, {"text": "world"}]
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_add_embeddings_detects_duplicates(self, mock_index_client_class, mock_search_client_class):
        """Test that add_embeddings detects duplicate IDs."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        # Should raise error for duplicate IDs in batch
        with pytest.raises(ValueError, match="Duplicate IDs found"):
            store.add_embeddings(
                ids=["doc1", "doc1"],  # Duplicate IDs
                vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                metadatas=[{"text": "hello"}, {"text": "world"}]
            )

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_query_validates_dimension(self, mock_index_client_class, mock_search_client_class):
        """Test that query validates query vector dimension."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        # Should raise error for wrong dimension
        with pytest.raises(ValueError, match="Query vector dimension"):
            store.query([1.0, 0.0])

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_query_success(self, mock_index_client_class, mock_search_client_class):
        """Test successful query."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock search results
        mock_result = {
            "id": "doc1",
            "embedding": [1.0, 0.0, 0.0],
            "metadata": '{"text": "hello"}',
            "@search.score": 0.95,
        }
        mock_search_client.search.return_value = [mock_result]

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        results = store.query([1.0, 0.0, 0.0], top_k=5)

        # Verify search was called with non-null search_text
        mock_search_client.search.assert_called_once()
        call_args = mock_search_client.search.call_args
        # Ensure search_text is not None (Azure SDK requirement)
        assert call_args[1]['search_text'] is not None
        assert call_args[1]['search_text'] == ""
        # Verify vector_queries is populated
        assert 'vector_queries' in call_args[1]
        assert len(call_args[1]['vector_queries']) == 1

        # Verify results
        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].metadata["text"] == "hello"

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_delete_success(self, mock_index_client_class, mock_search_client_class):
        """Test successful delete."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock get_document to return a document (exists)
        mock_search_client.get_document.return_value = {"id": "doc1"}

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        store.delete("doc1")

        # Verify delete_documents was called
        mock_search_client.delete_documents.assert_called_once()

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_delete_nonexistent_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that deleting non-existent document raises KeyError."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock get_document to raise exception (not found)
        mock_search_client.get_document.side_effect = Exception("Document not found")

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        with pytest.raises(KeyError, match="not found"):
            store.delete("nonexistent")

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_count(self, mock_index_client_class, mock_search_client_class):
        """Test count method."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock search to return count
        mock_search_result = Mock()
        mock_search_result.get_count.return_value = 42
        mock_search_client.search.return_value = mock_search_result

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        count = store.count()

        assert count == 42

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_get_success(self, mock_index_client_class, mock_search_client_class):
        """Test successful get."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock get_document to return a document
        mock_search_client.get_document.return_value = {
            "id": "doc1",
            "embedding": [1.0, 0.0, 0.0],
            "metadata": '{"text": "hello"}',
        }

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        result = store.get("doc1")

        assert result.id == "doc1"
        assert result.score == 1.0
        assert result.metadata["text"] == "hello"

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_get_nonexistent_raises_error(self, mock_index_client_class, mock_search_client_class):
        """Test that getting non-existent document raises KeyError."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        # Mock get_document to raise exception (not found)
        mock_search_client.get_document.side_effect = Exception("Document not found")

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        with pytest.raises(KeyError, match="not found"):
            store.get("nonexistent")

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    def test_clear(self, mock_index_client_class, mock_search_client_class):
        """Test clear method."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client

        # Mock get_index to return existing index initially
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=3)]
        mock_index_client.get_index.return_value = mock_index

        store = AzureAISearchVectorStore(
            endpoint="https://test.search.windows.net",
            api_key="test-key",
            vector_size=3,
        )

        store.clear()

        # Verify delete_index and create_index were called
        mock_index_client.delete_index.assert_called_once()
        assert mock_index_client.create_index.call_count >= 1
    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_managed_identity_with_client_id(self, mock_credential_class, mock_index_client_class, mock_search_client_class):
        """Test that managed identity uses client ID from AZURE_CLIENT_ID env var."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_credential = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client
        mock_credential_class.return_value = mock_credential

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=128)]
        mock_index_client.get_index.return_value = mock_index

        # Set AZURE_CLIENT_ID environment variable
        test_client_id = "test-client-id-12345"
        with patch.dict(os.environ, {'AZURE_CLIENT_ID': test_client_id}):
            store = AzureAISearchVectorStore(
                endpoint="https://test.search.windows.net",
                index_name="test_index",
                vector_size=128,
                use_managed_identity=True,
            )

            # Verify DefaultAzureCredential was called with managed_identity_client_id
            mock_credential_class.assert_called_once_with(managed_identity_client_id=test_client_id)
            assert store._endpoint == "https://test.search.windows.net"

    @patch('azure.search.documents.SearchClient')
    @patch('azure.search.documents.indexes.SearchIndexClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_managed_identity_without_client_id(self, mock_credential_class, mock_index_client_class, mock_search_client_class):
        """Test that managed identity works without AZURE_CLIENT_ID (system-assigned)."""
        mock_index_client = Mock()
        mock_search_client = Mock()
        mock_credential = Mock()
        mock_index_client_class.return_value = mock_index_client
        mock_search_client_class.return_value = mock_search_client
        mock_credential_class.return_value = mock_credential

        # Mock get_index to return existing index
        mock_index = Mock()
        mock_index.fields = [Mock(name="embedding", vector_search_dimensions=128)]
        mock_index_client.get_index.return_value = mock_index

        # Ensure AZURE_CLIENT_ID is not set
        with patch.dict(os.environ, {}, clear=True):
            store = AzureAISearchVectorStore(
                endpoint="https://test.search.windows.net",
                index_name="test_index",
                vector_size=128,
                use_managed_identity=True,
            )

            # Verify DefaultAzureCredential was called without managed_identity_client_id
            mock_credential_class.assert_called_once_with()
            assert store._endpoint == "https://test.search.windows.net"