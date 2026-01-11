# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for vector store factory."""

import os

import pytest
from copilot_config import DriverConfig
from copilot_vectorstore import create_vector_store
from copilot_vectorstore.inmemory import InMemoryVectorStore

try:
    from copilot_vectorstore.faiss_store import FAISSVectorStore
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


class SimpleConfig:
    """Simple config object for testing."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        """Return None for missing attributes to allow validation in store code."""
        return None


class TestCreateVectorStore:
    """Tests for create_vector_store factory function."""

    def test_create_inmemory_store(self):
        """Test creating an in-memory store."""
        config = SimpleConfig()
        store = create_vector_store(driver_name="inmemory", driver_config=config)
        assert isinstance(store, InMemoryVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store(self):
        """Test creating a FAISS store."""
        config = SimpleConfig(dimension=128, index_type="flat")
        store = create_vector_store(
            driver_name="faiss",
            driver_config=config,
        )
        assert isinstance(store, FAISSVectorStore)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_missing_dimension(self):
        """Test that creating FAISS store without dimension raises error."""
        config = SimpleConfig(index_type="flat")
        with pytest.raises(ValueError, match="dimension is required"):
            create_vector_store(driver_name="faiss", driver_config=config)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_missing_index_type(self):
        """Test that creating FAISS store without index_type raises error."""
        config = SimpleConfig(dimension=256)
        with pytest.raises(ValueError, match="index_type is required"):
            create_vector_store(driver_name="faiss", driver_config=config)

    @pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")
    def test_create_faiss_store_with_options(self):
        """Test creating a FAISS store with custom options."""
        store = create_vector_store(
            driver_name="faiss",
            driver_config=DriverConfig(driver_name="faiss", config={"dimension": 256, "index_type": "flat"}),
        )
        assert isinstance(store, FAISSVectorStore)

    def test_backend_parameter_is_required(self):
        """Test that backend parameter is required."""
        with pytest.raises(ValueError, match="driver_name is required"):
            create_vector_store()

    def test_backend_from_env_variable(self):
        """Test that factory doesn't read from environment automatically."""
        old_value = os.environ.get("VECTOR_STORE_BACKEND")
        os.environ["VECTOR_STORE_BACKEND"] = "inmemory"

        try:
            # Should still raise error because backend parameter is required
            with pytest.raises(ValueError, match="driver_name is required"):
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
            with pytest.raises(ValueError, match="driver_name is required"):
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
        config = SimpleConfig(vector_size=384)
        with pytest.raises(ValueError, match="host is required"):
            create_vector_store(driver_name="qdrant", driver_config=config)

    def test_azure_backend_alias(self):
        """Test that legacy 'azure' backend is treated as an alias for Azure AI Search."""
        config = SimpleConfig()
        with pytest.raises(ValueError, match="vector_size is required"):
            create_vector_store(driver_name="azure", driver_config=config)

    def test_azure_ai_search_backend_requires_parameters(self):
        """Test that Azure AI Search backend requires all parameters."""
        # Should raise error about missing vector_size
        config1 = SimpleConfig()
        with pytest.raises(ValueError, match="vector_size is required"):
            create_vector_store(driver_name="azure_ai_search", driver_config=config1)

        # Should raise error about missing authentication when endpoint is None
        # (auth check happens after endpoint access, but endpoint=None and index_name=None
        # will still trigger auth validation)
        config2 = SimpleConfig(vector_size=384)
        with pytest.raises(ValueError, match="Either api_key must be provided"):
            create_vector_store(driver_name="azure_ai_search", driver_config=config2)

        # With endpoint and auth, should fail on missing index_name
        config3 = SimpleConfig(
            vector_size=384,
            endpoint="https://test.search.windows.net",
            use_managed_identity=False,
            api_key="test-key",
        )
        with pytest.raises(ValueError, match="index_name is required"):
            create_vector_store(driver_name="azure_ai_search", driver_config=config3)

        # Missing api_key when use_managed_identity is False
        config4 = SimpleConfig(
            vector_size=384,
            endpoint="https://test.search.windows.net",
            use_managed_identity=False,
            index_name="embeddings",
        )
        with pytest.raises(ValueError, match="Either api_key must be provided"):
            create_vector_store(driver_name="azure_ai_search", driver_config=config4)

    def test_unsupported_backend_raises_error(self):
        """Test that unsupported backend raises ValueError."""
        config = SimpleConfig()
        with pytest.raises(ValueError, match="Unknown vector store driver"):
            create_vector_store(driver_name="unsupported", driver_config=config)

    def test_backend_case_insensitive(self):
        """Test that backend specification is case-insensitive."""
        config = SimpleConfig()
        store1 = create_vector_store(driver_name="INMEMORY", driver_config=config)
        store2 = create_vector_store(driver_name="InMemory", driver_config=config)
        store3 = create_vector_store(driver_name="inmemory", driver_config=config)

        assert isinstance(store1, InMemoryVectorStore)
        assert isinstance(store2, InMemoryVectorStore)
        assert isinstance(store3, InMemoryVectorStore)
