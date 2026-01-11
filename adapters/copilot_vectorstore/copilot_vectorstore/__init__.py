# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Vector store abstraction layer for Copilot-for-Consensus.

This module provides a unified interface for different vector store backends
(FAISS, Qdrant, Azure Cognitive Search, etc.) to enable backend flexibility
and simplify testing.
"""

from .factory import create_vector_store
from .interface import SearchResult, VectorStore

__all__ = [
    "VectorStore",
    "SearchResult",
    "create_vector_store",
]
