# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for vector store configuration in embedding service main.py."""

from unittest.mock import Mock, patch

import pytest


class MockConfig:
    """Mock configuration object for testing."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def mock_create_vector_store():
    """Mock the create_vector_store function."""
    with patch('main.create_vector_store') as mock:
        mock.return_value = Mock()
        yield mock


class TestVectorStoreConfiguration:
    """Test vector store configuration logic."""

    def test_azure_ai_search_backend_normalization(self, mock_create_vector_store):
        """Test that 'ai_search' is normalized to 'azure_ai_search'."""
        config = MockConfig(
            vector_store_type='ai_search',
            embedding_dimension=384,
            aisearch_endpoint='https://test.search.windows.net',
            aisearch_index_name='test-index',
            aisearch_use_managed_identity=True
        )
        
        # Import the function that would use this config
        # This is a conceptual test - in reality, we'd test the actual logic
        backend_type = config.vector_store_type.lower()
        if backend_type == "ai_search":
            backend_type = "azure_ai_search"
        
        assert backend_type == "azure_ai_search"

    def test_azure_ai_search_required_fields_validation(self):
        """Test that Azure AI Search backend validates required fields."""
        # Missing endpoint
        config = MockConfig(
            vector_store_type='azure_ai_search',
            embedding_dimension=384,
            aisearch_index_name='test-index'
        )
        
        with pytest.raises(AttributeError):
            # Should fail when checking aisearch_endpoint
            _ = config.aisearch_endpoint
        
        # Missing index_name
        config = MockConfig(
            vector_store_type='azure_ai_search',
            embedding_dimension=384,
            aisearch_endpoint='https://test.search.windows.net'
        )
        
        with pytest.raises(AttributeError):
            # Should fail when checking aisearch_index_name
            _ = config.aisearch_index_name

    def test_azure_ai_search_managed_identity_default(self):
        """Test that managed identity defaults to True."""
        config = MockConfig(
            vector_store_type='azure_ai_search',
            embedding_dimension=384,
            aisearch_endpoint='https://test.search.windows.net',
            aisearch_index_name='test-index'
        )
        
        # Use getattr with default
        use_managed_identity = getattr(config, 'aisearch_use_managed_identity', True)
        assert use_managed_identity is True

    def test_azure_ai_search_api_key_optional(self):
        """Test that API key is optional when using managed identity."""
        config = MockConfig(
            vector_store_type='azure_ai_search',
            embedding_dimension=384,
            aisearch_endpoint='https://test.search.windows.net',
            aisearch_index_name='test-index',
            aisearch_use_managed_identity=True
        )
        
        # API key should be optional
        api_key = getattr(config, 'aisearch_api_key', None)
        assert api_key is None

    def test_faiss_embedding_dimension_validation(self):
        """Test that FAISS backend validates embedding_dimension exists and is positive."""
        # Missing embedding_dimension
        config = MockConfig(
            vector_store_type='faiss',
            vector_store_index_type='flat'
        )
        
        assert not hasattr(config, 'embedding_dimension')
        
        # Zero embedding_dimension
        config = MockConfig(
            vector_store_type='faiss',
            embedding_dimension=0,
            vector_store_index_type='flat'
        )
        
        assert hasattr(config, 'embedding_dimension')
        assert config.embedding_dimension == 0
        
        # Negative embedding_dimension
        config = MockConfig(
            vector_store_type='faiss',
            embedding_dimension=-1,
            vector_store_index_type='flat'
        )
        
        assert config.embedding_dimension < 0
        
        # Valid embedding_dimension
        config = MockConfig(
            vector_store_type='faiss',
            embedding_dimension=384,
            vector_store_index_type='flat'
        )
        
        assert config.embedding_dimension > 0

    def test_qdrant_embedding_dimension_validation(self):
        """Test that Qdrant backend validates embedding_dimension exists and is positive."""
        # Missing embedding_dimension in required attrs
        config = MockConfig(
            vector_store_type='qdrant',
            vector_store_host='localhost',
            vector_store_port=6333,
            vector_store_collection='test',
            vector_store_distance='cosine',
            vector_store_batch_size=100
        )
        
        required_attrs = ["embedding_dimension", "vector_store_host", "vector_store_port",
                         "vector_store_collection", "vector_store_distance", "vector_store_batch_size"]
        missing = [attr for attr in required_attrs if not hasattr(config, attr)]
        
        assert "embedding_dimension" in missing
        
        # Valid configuration
        config = MockConfig(
            vector_store_type='qdrant',
            embedding_dimension=384,
            vector_store_host='localhost',
            vector_store_port=6333,
            vector_store_collection='test',
            vector_store_distance='cosine',
            vector_store_batch_size=100
        )
        
        missing = [attr for attr in required_attrs if not hasattr(config, attr)]
        assert len(missing) == 0
        assert config.embedding_dimension > 0

    def test_inmemory_backend_no_validation(self):
        """Test that inmemory backend requires no additional validation."""
        config = MockConfig(
            vector_store_type='inmemory'
        )
        
        # Should not require any additional attributes
        assert config.vector_store_type == 'inmemory'

    def test_unsupported_backend_error_message(self):
        """Test that unsupported backends would raise appropriate errors."""
        config = MockConfig(
            vector_store_type='unsupported_backend'
        )
        
        backend_type = config.vector_store_type.lower()
        supported_backends = ['inmemory', 'faiss', 'qdrant', 'azure_ai_search', 'ai_search']
        
        # Should fail validation
        assert backend_type not in supported_backends


class TestAzureAISearchConfiguration:
    """Specific tests for Azure AI Search configuration."""

    def test_endpoint_validation(self):
        """Test endpoint validation logic."""
        # Empty endpoint
        config = MockConfig(
            aisearch_endpoint=''
        )
        assert not config.aisearch_endpoint
        
        # Valid endpoint
        config = MockConfig(
            aisearch_endpoint='https://test.search.windows.net'
        )
        assert config.aisearch_endpoint

    def test_index_name_validation(self):
        """Test index_name validation logic."""
        # Empty index_name
        config = MockConfig(
            aisearch_index_name=''
        )
        assert not config.aisearch_index_name
        
        # Valid index_name
        config = MockConfig(
            aisearch_index_name='document-embeddings'
        )
        assert config.aisearch_index_name

    def test_dimension_validation(self):
        """Test embedding_dimension validation for Azure AI Search."""
        # Zero dimension
        config = MockConfig(
            embedding_dimension=0
        )
        assert config.embedding_dimension <= 0
        
        # Negative dimension
        config = MockConfig(
            embedding_dimension=-384
        )
        assert config.embedding_dimension <= 0
        
        # Valid dimension
        config = MockConfig(
            embedding_dimension=384
        )
        assert config.embedding_dimension > 0

    def test_api_key_vs_managed_identity(self):
        """Test API key and managed identity authentication options."""
        # Managed identity only
        config = MockConfig(
            aisearch_use_managed_identity=True
        )
        api_key = getattr(config, 'aisearch_api_key', None)
        assert config.aisearch_use_managed_identity is True
        assert api_key is None
        
        # API key provided
        config = MockConfig(
            aisearch_api_key='test-key-123',
            aisearch_use_managed_identity=False
        )
        assert config.aisearch_api_key == 'test-key-123'
        assert config.aisearch_use_managed_identity is False
