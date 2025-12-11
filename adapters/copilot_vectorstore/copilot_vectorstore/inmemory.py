# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""In-memory vector store implementation for testing."""

import numpy as np
from typing import List, Dict, Any

from .interface import VectorStore, SearchResult


class InMemoryVectorStore(VectorStore):
    """Simple in-memory vector store implementation.
    
    This implementation stores vectors in memory and uses numpy for
    similarity calculations. Ideal for testing and development.
    
    Note: This implementation is not persistent and all data is lost
    when the process terminates.
    """
    
    def __init__(self):
        """Initialize an empty in-memory vector store."""
        self._vectors: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
    
    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """Add a single embedding to the vector store.
        
        Args:
            id: Unique identifier for this embedding
            vector: The embedding vector
            metadata: Additional metadata to store with the embedding
            
        Raises:
            ValueError: If id already exists or vector is invalid
        """
        if id in self._vectors:
            raise ValueError(f"ID '{id}' already exists in the vector store")
        
        if not vector:
            raise ValueError("Vector cannot be empty")
        
        self._vectors[id] = np.array(vector, dtype=np.float32)
        self._metadata[id] = metadata.copy()
    
    def add_embeddings(self, ids: List[str], vectors: List[List[float]], 
                      metadatas: List[Dict[str, Any]]) -> None:
        """Add multiple embeddings to the vector store in batch.
        
        Args:
            ids: List of unique identifiers
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries
            
        Raises:
            ValueError: If lengths don't match or any id already exists
        """
        if not (len(ids) == len(vectors) == len(metadatas)):
            raise ValueError("ids, vectors, and metadatas must have the same length")
        
        # Check for duplicates before adding any
        for id in ids:
            if id in self._vectors:
                raise ValueError(f"ID '{id}' already exists in the vector store")
        
        # Add all embeddings
        for id, vector, metadata in zip(ids, vectors, metadatas):
            self.add_embedding(id, vector, metadata)
    
    def query(self, query_vector: List[float], top_k: int = 10) -> List[SearchResult]:
        """Query the vector store for similar embeddings.
        
        Uses cosine similarity for ranking results.
        
        Args:
            query_vector: The query embedding vector
            top_k: Number of top results to return
            
        Returns:
            List of SearchResult objects ordered by similarity (highest first)
            
        Raises:
            ValueError: If query_vector dimension doesn't match stored vectors
        """
        if not self._vectors:
            return []
        
        query_array = np.array(query_vector, dtype=np.float32)
        
        # Check dimension compatibility
        first_vector = next(iter(self._vectors.values()))
        if len(query_array) != len(first_vector):
            raise ValueError(
                f"Query vector dimension ({len(query_array)}) doesn't match "
                f"stored vectors dimension ({len(first_vector)})"
            )
        
        # Calculate cosine similarity for all vectors
        # Precompute normalized query vector for better performance
        query_norm = query_array / (np.linalg.norm(query_array) + 1e-8)
        
        similarities = []
        for embedding_id, vector in self._vectors.items():
            # Normalize stored vector for cosine similarity
            vector_norm = vector / (np.linalg.norm(vector) + 1e-8)
            similarity = np.dot(query_norm, vector_norm)
            similarities.append((embedding_id, float(similarity)))
        
        # Sort by similarity (descending) and take top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_results = similarities[:top_k]
        
        # Build SearchResult objects
        results = []
        for id, score in top_results:
            results.append(SearchResult(
                id=id,
                score=score,
                vector=self._vectors[id].tolist(),
                metadata=self._metadata[id].copy()
            ))
        
        return results
    
    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.
        
        Args:
            id: Unique identifier of the embedding to delete
            
        Raises:
            KeyError: If id doesn't exist
        """
        if id not in self._vectors:
            raise KeyError(f"ID '{id}' not found in vector store")
        
        del self._vectors[id]
        del self._metadata[id]
    
    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        self._vectors.clear()
        self._metadata.clear()
    
    def count(self) -> int:
        """Get the number of embeddings in the vector store.
        
        Returns:
            Number of embeddings currently stored
        """
        return len(self._vectors)
    
    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.
        
        Args:
            id: Unique identifier of the embedding
            
        Returns:
            SearchResult containing the embedding and metadata
            
        Raises:
            KeyError: If id doesn't exist
        """
        if id not in self._vectors:
            raise KeyError(f"ID '{id}' not found in vector store")
        
        return SearchResult(
            id=id,
            score=1.0,  # Perfect match with itself
            vector=self._vectors[id].tolist(),
            metadata=self._metadata[id].copy()
        )
