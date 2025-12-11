# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating vector store instances based on configuration."""

import os
import logging
from typing import Optional

from .interface import VectorStore
from .inmemory import InMemoryVectorStore
from .faiss_store import FAISSVectorStore

logger = logging.getLogger(__name__)


def create_vector_store(
    backend: Optional[str] = None,
    dimension: int = 384,
    **kwargs
) -> VectorStore:
    """Factory method to create a vector store based on configuration.
    
    The backend can be specified explicitly or via environment variable.
    Priority: function argument > env var > default (faiss)
    
    Args:
        backend: Backend type ("inmemory", "faiss", "qdrant", "azure").
                If None, reads from VECTOR_STORE_BACKEND env var.
        dimension: Dimension of embedding vectors (default: 384 for all-MiniLM-L6-v2)
        **kwargs: Additional backend-specific configuration options
        
    Returns:
        VectorStore instance
        
    Raises:
        ValueError: If backend is not supported
        
    Examples:
        >>> # Use default FAISS backend
        >>> store = create_vector_store(dimension=768)
        
        >>> # Use in-memory for testing
        >>> store = create_vector_store(backend="inmemory")
        
        >>> # Use environment variable
        >>> os.environ["VECTOR_STORE_BACKEND"] = "faiss"
        >>> store = create_vector_store(dimension=384)
    """
    # Determine backend
    if backend is None:
        backend = os.getenv("VECTOR_STORE_BACKEND", "faiss").lower()
    else:
        backend = backend.lower()
    
    logger.info(f"Creating vector store with backend='{backend}', dimension={dimension}")
    
    # Create appropriate vector store
    if backend == "inmemory":
        return InMemoryVectorStore()
    
    elif backend == "faiss":
        index_type = kwargs.get("index_type", "flat")
        persist_path = kwargs.get("persist_path")
        return FAISSVectorStore(
            dimension=dimension,
            index_type=index_type,
            persist_path=persist_path
        )
    
    elif backend == "qdrant":
        # Scaffold for future implementation
        raise NotImplementedError(
            "Qdrant backend is not yet implemented. "
            "Contributions welcome! See the VectorStore interface for requirements."
        )
    
    elif backend == "azure":
        # Scaffold for future implementation
        raise NotImplementedError(
            "Azure Cognitive Search backend is not yet implemented. "
            "Contributions welcome! See the VectorStore interface for requirements."
        )
    
    else:
        raise ValueError(
            f"Unsupported vector store backend: '{backend}'. "
            f"Supported backends: inmemory, faiss, qdrant (planned), azure (planned)"
        )
