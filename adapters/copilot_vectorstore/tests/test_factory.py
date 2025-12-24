# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for vector store factory."""

import os

import pytest
from copilot_vectorstore import InMemoryVectorStore, create_vector_store

try:
    from copilot_vectorstore import FAISSVectorStore
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# Check if Qdrant is available for conditional test execution
QDRANT_AVAILABLE = False
try:
    import qdrant_client
    QDRANT_AVAILABLE = True
except ImportError:
    pass


class TestCreateVectorStore:
    """Tests for create_vector_store factory function."""

    def test_create_inmemory_store(self):
        """Test creating an in-memory store."""
        store = create_vector_store(backend="inmemory")
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store(self):
        """Test creating a FAISS store."""
        store = create_vector_store(backend="faiss", dimension=128, index_type="flat")
        assert isinstance(store, FAISSVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_missing_dimension(self):
        """Test that creating FAISS store without dimension raises error."""
        with pytest.raises(ValueError, match="dimension parameter is required"):
            create_vector_store(backend="faiss", index_type="flat")

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_missing_index_type(self):
        """Test that creating FAISS store without index_type raises error."""
        with pytest.raises(ValueError, match="index_type parameter is required"):
            create_vector_store(backend="faiss", dimension=256)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_with_options(self):
        """Test creating a FAISS store with custom options."""
        store = create_vector_store(
            backend="faiss",
            dimension=256,
            index_type="flat"
        )
        assert isinstance(store, FAISSVectorStore)

    def test_backend_parameter_is_required(self):
        """Test that backend parameter is required."""
        with pytest.raises(ValueError, match="backend parameter is required"):
            create_vector_store()

    def test_backend_from_env_variable(self):
        """Test that factory doesn't read from environment automatically."""
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        os.environ["VECTOR_STORE_BACKEND"] = "inmemory"

        try:
            # Should still raise error because backend parameter is required
            with pytest.raises(ValueError, match="backend parameter is required"):
                create_vector_store()
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_BACKEND"] = old_value
            else:
                if "VECTOR_STORE_BACKEND" in os.environ:
                    del os.environ["VECTOR_STORE_BACKEND"]

    def test_explicit_backend_always_required(self):
        """Test that explicit backend parameter is always required."""
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        os.environ["VECTOR_STORE_BACKEND"] = "faiss"

        try:
            # Should raise error even though env var is set
            with pytest.raises(ValueError, match="backend parameter is required"):
                create_vector_store()
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_BACKEND"] = old_value
            else:
                if "VECTOR_STORE_BACKEND" in os.environ:
                    del os.environ["VECTOR_STORE_BACKEND"]

    def test_qdrant_backend_requires_connection(self):
        """Test that Qdrant backend requires all parameters."""
        # Should raise error about missing required parameters
        with pytest.raises(ValueError, match="host parameter is required"):
            create_vector_store(backend="qdrant", dimension=384)

    def test_azure_backend_not_implemented(self):
        """Test that legacy 'azure' backend raises NotImplementedError with helpful message."""
        with pytest.raises(NotImplementedError, match="azure_ai_search"):
            create_vector_store(backend="azure")

    def test_azure_ai_search_backend_requires_parameters(self):
        """Test that Azure AI Search backend requires all parameters."""
        # Should raise error about missing dimension
        with pytest.raises(ValueError, match="dimension parameter is required"):
            create_vector_store(backend="azure_ai_search")

        # Should raise error about missing endpoint
        with pytest.raises(ValueError, match="endpoint parameter is required"):
            create_vector_store(backend="azure_ai_search", dimension=384)

        # Should raise error about missing authentication
        with pytest.raises(ValueError, match="Either api_key parameter or use_managed_identity"):
            create_vector_store(
                backend="azure_ai_search",
                dimension=384,
                endpoint="https://test.search.windows.net",
                use_managed_identity=False
            )

        # Should raise error about missing index_name
        with pytest.raises(ValueError, match="index_name parameter is required"):
            create_vector_store(
                backend="azure_ai_search",
                dimension=384,
                endpoint="https://test.search.windows.net",
                api_key="test-key"
            )

    def test_unsupported_backend_raises_error(self):
        """Test that unsupported backend raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported vector store backend"):
            create_vector_store(backend="unsupported")

    def test_backend_case_insensitive(self):
        """Test that backend specification is case-insensitive."""
        store1 = create_vector_store(backend="INMEMORY")
        store2 = create_vector_store(backend="InMemory")
        store3 = create_vector_store(backend="inmemory")

        assert isinstance(store1, InMemoryVectorStore)
        assert isinstance(store2, InMemoryVectorStore)
        assert isinstance(store3, InMemoryVectorStore)
