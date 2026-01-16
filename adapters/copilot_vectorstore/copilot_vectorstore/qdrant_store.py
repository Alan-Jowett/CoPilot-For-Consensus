# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Qdrant-based vector store implementation."""

import importlib
import logging
import uuid
from typing import Any

from copilot_config.generated.adapters.vector_store import DriverConfig_VectorStore_Qdrant

from .interface import SearchResult, VectorStore

logger = logging.getLogger(__name__)


def _string_to_uuid(s: str) -> str:
    """Convert a string ID to a deterministic UUID string.

    This ensures consistent UUID generation for the same string ID.
    """
    # Use UUID5 with a namespace for deterministic UUIDs
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
    return str(uuid.uuid5(namespace, s))


def _coerce_vector_struct(vector_struct: Any, fallback: list[float]) -> list[float]:
    """Coerce Qdrant vector outputs into a plain list[float].

    Qdrant can return either a single unnamed vector (list[float]) or a
    named-vector mapping (dict[str, ...]). For this adapter, we always expose
    a single list[float] vector.
    """

    if vector_struct is None:
        return fallback

    if isinstance(vector_struct, list):
        return vector_struct

    if isinstance(vector_struct, dict):
        first_value = next(iter(vector_struct.values()), None)
        if isinstance(first_value, list):
            return first_value

        logger.warning(
            "Unexpected vector structure format for named vectors: "
            "expected first value to be list, got %s; returning fallback vector.",
            type(first_value).__name__ if first_value is not None else "None",
        )

    return fallback


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
        api_key: str | None = None,
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
            qdrant_client_module = importlib.import_module("qdrant_client")
            qdrant_models_module = importlib.import_module("qdrant_client.models")

            QdrantClient = getattr(qdrant_client_module, "QdrantClient")
            Distance = getattr(qdrant_models_module, "Distance")
            PointIdsList = getattr(qdrant_models_module, "PointIdsList")
            PointStruct = getattr(qdrant_models_module, "PointStruct")
            VectorParams = getattr(qdrant_models_module, "VectorParams")
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
        self._Distance: Any = Distance
        self._VectorParams: Any = VectorParams
        self._PointStruct: Any = PointStruct
        self._PointIdsList: Any = PointIdsList

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

        # Lazily ensure the collection exists on first use.
        # Unit tests instantiate stores without requiring a live Qdrant server.
        self._collection_ready = False

        logger.info(
            f"Initialized Qdrant vector store: collection={collection_name}, "
            f"host={host}:{port}, vector_size={vector_size}, distance={distance}"
        )

    def _ensure_collection_ready(self) -> None:
        if self._collection_ready:
            return
        self._ensure_collection()
        self._collection_ready = True

    @classmethod
    def from_config(cls, config: DriverConfig_VectorStore_Qdrant) -> "QdrantVectorStore":
        """Create a QdrantVectorStore from configuration.

        Args:
            config: Configuration object with host, port, collection_name, vector_size,
                    distance, upsert_batch_size, and api_key attributes.
                    Distance and upsert_batch_size defaults are provided by the schema.

        Returns:
            Configured QdrantVectorStore instance

        """
        return cls(
            host=config.host,
            port=config.port,
            api_key=config.api_key,
            collection_name=config.collection_name,
            vector_size=config.vector_size,
            distance=config.distance,
            upsert_batch_size=config.upsert_batch_size,
        )

    def _ensure_collection(self) -> None:
        """Ensure the collection exists, create it if not."""
        # Check if collection exists
        collections = self._client.get_collections().collections
        collection_exists = any(c.name == self._collection_name for c in collections)

        if collection_exists:
            # Verify collection configuration matches
            collection_info: Any = self._client.get_collection(self._collection_name)

            vectors: Any = collection_info.config.params.vectors
            if vectors is None:
                existing_size: Any = None
            elif isinstance(vectors, dict):
                first_params = next(iter(vectors.values()), None)
                existing_size = getattr(first_params, "size", None)
            else:
                existing_size = getattr(vectors, "size", None)

            if existing_size is not None and existing_size != self._vector_size:
                raise ValueError(
                    f"Collection '{self._collection_name}' exists with different vector size: "
                    f"expected {self._vector_size}, found {existing_size}"
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

    def add_embedding(self, id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        """Add a single embedding to the vector store.

        Idempotent operation: if the ID already exists, it will be updated with the new
        vector and metadata (upsert semantics).

        Args:
            id: Unique identifier for this embedding
            vector: The embedding vector
            metadata: Additional metadata to store with the embedding

        Raises:
            ValueError: If vector dimension doesn't match
        """
        if len(vector) != self._vector_size:
            raise ValueError(
                f"Vector dimension ({len(vector)}) doesn't match "
                f"expected dimension ({self._vector_size})"
            )

        self._ensure_collection_ready()

        # Add the point (upsert: create if new, update if exists)
        point = self._PointStruct(
            id=_string_to_uuid(id),
            vector=vector,
            payload={**metadata, "_original_id": id},  # Store original ID in payload
        )

        self._client.upsert(
            collection_name=self._collection_name,
            points=[point],
        )
        logger.debug(f"Upserted embedding with ID: {id}")

    def add_embeddings(self, ids: list[str], vectors: list[list[float]],
                      metadatas: list[dict[str, Any]]) -> None:
        """Add multiple embeddings to the vector store in batch.

        Idempotent operation: if any IDs already exist, they will be updated with the new
        vectors and metadata (upsert semantics).

        Args:
            ids: List of unique identifiers
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries

        Raises:
            ValueError: If lengths don't match or vector dimensions are wrong
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

        # Convert IDs to UUIDs for Qdrant compatibility
        uuid_ids = [_string_to_uuid(id_val) for id_val in ids]

        self._ensure_collection_ready()

        # Create points (upsert: create if new, update if exists)
        points = [
            self._PointStruct(
                id=uuid_id,  # Use deterministic UUID for Qdrant compatibility
                vector=vector,
                payload={**metadata, "_original_id": id_val},  # Keep original ID in payload
            )
            for uuid_id, id_val, vector, metadata in zip(uuid_ids, ids, vectors, metadatas)
        ]

        # Batch upsert
        for i in range(0, len(points), self._upsert_batch_size):
            batch = points[i:i + self._upsert_batch_size]
            self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )

    def query(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]:
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

        self._ensure_collection_ready()

        # Search in Qdrant
        points_result: Any = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=True,
        )
        results = points_result.points

        # Convert to SearchResult objects
        search_results = []
        for result in results:
            # Extract original ID from payload
            payload = result.payload.copy() if result.payload else {}
            original_id = payload.pop("_original_id", str(result.id))

            result_vector = _coerce_vector_struct(result.vector, fallback=query_vector)

            search_results.append(SearchResult(
                id=original_id,
                score=float(result.score),
                vector=result_vector,
                metadata=payload,
            ))

        return search_results

    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.

        Args:
            id: Unique identifier of the embedding to delete

        Raises:
            KeyError: If id doesn't exist
        """
        self._ensure_collection_ready()

        # Check if ID exists
        uuid_id = _string_to_uuid(id)
        existing = self._client.retrieve(
            collection_name=self._collection_name,
            ids=[uuid_id],
        )
        if not existing:
            raise KeyError(f"ID '{id}' not found in vector store")

        # Delete the point
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=self._PointIdsList(points=[uuid_id]),
        )

    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        self._ensure_collection_ready()

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
        self._ensure_collection_ready()

        collection_info: Any = self._client.get_collection(self._collection_name)
        return int(collection_info.points_count or 0)

    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.

        Args:
            id: Unique identifier of the embedding

        Returns:
            SearchResult containing the embedding and metadata

        Raises:
            KeyError: If id doesn't exist
        """
        self._ensure_collection_ready()

        points = self._client.retrieve(
            collection_name=self._collection_name,
            ids=[_string_to_uuid(id)],
            with_vectors=True,
        )

        if not points:
            raise KeyError(f"ID '{id}' not found in vector store")

        point = points[0]
        payload = point.payload if point.payload else {}
        # Remove internal _original_id field
        payload.pop("_original_id", None)

        return SearchResult(
            id=id,  # Return original ID
            score=1.0,  # Perfect match with itself
            vector=_coerce_vector_struct(point.vector, fallback=[]),
            metadata=payload,
        )
