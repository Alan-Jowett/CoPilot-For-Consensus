# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating vector store instances based on configuration."""

from __future__ import annotations

from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_AzureAiSearch,
    DriverConfig_VectorStore_Faiss,
    DriverConfig_VectorStore_Inmemory,
    DriverConfig_VectorStore_Qdrant,
)

from .azure_ai_search_store import AzureAISearchVectorStore
from .faiss_store import FAISSVectorStore
from .inmemory import InMemoryVectorStore
from .interface import VectorStore
from .qdrant_store import QdrantVectorStore

_DriverConfig: TypeAlias = (
    DriverConfig_VectorStore_AzureAiSearch
    | DriverConfig_VectorStore_Faiss
    | DriverConfig_VectorStore_Inmemory
    | DriverConfig_VectorStore_Qdrant
)


def _build_inmemory(driver_config: _DriverConfig) -> VectorStore:
    if isinstance(driver_config, DriverConfig_VectorStore_Inmemory):
        return InMemoryVectorStore.from_config(driver_config)
    raise TypeError(f"Expected inmemory config, got {type(driver_config).__name__}")


def _build_faiss(driver_config: _DriverConfig) -> VectorStore:
    if isinstance(driver_config, DriverConfig_VectorStore_Faiss):
        return FAISSVectorStore.from_config(driver_config)
    raise TypeError(f"Expected faiss config, got {type(driver_config).__name__}")


def _build_qdrant(driver_config: _DriverConfig) -> VectorStore:
    if isinstance(driver_config, DriverConfig_VectorStore_Qdrant):
        return QdrantVectorStore.from_config(driver_config)
    raise TypeError(f"Expected qdrant config, got {type(driver_config).__name__}")


def _build_azure_ai_search(driver_config: _DriverConfig) -> VectorStore:
    if isinstance(driver_config, DriverConfig_VectorStore_AzureAiSearch):
        return AzureAISearchVectorStore.from_config(driver_config)
    raise TypeError(f"Expected azure_ai_search config, got {type(driver_config).__name__}")


def create_vector_store(config: AdapterConfig_VectorStore) -> VectorStore:
    """Create a vector store instance.

    Args:
        config: Typed adapter config.

    Returns:
        VectorStore instance.
    """

    return create_adapter(
        config,
        adapter_name="vector_store",
        get_driver_type=lambda c: str(c.vector_store_type).lower(),
        get_driver_config=lambda c: c.driver,
        drivers={
            "inmemory": _build_inmemory,
            "faiss": _build_faiss,
            "qdrant": _build_qdrant,
            "azure_ai_search": _build_azure_ai_search,
        },
    )
