# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for vector store factory."""

import os

import pytest
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_AzureAiSearch,
    DriverConfig_VectorStore_Faiss,
    DriverConfig_VectorStore_Inmemory,
    DriverConfig_VectorStore_Qdrant,
)

from copilot_vectorstore import create_vector_store
from copilot_vectorstore.inmemory import InMemoryVectorStore

try:
    import faiss  # type: ignore[import]  # noqa: F401
    from copilot_vectorstore.faiss_store import FAISSVectorStore
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class TestCreateVectorStore:
    """Tests for create_vector_store factory function."""

    def test_create_inmemory_store(self):
        """Test creating an in-memory store."""
        config = AdapterConfig_VectorStore(
            vector_store_type="inmemory",
            driver=DriverConfig_VectorStore_Inmemory(),
        )
        store = create_vector_store(config)
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store(self):
        """Test creating a FAISS store."""
        config = AdapterConfig_VectorStore(
            vector_store_type="faiss",
            driver=DriverConfig_VectorStore_Faiss(dimension=128, index_type="flat"),
        )
        store = create_vector_store(config)
        assert isinstance(store, FAISSVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_invalid_dimension(self):
        """Test that schema validation rejects invalid dimension."""
        config = AdapterConfig_VectorStore(
            vector_store_type="faiss",
            driver=DriverConfig_VectorStore_Faiss(dimension=0, index_type="flat"),
        )
        with pytest.raises(ValueError, match="dimension parameter is invalid"):
            create_vector_store(config)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_invalid_index_type(self):
        """Test that schema validation rejects invalid index_type."""
        config = AdapterConfig_VectorStore(
            vector_store_type="faiss",
            driver=DriverConfig_VectorStore_Faiss(dimension=256, index_type="unsupported"),
        )
        with pytest.raises(ValueError, match="index_type parameter is invalid"):
            create_vector_store(config)

    def test_config_is_required(self):
        """Test that config parameter is required."""
        with pytest.raises(ValueError, match="vector_store config is required"):
            create_vector_store(None)  # type: ignore[arg-type]

    def test_backend_from_env_variable(self):
        """Test that factory doesn't read from environment automatically."""
        old_value = os.environ.get("VECTOR_STORE_TYPE")
        os.environ["VECTOR_STORE_TYPE"] = "inmemory"

        try:
            # Should still raise error because backend parameter is required
            with pytest.raises(ValueError, match="vector_store config is required"):
                create_vector_store(None)  # type: ignore[arg-type]
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_TYPE"] = old_value
            else:
                if "VECTOR_STORE_TYPE" in os.environ:
                    del os.environ["VECTOR_STORE_TYPE"]

    def test_explicit_backend_always_required(self):
        """Test that explicit backend parameter is always required."""
        old_value = os.environ.get("VECTOR_STORE_TYPE")
        os.environ["VECTOR_STORE_TYPE"] = "faiss"

        try:
            # Should raise error even though env var is set
            with pytest.raises(ValueError, match="vector_store config is required"):
                create_vector_store(None)  # type: ignore[arg-type]
        finally:
            # Restore environment variable
            if old_value:
                os.environ["VECTOR_STORE_TYPE"] = old_value
            else:
                if "VECTOR_STORE_TYPE" in os.environ:
                    del os.environ["VECTOR_STORE_TYPE"]

    def test_qdrant_backend_rejects_empty_host(self):
        """Test that schema validation rejects empty host for Qdrant backend."""
        config = AdapterConfig_VectorStore(
            vector_store_type="qdrant",
            driver=DriverConfig_VectorStore_Qdrant(host=""),
        )
        with pytest.raises(ValueError, match="host parameter is required"):
            create_vector_store(config)

    def test_azure_backend_alias(self, monkeypatch):
        """Test that legacy 'azure' backend is treated as an alias for Azure AI Search."""
        sentinel = object()
        monkeypatch.setattr(
            "copilot_vectorstore.factory.AzureAISearchVectorStore.from_config",
            lambda _cfg: sentinel,
        )

        config = AdapterConfig_VectorStore(
            vector_store_type="azure",
            driver=DriverConfig_VectorStore_AzureAiSearch(
                endpoint="https://test.search.windows.net",
                index_name="test-index",
                use_managed_identity=True,
            ),
        )
        assert create_vector_store(config) is sentinel

    def test_azure_ai_search_backend_requires_api_key_when_not_using_managed_identity(self):
        """Test schema-level conditional requirement for api_key."""
        config = AdapterConfig_VectorStore(
            vector_store_type="azure_ai_search",
            driver=DriverConfig_VectorStore_AzureAiSearch(
                endpoint="https://test.search.windows.net",
                index_name="embeddings",
                use_managed_identity=False,
                api_key=None,
            ),
        )
        with pytest.raises(ValueError, match="api_key parameter is required"):
            create_vector_store(config)

    def test_unsupported_backend_raises_error(self):
        """Test that unsupported backend raises ValueError."""
        config = AdapterConfig_VectorStore(
            vector_store_type="unsupported",
            driver=DriverConfig_VectorStore_Inmemory(),
        )
        with pytest.raises(ValueError, match="Unknown vector_store driver"):
            create_vector_store(config)

    def test_backend_case_insensitive(self):
        """Test that backend specification is case-insensitive."""
        store1 = create_vector_store(
            AdapterConfig_VectorStore(
                vector_store_type="INMEMORY",
                driver=DriverConfig_VectorStore_Inmemory(),
            )
        )
        store2 = create_vector_store(
            AdapterConfig_VectorStore(
                vector_store_type="InMemory",
                driver=DriverConfig_VectorStore_Inmemory(),
            )
        )
        store3 = create_vector_store(
            AdapterConfig_VectorStore(
                vector_store_type="inmemory",
                driver=DriverConfig_VectorStore_Inmemory(),
            )
        )

        assert isinstance(store1, InMemoryVectorStore)
        assert isinstance(store2, InMemoryVectorStore)
        assert isinstance(store3, InMemoryVectorStore)
