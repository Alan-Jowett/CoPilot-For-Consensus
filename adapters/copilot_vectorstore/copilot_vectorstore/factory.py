# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating vector store instances based on configuration."""

from __future__ import annotations

from typing import Any

from .azure_ai_search_store import AzureAISearchVectorStore
from .faiss_store import FAISSVectorStore
from .inmemory import InMemoryVectorStore
from .interface import VectorStore
from .qdrant_store import QdrantVectorStore


def create_vector_store(
    driver_name: str | None = None,
    driver_config: Any | None = None,
) -> VectorStore:
    """Create a vector store instance.

    Args:
        driver_name: Backend type (required). Options: "inmemory", "faiss", "qdrant", "azure_ai_search", "aisearch".
        driver_config: Backend configuration as dict-like object.

    Returns:
        VectorStore instance.

    Raises:
        ValueError: If driver_name is not provided or is unknown.
    """
    if not driver_name:
        raise ValueError(
            "driver_name is required for create_vector_store "
            "(choose: 'inmemory', 'faiss', 'qdrant', 'azure_ai_search', or 'aisearch')"
        )

    driver_lower = driver_name.lower()
    if driver_lower in {"aisearch", "ai_search", "azure", "azureaisearch", "azure_ai_search"}:
        driver_lower = "azure_ai_search"

    if driver_config is None:
        driver_config = {}

    if driver_lower == "inmemory":
        return InMemoryVectorStore.from_config(driver_config)

    if driver_lower == "faiss":
        return FAISSVectorStore.from_config(driver_config)

    if driver_lower == "qdrant":
        return QdrantVectorStore.from_config(driver_config)

    if driver_lower == "azure_ai_search":
        return AzureAISearchVectorStore.from_config(driver_config)

    raise ValueError(f"Unknown vector store driver: {driver_name}")
