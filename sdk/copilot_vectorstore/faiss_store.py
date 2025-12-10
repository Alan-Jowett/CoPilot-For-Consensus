# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""FAISS-based vector store implementation."""

import numpy as np
from typing import List, Dict, Any, Optional
import logging

from .interface import VectorStore, SearchResult

logger = logging.getLogger(__name__)


class FAISSVectorStore(VectorStore):
    """FAISS-based vector store implementation.
    
    This implementation uses Facebook AI Similarity Search (FAISS) for
    efficient similarity search on large-scale embeddings. It's the
    default backend for production use.
    
    Args:
        dimension: Dimension of the embedding vectors
        index_type: Type of FAISS index to use ("flat" or "ivf")
        persist_path: Optional path to persist the index to disk
    """
    
    def __init__(self, dimension: int, index_type: str = "flat", 
                 persist_path: Optional[str] = None):
        """Initialize a FAISS vector store.
        
        Args:
            dimension: Dimension of the embedding vectors
            index_type: Type of FAISS index ("flat" for exact search,
                       "ivf" for approximate search on large datasets)
            persist_path: Optional path to save/load the index
            
        Raises:
            ImportError: If FAISS is not installed
            ValueError: If dimension <= 0 or index_type is invalid
        """
        try:
            import faiss
        except ImportError as e:
            raise ImportError(
                "FAISS is not installed. Install it with: pip install faiss-cpu"
            ) from e
        
        if dimension <= 0:
            raise ValueError(f"Dimension must be positive, got {dimension}")
        
        if index_type not in ["flat", "ivf"]:
            raise ValueError(f"Invalid index_type '{index_type}'. Must be 'flat' or 'ivf'")
        
        self._dimension = dimension
        self._index_type = index_type
        self._persist_path = persist_path
        self._faiss = faiss
        
        # Initialize FAISS index
        if index_type == "flat":
            # Flat index for exact search (using L2 distance)
            self._index = faiss.IndexFlatL2(dimension)
        else:
            # IVF index for approximate search
            quantizer = faiss.IndexFlatL2(dimension)
            self._index = faiss.IndexIVFFlat(quantizer, dimension, 100)
            # Train with deterministic random data for initialization
            # In production, this will be replaced by actual data during first batch add
            np.random.seed(42)
            self._index.train(np.random.rand(1000, dimension).astype('float32'))
        
        # Maintain mapping from FAISS index to our IDs and metadata
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._vectors: Dict[str, np.ndarray] = {}
        self._next_idx = 0
        
        logger.info(f"Initialized FAISS vector store with dimension={dimension}, type={index_type}")
    
    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """Add a single embedding to the vector store.
        
        Args:
            id: Unique identifier for this embedding
            vector: The embedding vector
            metadata: Additional metadata to store with the embedding
            
        Raises:
            ValueError: If id already exists or vector dimension doesn't match
        """
        if id in self._id_to_idx:
            raise ValueError(f"ID '{id}' already exists in the vector store")
        
        vec_array = np.array(vector, dtype=np.float32).reshape(1, -1)
        
        if vec_array.shape[1] != self._dimension:
            raise ValueError(
                f"Vector dimension ({vec_array.shape[1]}) doesn't match "
                f"index dimension ({self._dimension})"
            )
        
        # Add to FAISS index
        self._index.add(vec_array)
        
        # Update mappings
        idx = self._next_idx
        self._id_to_idx[id] = idx
        self._idx_to_id[idx] = id
        self._metadata[id] = metadata.copy()
        self._vectors[id] = vec_array.flatten()
        self._next_idx += 1
    
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
            if id in self._id_to_idx:
                raise ValueError(f"ID '{id}' already exists in the vector store")
        
        # Convert to numpy array for batch addition
        vec_array = np.array(vectors, dtype=np.float32)
        
        if vec_array.shape[1] != self._dimension:
            raise ValueError(
                f"Vector dimension ({vec_array.shape[1]}) doesn't match "
                f"index dimension ({self._dimension})"
            )
        
        # Add to FAISS index in batch
        self._index.add(vec_array)
        
        # Update mappings
        for i, (id, vector, metadata) in enumerate(zip(ids, vectors, metadatas)):
            idx = self._next_idx + i
            self._id_to_idx[id] = idx
            self._idx_to_id[idx] = id
            self._metadata[id] = metadata.copy()
            self._vectors[id] = np.array(vector, dtype=np.float32)
        
        self._next_idx += len(ids)
    
    def query(self, query_vector: List[float], top_k: int = 10) -> List[SearchResult]:
        """Query the vector store for similar embeddings.
        
        Uses L2 distance for similarity (lower distance = more similar).
        Converts L2 distance to a similarity score for consistency.
        
        Args:
            query_vector: The query embedding vector
            top_k: Number of top results to return
            
        Returns:
            List of SearchResult objects ordered by similarity (highest first)
            
        Raises:
            ValueError: If query_vector dimension doesn't match stored vectors
        """
        if self._index.ntotal == 0:
            return []
        
        query_array = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        
        if query_array.shape[1] != self._dimension:
            raise ValueError(
                f"Query vector dimension ({query_array.shape[1]}) doesn't match "
                f"index dimension ({self._dimension})"
            )
        
        # Search in FAISS (returns distances and indices)
        k = min(top_k, self._index.ntotal)
        distances, indices = self._index.search(query_array, k)
        
        # Build SearchResult objects
        # Convert L2 distance to similarity score: score = 1 / (1 + distance)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for missing results
                continue
            
            id = self._idx_to_id[idx]
            score = 1.0 / (1.0 + float(dist))  # Convert distance to similarity
            
            results.append(SearchResult(
                id=id,
                score=score,
                vector=self._vectors[id].tolist(),
                metadata=self._metadata[id].copy()
            ))
        
        return results
    
    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.
        
        Note: FAISS doesn't support efficient deletion, so we mark the
        ID as deleted but keep the vector in the index. A rebuild would
        be needed to reclaim space.
        
        Args:
            id: Unique identifier of the embedding to delete
            
        Raises:
            KeyError: If id doesn't exist
        """
        if id not in self._id_to_idx:
            raise KeyError(f"ID '{id}' not found in vector store")
        
        idx = self._id_to_idx[id]
        
        # Remove from mappings
        del self._id_to_idx[id]
        del self._idx_to_id[idx]
        del self._metadata[id]
        del self._vectors[id]
        
        logger.warning(
            f"Deleted ID '{id}' from mappings. Note: FAISS index still contains "
            "the vector. Consider rebuilding the index to reclaim space."
        )
    
    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        # Recreate the index
        if self._index_type == "flat":
            self._index = self._faiss.IndexFlatL2(self._dimension)
        else:
            quantizer = self._faiss.IndexFlatL2(self._dimension)
            self._index = self._faiss.IndexIVFFlat(quantizer, self._dimension, 100)
            # Train with deterministic random data for initialization
            np.random.seed(42)
            self._index.train(np.random.rand(1000, self._dimension).astype('float32'))
        
        # Clear all mappings
        self._id_to_idx.clear()
        self._idx_to_id.clear()
        self._metadata.clear()
        self._vectors.clear()
        self._next_idx = 0
    
    def count(self) -> int:
        """Get the number of embeddings in the vector store.
        
        Returns:
            Number of embeddings currently stored
        """
        return len(self._id_to_idx)
    
    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.
        
        Args:
            id: Unique identifier of the embedding
            
        Returns:
            SearchResult containing the embedding and metadata
            
        Raises:
            KeyError: If id doesn't exist
        """
        if id not in self._id_to_idx:
            raise KeyError(f"ID '{id}' not found in vector store")
        
        return SearchResult(
            id=id,
            score=1.0,  # Perfect match with itself
            vector=self._vectors[id].tolist(),
            metadata=self._metadata[id].copy()
        )
    
    def save(self, path: Optional[str] = None) -> None:
        """Save the FAISS index to disk.
        
        Args:
            path: Path to save the index. Uses persist_path if not provided.
            
        Raises:
            ValueError: If no path is provided and persist_path is not set
        """
        save_path = path or self._persist_path
        if not save_path:
            raise ValueError("No path provided for saving the index")
        
        self._faiss.write_index(self._index, save_path)
        logger.info(f"Saved FAISS index to {save_path}")
    
    def load(self, path: Optional[str] = None) -> None:
        """Load a FAISS index from disk.
        
        Args:
            path: Path to load the index from. Uses persist_path if not provided.
            
        Raises:
            ValueError: If no path is provided and persist_path is not set
        """
        load_path = path or self._persist_path
        if not load_path:
            raise ValueError("No path provided for loading the index")
        
        self._index = self._faiss.read_index(load_path)
        logger.info(f"Loaded FAISS index from {load_path}")
