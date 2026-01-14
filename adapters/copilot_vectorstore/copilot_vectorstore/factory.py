# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating vector store instances based on configuration."""

from __future__ import annotations

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.vector_store import AdapterConfig_VectorStore

from .azure_ai_search_store import AzureAISearchVectorStore
from .faiss_store import FAISSVectorStore
from .inmemory import InMemoryVectorStore
from .interface import VectorStore
from .qdrant_store import QdrantVectorStore


def create_vector_store(config: AdapterConfig_VectorStore) -> VectorStore:
    """Create a vector store instance.

    Args:
        config: Typed adapter config.

    Returns:
        VectorStore instance.
    """

    def _normalized_driver_type(c: AdapterConfig_VectorStore) -> str:
        driver_type = str(c.vector_store_type).lower()
        if driver_type in {"aisearch", "ai_search", "azure", "azureaisearch"}:
            return "azure_ai_search"
        return driver_type

    return create_adapter(
        config,
        adapter_name="vector_store",
        get_driver_type=_normalized_driver_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "inmemory": InMemoryVectorStore.from_config,
            "faiss": FAISSVectorStore.from_config,
            "qdrant": QdrantVectorStore.from_config,
            "azure_ai_search": AzureAISearchVectorStore.from_config,
        },
    )
