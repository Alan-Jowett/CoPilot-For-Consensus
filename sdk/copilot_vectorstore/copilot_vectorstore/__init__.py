# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Vector store abstraction layer for Copilot-for-Consensus.

This module provides a unified interface for different vector store backends
(FAISS, Qdrant, Azure Cognitive Search, etc.) to enable backend flexibility
and simplify testing.
"""

from .interface import VectorStore, SearchResult
from .inmemory import InMemoryVectorStore
from .faiss_store import FAISSVectorStore
from .factory import create_vector_store

__all__ = [
    "VectorStore",
    "SearchResult",
    "InMemoryVectorStore",
    "FAISSVectorStore",
    "create_vector_store",
]
