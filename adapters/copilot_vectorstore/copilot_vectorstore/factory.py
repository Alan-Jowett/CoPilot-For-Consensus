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
from .azure_ai_search_store import AzureAISearchVectorStore

logger = logging.getLogger(__name__)


def create_vector_store(
    backend: Optional[str] = None,
    dimension: Optional[int] = None,
    **kwargs
) -> VectorStore:
    """Factory method to create a vector store based on configuration.

    All parameters must be provided explicitly - no defaults are applied.

    Args:
        backend: Backend type (required). Options: "inmemory", "faiss", "qdrant", "azure_ai_search"
        dimension: Dimension of embedding vectors. Required for faiss, qdrant, and azure_ai_search backends.
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
            "Must be one of: inmemory, faiss, qdrant, azure_ai_search"
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

    elif backend == "azure_ai_search":
        if dimension is None:
            raise ValueError(
                "dimension parameter is required for Azure AI Search backend. "
                "Specify the embedding dimension (e.g., 384, 768)"
            )

        # Get Azure AI Search configuration
        endpoint = kwargs.get("endpoint")
        if not endpoint:
            raise ValueError(
                "endpoint parameter is required for Azure AI Search backend. "
                "Specify the Azure AI Search endpoint (e.g., 'https://myservice.search.windows.net')"
            )

        api_key = kwargs.get("api_key")  # Optional if using managed identity
        use_managed_identity = kwargs.get("use_managed_identity", False)

        if not use_managed_identity and not api_key:
            raise ValueError(
                "Either api_key parameter or use_managed_identity=True is required for Azure AI Search backend."
            )

        index_name = kwargs.get("index_name")
        if not index_name:
            raise ValueError(
                "index_name parameter is required for Azure AI Search backend. "
                "Specify the index name (e.g., 'embeddings')"
            )

        return AzureAISearchVectorStore(
            endpoint=endpoint,
            api_key=api_key,
            index_name=index_name,
            vector_size=dimension,
            use_managed_identity=use_managed_identity,
        )

    elif backend == "azure":
        # Legacy alias for backward compatibility
        raise NotImplementedError(
            "Backend 'azure' has been renamed to 'azure_ai_search'. "
            "Please use backend='azure_ai_search' instead."
        )

    else:
        raise ValueError(
            f"Unsupported vector store backend: '{backend}'. "
            f"Supported backends: inmemory, faiss, qdrant, azure_ai_search"
        )
