# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Qdrant-based vector store implementation."""

import logging
from typing import List, Dict, Any, Optional

from .interface import VectorStore, SearchResult

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    """Qdrant-based vector store implementation.
    
    This implementation uses Qdrant for efficient similarity search
    with support for metadata filtering and persistence.
    
    Args:
        host: Qdrant server host (default: "localhost")
        port: Qdrant server port (default: 6333)
        api_key: Optional API key for authentication
        collection_name: Name of the collection to use (default: "embeddings")
        vector_size: Dimension of embedding vectors (default: 384)
        distance: Distance metric ("cosine" or "euclid", default: "cosine")
        upsert_batch_size: Batch size for upsert operations (default: 100)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
        collection_name: str = "embeddings",
        vector_size: int = 384,
        distance: str = "cosine",
        upsert_batch_size: int = 100,
    ):
        """Initialize a Qdrant vector store.
        
        Args:
            host: Qdrant server host
            port: Qdrant server port
            api_key: Optional API key for authentication
            collection_name: Name of the collection to use
            vector_size: Dimension of embedding vectors
            distance: Distance metric ("cosine" or "euclid")
            upsert_batch_size: Batch size for upsert operations
            
        Raises:
            ImportError: If qdrant-client is not installed
            ValueError: If distance is not "cosine" or "euclid"
            ConnectionError: If cannot connect to Qdrant server
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
        except ImportError as e:
            raise ImportError(
                "qdrant-client is not installed. Install it with: pip install qdrant-client"
            ) from e
        
        if distance not in ["cosine", "euclid"]:
            raise ValueError(f"Invalid distance metric '{distance}'. Must be 'cosine' or 'euclid'")
        
        if vector_size <= 0:
            raise ValueError(f"Vector size must be positive, got {vector_size}")
        
        self._host = host
        self._port = port
        self._api_key = api_key
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._distance = distance
        self._upsert_batch_size = upsert_batch_size
        
        # Store imports for later use
        self._Distance = Distance
        self._VectorParams = VectorParams
        self._PointStruct = PointStruct
        
        # Initialize Qdrant client
        try:
            self._client = QdrantClient(
                host=host,
                port=port,
                api_key=api_key,
                timeout=30,
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Qdrant at {host}:{port}. Error: {e}"
            ) from e
        
        # Ensure collection exists
        self._ensure_collection()
        
        logger.info(
            f"Initialized Qdrant vector store: collection={collection_name}, "
            f"host={host}:{port}, vector_size={vector_size}, distance={distance}"
        )
    
    def _ensure_collection(self) -> None:
        """Ensure the collection exists, create it if not."""
        try:
            # Check if collection exists
            collections = self._client.get_collections().collections
            collection_exists = any(c.name == self._collection_name for c in collections)
            
            if collection_exists:
                # Verify collection configuration matches
                collection_info = self._client.get_collection(self._collection_name)
                if collection_info.config.params.vectors.size != self._vector_size:
                    raise ValueError(
                        f"Collection '{self._collection_name}' exists with different vector size: "
                        f"expected {self._vector_size}, found {collection_info.config.params.vectors.size}"
                    )
                logger.info(f"Using existing collection '{self._collection_name}'")
            else:
                # Create collection
                distance_map = {
                    "cosine": self._Distance.COSINE,
                    "euclid": self._Distance.EUCLID,
                }
                
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=self._VectorParams(
                        size=self._vector_size,
                        distance=distance_map[self._distance],
                    ),
                )
                logger.info(f"Created new collection '{self._collection_name}'")
        except Exception as e:
            if "exists" not in str(e).lower():
                raise
    
    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """Add a single embedding to the vector store.
        
        Args:
            id: Unique identifier for this embedding
            vector: The embedding vector
            metadata: Additional metadata to store with the embedding
            
        Raises:
            ValueError: If vector dimension doesn't match or id already exists
        """
        if len(vector) != self._vector_size:
            raise ValueError(
                f"Vector dimension ({len(vector)}) doesn't match "
                f"expected dimension ({self._vector_size})"
            )
        
        # Check if ID already exists
        try:
            existing = self._client.retrieve(
                collection_name=self._collection_name,
                ids=[id],
            )
            if existing:
                raise ValueError(f"ID '{id}' already exists in the vector store")
        except Exception as e:
            # If error is not about non-existent point, re-raise
            if "not found" not in str(e).lower() and "does not exist" not in str(e).lower():
                # Only raise if it's actually a duplicate error
                if "already exists" in str(e).lower():
                    raise ValueError(f"ID '{id}' already exists in the vector store") from e
        
        # Add the point
        point = self._PointStruct(
            id=id,
            vector=vector,
            payload=metadata,
        )
        
        self._client.upsert(
            collection_name=self._collection_name,
            points=[point],
        )
    
    def add_embeddings(self, ids: List[str], vectors: List[List[float]], 
                      metadatas: List[Dict[str, Any]]) -> None:
        """Add multiple embeddings to the vector store in batch.
        
        Args:
            ids: List of unique identifiers
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries
            
        Raises:
            ValueError: If lengths don't match, vector dimensions are wrong, or any id already exists
        """
        if not (len(ids) == len(vectors) == len(metadatas)):
            raise ValueError("ids, vectors, and metadatas must have the same length")
        
        # Validate vector dimensions
        for i, vector in enumerate(vectors):
            if len(vector) != self._vector_size:
                raise ValueError(
                    f"Vector at index {i} has dimension {len(vector)}, "
                    f"expected {self._vector_size}"
                )
        
        # Check for duplicate IDs in the batch
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate IDs found in the batch")
        
        # Check if any IDs already exist
        try:
            existing = self._client.retrieve(
                collection_name=self._collection_name,
                ids=ids,
            )
            if existing:
                existing_ids = [p.id for p in existing]
                raise ValueError(
                    f"The following IDs already exist in the vector store: {existing_ids}"
                )
        except Exception as e:
            # If error is not about non-existent points, handle it
            if "already exist" in str(e).lower():
                raise
        
        # Create points
        points = [
            self._PointStruct(
                id=id_val,
                vector=vector,
                payload=metadata,
            )
            for id_val, vector, metadata in zip(ids, vectors, metadatas)
        ]
        
        # Batch upsert
        for i in range(0, len(points), self._upsert_batch_size):
            batch = points[i:i + self._upsert_batch_size]
            self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )
    
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
        if len(query_vector) != self._vector_size:
            raise ValueError(
                f"Query vector dimension ({len(query_vector)}) doesn't match "
                f"expected dimension ({self._vector_size})"
            )
        
        # Search in Qdrant
        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        
        # Convert to SearchResult objects
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                id=str(result.id),
                score=float(result.score),
                vector=result.vector if result.vector else query_vector,  # Qdrant may not return vectors
                metadata=result.payload if result.payload else {},
            ))
        
        return search_results
    
    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.
        
        Args:
            id: Unique identifier of the embedding to delete
            
        Raises:
            KeyError: If id doesn't exist
        """
        # Check if ID exists
        try:
            existing = self._client.retrieve(
                collection_name=self._collection_name,
                ids=[id],
            )
            if not existing:
                raise KeyError(f"ID '{id}' not found in vector store")
        except Exception as e:
            if "not found" in str(e).lower():
                raise KeyError(f"ID '{id}' not found in vector store") from e
            raise
        
        # Delete the point
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=[id],
        )
    
    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        # Delete and recreate the collection
        try:
            self._client.delete_collection(collection_name=self._collection_name)
        except Exception as e:
            logger.warning(f"Failed to delete collection: {e}")
        
        # Recreate the collection
        self._ensure_collection()
    
    def count(self) -> int:
        """Get the number of embeddings in the vector store.
        
        Returns:
            Number of embeddings currently stored
        """
        collection_info = self._client.get_collection(self._collection_name)
        return collection_info.points_count
    
    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.
        
        Args:
            id: Unique identifier of the embedding
            
        Returns:
            SearchResult containing the embedding and metadata
            
        Raises:
            KeyError: If id doesn't exist
        """
        points = self._client.retrieve(
            collection_name=self._collection_name,
            ids=[id],
            with_vectors=True,
        )
        
        if not points:
            raise KeyError(f"ID '{id}' not found in vector store")
        
        point = points[0]
        return SearchResult(
            id=str(point.id),
            score=1.0,  # Perfect match with itself
            vector=point.vector if point.vector else [],
            metadata=point.payload if point.payload else {},
        )
