# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating vector store instances based on configuration."""

import os
import logging
from typing import Optional

from .interface import VectorStore
from .inmemory import InMemoryVectorStore
from .faiss_store import FAISSVectorStore
from .qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)


def create_vector_store(
    backend: Optional[str] = None,
    dimension: Optional[int] = None,
    **kwargs
) -> VectorStore:
    """Factory method to create a vector store based on configuration.
    
    All parameters must be provided explicitly - no defaults are applied.
    
    Args:
        backend: Backend type (required). Options: "inmemory", "faiss", "qdrant", "azure"
        dimension: Dimension of embedding vectors. Required for faiss and qdrant backends.
        **kwargs: Additional backend-specific configuration options
        
    Returns:
        VectorStore instance
        
    Raises:
        ValueError: If backend is not supported or required parameters are missing
        
    Examples:
        >>> # Use in-memory for testing
        >>> store = create_vector_store(backend="inmemory")
        
        >>> # Use FAISS with explicit parameters
        >>> store = create_vector_store(backend="faiss", dimension=768, index_type="flat")
        
        >>> # Use Qdrant with explicit parameters
        >>> store = create_vector_store(
        ...     backend="qdrant",
        ...     dimension=384,
        ...     host="localhost",
        ...     port=6333,
        ...     collection_name="embeddings"
        ... )
    """
    if not backend:
        raise ValueError(
            "backend parameter is required. "
            "Must be one of: inmemory, faiss, qdrant, azure"
        )
    
    backend = backend.lower()
    
    logger.info(f"Creating vector store with backend='{backend}', dimension={dimension}")
    
    # Create appropriate vector store
    if backend == "inmemory":
        return InMemoryVectorStore()
    
    elif backend == "faiss":
        if dimension is None:
            raise ValueError(
                "dimension parameter is required for FAISS backend. "
                "Specify the embedding dimension (e.g., 384, 768)"
            )
        
        index_type = kwargs.get("index_type")
        if index_type is None:
            raise ValueError(
                "index_type parameter is required for FAISS backend. "
                "Specify the index type (e.g., 'flat', 'ivf')"
            )
        
        persist_path = kwargs.get("persist_path")
        return FAISSVectorStore(
            dimension=dimension,
            index_type=index_type,
            persist_path=persist_path
        )
    
    elif backend == "qdrant":
        if dimension is None:
            raise ValueError(
                "dimension parameter is required for Qdrant backend. "
                "Specify the embedding dimension (e.g., 384, 768)"
            )
        
        # Get Qdrant configuration - all required
        host = kwargs.get("host")
        if not host:
            raise ValueError(
                "host parameter is required for Qdrant backend. "
                "Specify the Qdrant host (e.g., 'localhost')"
            )
        
        port = kwargs.get("port")
        if port is None:
            raise ValueError(
                "port parameter is required for Qdrant backend. "
                "Specify the Qdrant port (e.g., 6333)"
            )
        
        # Validate port is an integer
        if not isinstance(port, int):
            try:
                port = int(port)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid value for port: '{port}'. Must be an integer.")
        
        collection_name = kwargs.get("collection_name")
        if not collection_name:
            raise ValueError(
                "collection_name parameter is required for Qdrant backend. "
                "Specify the collection name (e.g., 'embeddings')"
            )
        
        distance = kwargs.get("distance")
        if not distance:
            raise ValueError(
                "distance parameter is required for Qdrant backend. "
                "Specify the distance metric (e.g., 'cosine', 'euclidean')"
            )
        
        upsert_batch_size = kwargs.get("upsert_batch_size")
        if upsert_batch_size is None:
            raise ValueError(
                "upsert_batch_size parameter is required for Qdrant backend. "
                "Specify the batch size for upserts (e.g., 100)"
            )
        
        # Validate batch size is an integer
        if not isinstance(upsert_batch_size, int):
            try:
                upsert_batch_size = int(upsert_batch_size)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid value for upsert_batch_size: '{upsert_batch_size}'. Must be an integer.")
        
        api_key = kwargs.get("api_key")  # Optional for Qdrant
        
        return QdrantVectorStore(
            host=host,
            port=port,
            api_key=api_key,
            collection_name=collection_name,
            vector_size=dimension,
            distance=distance,
            upsert_batch_size=upsert_batch_size,
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
