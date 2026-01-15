# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure AI Search-based vector store implementation."""

import json
import logging
import os
from typing import Any, cast

from copilot_config.generated.adapters.vector_store import DriverConfig_VectorStore_AzureAiSearch

from .interface import SearchResult, VectorStore

# Try to import Azure SDK exception types at module level
try:
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    # Fallback if azure.core.exceptions is not available
    ResourceNotFoundError = None  # type: ignore

logger = logging.getLogger(__name__)

# HNSW algorithm configuration constants
# These control the trade-off between search quality and performance
HNSW_M = 4  # Number of bi-directional links per node (higher = better recall, more memory)
# Size of dynamic candidate list during construction (higher = better index quality)
HNSW_EF_CONSTRUCTION = 400
# Size of dynamic candidate list during search (higher = better recall, slower search)
HNSW_EF_SEARCH = 500


class AzureAISearchVectorStore(VectorStore):
    """Azure AI Search-based vector store implementation.

    This implementation uses Azure AI Search (formerly Azure Cognitive Search)
    for vector similarity search with support for metadata filtering and persistence.

    Args:
        endpoint: Azure AI Search service endpoint URL
        api_key: Azure AI Search API key (or use managed identity)
        index_name: Name of the search index to use
        vector_size: Dimension of embedding vectors
        use_managed_identity: Whether to use managed identity for authentication
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        index_name: str = "embeddings",
        vector_size: int = 384,
        use_managed_identity: bool = False,
    ):
        """Initialize an Azure AI Search vector store.

        Args:
            endpoint: Azure AI Search service endpoint URL
            api_key: Azure AI Search API key (required unless using managed identity)
            index_name: Name of the search index to use
            vector_size: Dimension of embedding vectors
            use_managed_identity: Whether to use managed identity for authentication

        Raises:
            ImportError: If azure-search-documents is not installed
            RuntimeError: If cannot connect to Azure AI Search
        """
        # Basic parameter validation.
        # This adapter is often constructed directly in unit tests, so it should
        # not rely solely on schema-level validation.
        if not endpoint:
            raise ValueError("endpoint parameter is required")
        if not endpoint.startswith("https://"):
            raise ValueError("Must start with 'https://'")
        if vector_size <= 0:
            raise ValueError("Vector size must be positive")
        if not use_managed_identity and not api_key:
            raise ValueError(
                "Either api_key must be provided when not using managed identity"
            )

        # Import Azure SDK components after parameter validation
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.indexes import SearchIndexClient
            from azure.search.documents.indexes.models import (
                HnswAlgorithmConfiguration,
                SearchField,
                SearchFieldDataType,
                SearchIndex,
                SimpleField,
                VectorSearch,
                VectorSearchProfile,
            )
        except ImportError as e:
            raise ImportError(
                "azure-search-documents is not installed. "
                "Install it with: pip install azure-search-documents"
            ) from e

        self._endpoint = endpoint
        self._api_key = api_key
        self._index_name = index_name
        self._vector_size = vector_size
        self._use_managed_identity = use_managed_identity

        # Store imports for later use
        self._SearchClient = SearchClient
        self._SearchIndexClient = SearchIndexClient
        self._SearchIndex = SearchIndex
        self._SimpleField = SimpleField
        self._SearchFieldDataType = SearchFieldDataType
        self._SearchField = SearchField
        self._VectorSearch = VectorSearch
        self._HnswAlgorithmConfiguration = HnswAlgorithmConfiguration
        self._VectorSearchProfile = VectorSearchProfile
        self._AzureKeyCredential = AzureKeyCredential

        # Initialize credentials
        if use_managed_identity:
            try:
                from azure.identity import DefaultAzureCredential
                # Use AZURE_CLIENT_ID env var if set (for user-assigned managed identity in Container Apps)
                client_id = os.environ.get('AZURE_CLIENT_ID')
                if client_id:
                    self._credential = DefaultAzureCredential(managed_identity_client_id=client_id)
                else:
                    self._credential = DefaultAzureCredential()
            except ImportError as e:
                raise ImportError(
                    "azure-identity is required for managed identity. "
                    "Install it with: pip install azure-identity"
                ) from e
        else:
            # api_key is schema-validated (required when not using managed identity).
            self._credential = AzureKeyCredential(cast(str, api_key))

        # Initialize clients
        try:
            self._index_client = SearchIndexClient(
                endpoint=endpoint,
                credential=self._credential,
            )
            self._search_client = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=self._credential,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to Azure AI Search at {endpoint}. Error: {e}"
            ) from e

        # Lazily ensure the index exists on first use.
        # Unit tests may instantiate stores without requiring live Azure access.
        self._index_ready = False

        logger.info(
            f"Initialized Azure AI Search vector store: endpoint={endpoint}, "
            f"index={index_name}, vector_size={vector_size}"
        )

    def _ensure_index_ready(self) -> None:
        if self._index_ready:
            return
        self._ensure_index()
        self._index_ready = True

    @classmethod
    def from_config(cls, config: DriverConfig_VectorStore_AzureAiSearch) -> "AzureAISearchVectorStore":
        """Create an AzureAISearchVectorStore from configuration.

        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/vector_store/vectorstore_aisearch.json

        """
        return cls(
            endpoint=config.endpoint,
            api_key=config.api_key,
            index_name=config.index_name,
            vector_size=config.vector_size,
            use_managed_identity=config.use_managed_identity,
        )

    def _ensure_index(self) -> None:
        """Ensure the search index exists, create it if not."""
        try:
            # Check if index exists
            existing_index = self._index_client.get_index(self._index_name)
            logger.info(f"Using existing index '{self._index_name}'")

            # Validate vector field configuration
            vector_field = next(
                (f for f in existing_index.fields if f.name == "embedding"),
                None
            )
            if vector_field and hasattr(vector_field, 'vector_search_dimensions'):
                if vector_field.vector_search_dimensions != self._vector_size:
                    raise ValueError(
                        f"Index '{self._index_name}' exists with different vector size: "
                        f"expected {self._vector_size}, found {vector_field.vector_search_dimensions}"
                    )
        except Exception as e:
            # Check for ResourceNotFoundError first (requires azure-search-documents >= 11.0),
            # then fall back to string matching for older SDK versions or other clients
            is_not_found = (
                (ResourceNotFoundError and isinstance(e, ResourceNotFoundError)) or
                "not found" in str(e).lower() or "does not exist" in str(e).lower()
            )
            if is_not_found:
                # Create new index
                logger.info(f"Creating new index '{self._index_name}'")
                self._create_index()
            else:
                raise

    def _create_index(self) -> None:
        """Create a new search index with vector search configuration."""
        fields = [
            self._SimpleField(
                name="id",
                type=self._SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            self._SearchField(
                name="embedding",
                type=self._SearchFieldDataType.Collection(self._SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self._vector_size,
                vector_search_profile_name="vector-profile",
            ),
            self._SimpleField(
                name="metadata",
                type=self._SearchFieldDataType.String,
                filterable=True,
            ),
        ]

        # Configure vector search with HNSW algorithm
        # Note: HnswAlgorithmConfiguration has different constructor signatures
        # depending on the azure-search-documents SDK version. We try multiple
        # approaches to maximize compatibility:
        # 1. Modern SDK (>= 11.4.0): HnswParameters with snake_case kwargs
        # 2. Legacy SDK: dict-based parameters with camelCase keys (REST API format)
        # 3. Fallback: basic configuration without custom parameters

        hnsw_config: Any
        try:
            # Preferred: Modern azure-search-documents SDK (>= 11.4.0) with
            # HnswParameters class using snake_case keyword arguments
            from azure.search.documents.indexes.models import HnswParameters
            hnsw_params = HnswParameters(
                m=HNSW_M,
                ef_construction=HNSW_EF_CONSTRUCTION,
                ef_search=HNSW_EF_SEARCH,
                metric="cosine",
            )
            hnsw_config = self._HnswAlgorithmConfiguration(
                name="hnsw-algorithm",
                parameters=hnsw_params
            )
        except (ImportError, TypeError):
            # Legacy: Older SDK versions may accept dict with camelCase keys
            # matching the Azure REST API schema ("efConstruction", "efSearch")
            try:
                hnsw_config = self._HnswAlgorithmConfiguration(
                    name="hnsw-algorithm",
                    parameters=cast(Any, {
                        "m": HNSW_M,
                        "efConstruction": HNSW_EF_CONSTRUCTION,
                        "efSearch": HNSW_EF_SEARCH,
                        "metric": "cosine",
                    })
                )
            except TypeError:
                # Fallback to basic configuration
                logger.warning(
                    "Falling back to basic HNSW configuration for index '%s'; "
                    "custom HNSW parameters could not be applied because your "
                    "installed azure-search-documents SDK version does not "
                    "support the expected HnswAlgorithmConfiguration/HnswParameters "
                    "constructor signatures. This may reduce vector search quality. "
                    "Consider upgrading to azure-search-documents >= 11.4.0 or "
                    "review the SDK documentation for the correct configuration API.",
                    self._index_name,
                )
                hnsw_config = self._HnswAlgorithmConfiguration(name="hnsw-algorithm")

        vector_search = self._VectorSearch(
            algorithms=[hnsw_config],
            profiles=[
                self._VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-algorithm",
                )
            ],
        )

        index = self._SearchIndex(
            name=self._index_name,
            fields=fields,
            vector_search=vector_search,
        )

        self._index_client.create_index(index)
        logger.info(f"Created index '{self._index_name}'")

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
        self._ensure_index_ready()

        if len(vector) != self._vector_size:
            raise ValueError(
                f"Vector dimension ({len(vector)}) doesn't match "
                f"expected dimension ({self._vector_size})"
            )

        # Prepare document for indexing
        document = {
            "id": id,
            "embedding": vector,
            "metadata": json.dumps(metadata),
        }

        # Upload document (upsert semantics)
        self._search_client.upload_documents(documents=[document])
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
        self._ensure_index_ready()

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

        # Prepare documents for batch indexing
        documents = [
            {
                "id": id_val,
                "embedding": vector,
                "metadata": json.dumps(metadata),
            }
            for id_val, vector, metadata in zip(ids, vectors, metadatas)
        ]

        # Upload documents in batch (upsert semantics)
        self._search_client.upload_documents(documents=documents)
        logger.debug(f"Upserted {len(documents)} embeddings")

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
        self._ensure_index_ready()

        if len(query_vector) != self._vector_size:
            raise ValueError(
                f"Query vector dimension ({len(query_vector)}) doesn't match "
                f"expected dimension ({self._vector_size})"
            )

        from azure.search.documents.models import VectorizedQuery

        # Create vector query
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding"
        )

        # Execute search
        # Use empty string for search_text in vector-only queries
        # (Azure SDK requires non-null string for search_text parameter)
        results = self._search_client.search(
            search_text="",
            vector_queries=[vector_query],
            select=["id", "embedding", "metadata"],
            top=top_k,
        )

        # Convert to SearchResult objects
        search_results = []
        for result in results:
            # Parse metadata
            metadata = {}
            if "metadata" in result and result["metadata"]:
                try:
                    metadata = json.loads(result["metadata"])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for document {result.get('id')}")

            # Get stored vector; this must be returned by Azure AI Search
            vector = result.get("embedding")
            if vector is None:
                logger.warning(
                    f"Search result for document {result.get('id')} did not include 'embedding' field. "
                    "Using query vector as fallback. Ensure select parameter includes 'embedding'."
                )
                vector = query_vector

            search_results.append(SearchResult(
                id=result["id"],
                score=float(result["@search.score"]),
                vector=vector,
                metadata=metadata,
            ))

        return search_results

    def delete(self, id: str) -> None:
        """Delete an embedding from the vector store.

        Args:
            id: Unique identifier of the embedding to delete

        Raises:
            KeyError: If id doesn't exist
        """
        self._ensure_index_ready()

        # Check if document exists
        try:
            self._search_client.get_document(key=id)
        except Exception as e:
            # Check for ResourceNotFoundError first (requires azure-search-documents >= 11.0),
            # then fall back to string matching for older SDK versions or other clients
            is_not_found = (
                (ResourceNotFoundError and isinstance(e, ResourceNotFoundError)) or
                "not found" in str(e).lower()
            )
            if is_not_found:
                raise KeyError(f"ID '{id}' not found in vector store") from e
            raise

        # Delete the document
        self._search_client.delete_documents(documents=[{"id": id}])
        logger.debug(f"Deleted embedding with ID: {id}")

    def clear(self) -> None:
        """Remove all embeddings from the vector store."""
        self._ensure_index_ready()

        # Delete and recreate the index
        try:
            self._index_client.delete_index(self._index_name)
            logger.info(f"Deleted index '{self._index_name}'")
        except Exception as e:
            logger.warning(f"Failed to delete index: {e}")

        # Recreate the index
        self._create_index()

    def count(self) -> int:
        """Get the number of embeddings in the vector store.

        Returns:
            Number of embeddings currently stored
        """
        self._ensure_index_ready()

        # Azure AI Search doesn't have a direct count API
        # We need to search and count results
        results = self._search_client.search(
            search_text="*",
            include_total_count=True,
            top=0,  # Don't return actual documents, just count
        )
        # Some SDK versions type this as `int`, but at runtime it can be `None`.
        count = cast(Any, results).get_count()
        if count is None:
            logger.warning(
                "Azure AI Search returned None for count, returning 0. "
                "This may indicate a count retrieval issue or search service problem."
            )
            return 0
        return count

    def get(self, id: str) -> SearchResult:
        """Retrieve a specific embedding by ID.

        Args:
            id: Unique identifier of the embedding

        Returns:
            SearchResult containing the embedding and metadata

        Raises:
            KeyError: If id doesn't exist
        """
        self._ensure_index_ready()

        try:
            result = self._search_client.get_document(key=id)
        except Exception as e:
            # Check for ResourceNotFoundError first (requires azure-search-documents >= 11.0),
            # then fall back to string matching for older SDK versions or other clients
            is_not_found = (
                (ResourceNotFoundError and isinstance(e, ResourceNotFoundError)) or
                "not found" in str(e).lower()
            )
            if is_not_found:
                raise KeyError(f"ID '{id}' not found in vector store") from e
            raise

        # Parse metadata
        metadata = {}
        if "metadata" in result and result["metadata"]:
            try:
                metadata = json.loads(result["metadata"])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata for document {id}")

        return SearchResult(
            id=id,
            score=1.0,  # Perfect match with itself
            vector=result.get("embedding", []),
            metadata=metadata,
        )
