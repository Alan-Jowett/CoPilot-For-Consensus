# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract interface for vector store implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class SearchResult:
    """Result from a vector similarity search.

    Attributes:
        id: Unique identifier for the document/chunk
        score: Similarity score (higher is more similar)
        vector: The embedding vector
        metadata: Additional metadata associated with the document
    """
    id: str
    score: float
    vector: List[float]
    metadata: Dict[str, Any]


class VectorStore(ABC):
    """Abstract base class for vector store implementations.

    This interface defines the contract that all vector store backends
    must implement, enabling seamless switching between different backends
    (FAISS, Qdrant, Azure Cognitive Search, etc.).
    """

    @abstractmethod
    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """Add a single embedding to the vector store.

        Idempotent operation: if the ID already exists, implementations should use
        upsert semantics (update the existing embedding with new vector and metadata).

        Args:
            id: Unique identifier for this embedding
            vector: The embedding vector
            metadata: Additional metadata to store with the embedding

        Raises:
            ValueError: If vector is invalid (e.g., wrong dimensions)
        """
        pass

    @abstractmethod
    def add_embeddings(self, ids: List[str], vectors: List[List[float]],
                      metadatas: List[Dict[str, Any]]) -> None:
        """Add multiple embeddings to the vector store in batch.

        Idempotent operation: if any IDs already exist, implementations should use
        upsert semantics (update existing embeddings with new vectors and metadata).

        Args:
            ids: List of unique identifiers
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries

        Raises:
            ValueError: If lengths don't match, vectors have wrong dimensions,
                       or duplicate IDs exist within the batch
        """
        pass

    @abstractmethod
    def query(self, query_vector: List[float], top_k: int = 10) -> List[SearchResult]:
        """Query the vector store for similar embeddings.

        Args:
            query_vector: The query embedding vector
            top_k: Number of top results to return

        Returns:
            List of SearchResult objects ordered by similarity (highest first)

        Raises:
            ValueError: If query_vector dimension doesn't match stored vectors
        """
        pass

    @abstractmethod
    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.

        Args:
            id: Unique identifier of the embedding to delete

        Raises:
            KeyError: If id doesn't exist
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get the number of embeddings in the vector store.

        Returns:
            Number of embeddings currently stored
        """
        pass

    @abstractmethod
    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.

        Args:
            id: Unique identifier of the embedding

        Returns:
            SearchResult containing the embedding and metadata

        Raises:
            KeyError: If id doesn't exist
        """
        pass
