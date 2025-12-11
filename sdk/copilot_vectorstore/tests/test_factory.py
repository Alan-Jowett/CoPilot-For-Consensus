# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for vector store factory."""

import os
import pytest
from copilot_vectorstore import create_vector_store, InMemoryVectorStore

try:
    from copilot_vectorstore import FAISSVectorStore
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class TestCreateVectorStore:
    """Tests for create_vector_store factory function."""
    
    def test_create_inmemory_store(self):
        """Test creating an in-memory store."""
        store = create_vector_store(backend="inmemory")
        assert isinstance(store, InMemoryVectorStore)
    
    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store(self):
        """Test creating a FAISS store."""
        store = create_vector_store(backend="faiss", dimension=128)
        assert isinstance(store, FAISSVectorStore)
    
    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_with_options(self):
        """Test creating a FAISS store with custom options."""
        store = create_vector_store(
            backend="faiss",
            dimension=256,
            index_type="flat"
        )
        assert isinstance(store, FAISSVectorStore)
    
    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_default_backend_is_faiss(self):
        """Test that default backend is FAISS."""
        # Clear environment variable if set
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        if "VECTOR_STORE_BACKEND" in os.environ:
            del os.environ["VECTOR_STORE_BACKEND"]
        
        try:
            store = create_vector_store(dimension=128)
            assert isinstance(store, FAISSVectorStore)
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_BACKEND"] = old_value
    
    def test_backend_from_env_variable(self):
        """Test reading backend from environment variable."""
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        os.environ["VECTOR_STORE_BACKEND"] = "inmemory"
        
        try:
            store = create_vector_store()
            assert isinstance(store, InMemoryVectorStore)
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_BACKEND"] = old_value
            else:
                del os.environ["VECTOR_STORE_BACKEND"]
    
    def test_explicit_backend_overrides_env(self):
        """Test that explicit backend parameter overrides environment variable."""
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        os.environ["VECTOR_STORE_BACKEND"] = "faiss"
        
        try:
            store = create_vector_store(backend="inmemory")
            assert isinstance(store, InMemoryVectorStore)
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_BACKEND"] = old_value
            else:
                if "VECTOR_STORE_BACKEND" in os.environ:
                    del os.environ["VECTOR_STORE_BACKEND"]
    
    def test_qdrant_backend_not_implemented(self):
        """Test that Qdrant backend raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Qdrant"):
            create_vector_store(backend="qdrant")
    
    def test_azure_backend_not_implemented(self):
        """Test that Azure backend raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Azure"):
            create_vector_store(backend="azure")
    
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
