# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all vector store drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path
import pytest

from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_AzureAiSearch,
    DriverConfig_VectorStore_Faiss,
    DriverConfig_VectorStore_Inmemory,
    DriverConfig_VectorStore_Qdrant,
)
from copilot_vectorstore.factory import create_vector_store


def get_schema_dir():
    """Get path to schemas directory."""
    return Path(__file__).parent.parent.parent.parent / "docs" / "schemas" / "configs" / "adapters"


def load_json(path):
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def _driver_config_for(driver: str):
    if driver == "inmemory":
        return DriverConfig_VectorStore_Inmemory()

    if driver == "faiss":
        return DriverConfig_VectorStore_Faiss(dimension=384, index_type="flat")

    if driver == "qdrant":
        return DriverConfig_VectorStore_Qdrant(
            host="localhost",
            port=6333,
            collection_name="test-collection",
            vector_size=384,
        )

    if driver == "azure_ai_search":
        # Keep validation happy while avoiding requiring an API key.
        return DriverConfig_VectorStore_AzureAiSearch(
            endpoint="https://test.search.windows.net",
            index_name="test-index",
            vector_size=384,
            use_managed_identity=True,
        )

    raise AssertionError(f"Unknown driver: {driver}")


class TestVectorStoreAllDrivers:
    """Test factory creation for all vector store drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "vector_store.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        
        for driver in drivers_enum:
            # Should not raise any exceptions (skip if optional dependencies are missing)
            try:
                adapter_config = AdapterConfig_VectorStore(
                    vector_store_type=driver,
                    driver=_driver_config_for(driver),
                )
                store = create_vector_store(adapter_config)
                assert store is not None, f"Failed to create vector store for driver: {driver}"
            except ImportError as e:
                pytest.skip(f"Optional dependencies for {driver} not installed: {str(e)}")

            except Exception as e:
                # Skip on connection errors or other runtime errors (e.g., service not running)
                error_str = str(e).lower()
                if any(x in error_str for x in ["connection", "refused", "connect", "timeout"]):
                    pytest.skip(f"Cannot connect to {driver} service: {type(e).__name__}")
                raise  # Re-raise other exceptions

