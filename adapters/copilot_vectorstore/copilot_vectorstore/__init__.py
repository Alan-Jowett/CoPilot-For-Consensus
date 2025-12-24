# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Vector store abstraction layer for Copilot-for-Consensus.

This module provides a unified interface for different vector store backends
(FAISS, Qdrant, Azure Cognitive Search, etc.) to enable backend flexibility
and simplify testing.
"""

from .factory import create_vector_store
from .inmemory import InMemoryVectorStore
from .interface import SearchResult, VectorStore

# Optional imports that may not be available
try:
    from .faiss_store import FAISSVectorStore
except ImportError:
    FAISSVectorStore = None

try:
    from .qdrant_store import QdrantVectorStore
except ImportError:
    QdrantVectorStore = None

try:
    from .azure_ai_search_store import AzureAISearchVectorStore
except ImportError:
    AzureAISearchVectorStore = None

__all__ = [
    "VectorStore",
    "SearchResult",
    "InMemoryVectorStore",
    "FAISSVectorStore",
    "QdrantVectorStore",
    "AzureAISearchVectorStore",
    "create_vector_store",
]
