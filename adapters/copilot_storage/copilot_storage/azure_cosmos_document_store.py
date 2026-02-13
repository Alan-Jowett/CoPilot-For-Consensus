# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Cosmos DB document store implementation."""

import copy
import logging
import re
import uuid
from typing import Any, cast

from copilot_config.generated.adapters.document_store import DriverConfig_DocumentStore_AzureCosmosdb

from .document_store import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
)
from .schema_registry import sanitize_document, sanitize_documents

logger = logging.getLogger(__name__)

# Import azure.cosmos at module level to avoid repeated imports in methods.
# This dependency is optional; when missing, connect() will raise a clear error.
cosmos_exceptions: Any
try:
    from azure.cosmos import exceptions as cosmos_exceptions
except ImportError:
    cosmos_exceptions = None


class AzureCosmosDocumentStore(DocumentStore):
    """Azure Cosmos DB document store implementation using Core (SQL) API.

    Each collection type is stored in its own container with partition key /id.
    This enables independent management of source data (messages, archives) vs
    derived data (chunks, reports, summaries).
    """

    @classmethod
    def from_config(cls, config: DriverConfig_DocumentStore_AzureCosmosdb) -> "AzureCosmosDocumentStore":
        """Create an AzureCosmosDocumentStore from configuration.

        Args:
            config: Configuration object with endpoint, key, and database attributes.
                    Database default is provided by the schema.

        Returns:
            Configured AzureCosmosDocumentStore instance

        Raises:
            AttributeError: If required config attributes are missing
        """
        kwargs: dict[str, Any] = {}

        if config.endpoint is not None:
            kwargs["endpoint"] = config.endpoint

        if config.key is not None:
            kwargs["key"] = config.key

        if config.database is not None:
            kwargs["database"] = config.database

        return cls(**kwargs)

    def __init__(
        self,
        endpoint: str | None = None,
        key: str | None = None,
        database: str = "copilot",
        **kwargs,
    ):
        """Initialize Azure Cosmos DB document store.

        Args:
            endpoint: Cosmos DB endpoint URL (e.g., https://myaccount.documents.azure.com:443/).
                     Required parameter.
            key: Cosmos DB account key (optional; if None, managed identity via DefaultAzureCredential will be used).
                 Either key or managed identity support required.
            database: Database name (default: "copilot")
            **kwargs: Additional Cosmos client options (e.g., connection_timeout, request_timeout)

        Raises:
            ValueError: If endpoint is not provided
        """
        if not endpoint:
            raise ValueError("endpoint is required for AzureCosmosDocumentStore")

        self.endpoint = endpoint
        self.key = key
        self.database_name = database
        self.client_options = kwargs
        self.client: Any | None = None
        self.database: Any | None = None
        # Cache for containers: {collection_name: container_client}
        self.containers: dict[str, Any] = {}

    def _is_valid_field_name(self, field_name: str) -> bool:
        """Validate that a field name contains only safe characters.

        This helper supports nested field access via dots (e.g., ``user.email``),
        but validates each component between dots individually to avoid
        bypassing validation with crafted nested paths.

        Args:
            field_name: Field name to validate

        Returns:
            True if field name is safe, False otherwise
        """
        # First, ensure the overall string only contains allowed characters
        if not re.match(r"^[a-zA-Z0-9_.]+$", field_name):
            return False

        # Then, validate each component between dots to prevent empty segments
        # or other invalid patterns (e.g., "user..email")
        components = field_name.split(".")
        if any(not component or not re.match(r"^[a-zA-Z0-9_]+$", component) for component in components):
            return False

        return True

    def _is_valid_document_id(self, doc_id: str) -> bool:
        """Validate that a document ID meets Cosmos DB requirements.

        Cosmos DB document IDs cannot contain: '/', '\', '#', '?', or control characters.

        Args:
            doc_id: Document ID to validate

        Returns:
            True if document ID is valid, False otherwise
        """
        if not doc_id or not isinstance(doc_id, str):
            return False

        # Check for invalid characters
        invalid_chars = ["/", "\\", "#", "?"]
        if any(char in doc_id for char in invalid_chars):
            return False

        # Check for control characters
        if any(ord(char) < 32 for char in doc_id):
            return False

        return True

    def _get_container_config_for_collection(self, collection: str) -> tuple[str, str]:
        """Get container name and partition key for a collection.

        Each collection type gets its own container with partition key /id.

        Args:
            collection: Logical collection name (e.g., "messages", "chunks")

        Returns:
            Tuple of (container_name, partition_key)
        """
        # Known collection types with explicit container configs
        container_configs = {
            # Source containers
            "messages": ("messages", "/id"),
            "archives": ("archives", "/id"),
            # Ingestion configuration
            "sources": ("sources", "/id"),
            # Derived containers
            "chunks": ("chunks", "/id"),
            "reports": ("reports", "/id"),
            "summaries": ("summaries", "/id"),
            "threads": ("threads", "/id"),
        }

        # Use collection-specific config if defined, otherwise use collection name as container
        return container_configs.get(collection, (collection, "/id"))

    def _get_container_for_collection(self, collection: str) -> Any:
        """Get or create the Cosmos container for a collection.

        Args:
            collection: Logical collection name

        Returns:
            Cosmos container client

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If container creation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        if collection in self.containers:
            return self.containers[collection]

        # Create container if not cached
        container_name, partition_key = self._get_container_config_for_collection(collection)

        try:
            from azure.cosmos import PartitionKey
            from azure.core.exceptions import AzureError

            container_client = self.database.create_container_if_not_exists(
                id=container_name, partition_key=PartitionKey(path=partition_key)
            )
            self.containers[collection] = container_client
            logger.info(
                f"AzureCosmosDocumentStore: initialized container '{container_name}' "
                f"for collection '{collection}' with partition key '{partition_key}'"
            )
            return container_client

        except cosmos_exceptions.CosmosHttpResponseError as e:
            logger.error(f"AzureCosmosDocumentStore: failed to create/access container '{container_name}' - {e}")
            raise DocumentStoreError(f"Failed to create/access container '{container_name}'") from e
        except AzureError as e:
            logger.error(f"AzureCosmosDocumentStore: Azure error during container creation for '{container_name}' - {e}")
            raise DocumentStoreError(f"Azure error creating/accessing container '{container_name}'") from e

    def connect(self) -> None:
        """Connect to Azure Cosmos DB.

        Raises:
            DocumentStoreConnectionError: If connection fails
        """
        try:
            from azure.core.exceptions import AzureError
            from azure.cosmos import CosmosClient
        except ImportError as e:
            logger.error("AzureCosmosDocumentStore: azure-cosmos not installed")
            raise DocumentStoreConnectionError("azure-cosmos not installed") from e

        if not self.endpoint:
            raise DocumentStoreConnectionError("Cosmos DB endpoint is required")

        try:
            # Create Cosmos client
            # If key is provided, use key-based authentication
            # Otherwise, use managed identity via DefaultAzureCredential
            if self.key:
                self.client = CosmosClient(self.endpoint, self.key, **self.client_options)
                logger.info("AzureCosmosDocumentStore: using key-based authentication")
            else:
                try:
                    from azure.identity import DefaultAzureCredential

                    credential = DefaultAzureCredential()
                    self.client = CosmosClient(self.endpoint, credential=credential, **self.client_options)
                    logger.info("AzureCosmosDocumentStore: using managed identity authentication")
                except ImportError as e:
                    logger.error("AzureCosmosDocumentStore: azure-identity not installed for managed identity")
                    raise DocumentStoreConnectionError(
                        "azure-identity package is required for managed identity authentication. "
                        "Install it with: pip install azure-identity"
                    ) from e

            # Get or create database
            try:
                database = self.client.create_database_if_not_exists(id=self.database_name)
                self.database = database
                logger.info(f"AzureCosmosDocumentStore: using database '{self.database_name}'")
            except cosmos_exceptions.CosmosHttpResponseError as e:
                logger.error(f"AzureCosmosDocumentStore: failed to create/access database - {e}")
                raise DocumentStoreConnectionError(f"Failed to create/access database '{self.database_name}'") from e

            # Containers are created on-demand when first accessed
            logger.info(f"AzureCosmosDocumentStore: connected to {self.endpoint}/{self.database_name}")

        except (cosmos_exceptions.CosmosHttpResponseError, AzureError) as e:
            logger.error(f"AzureCosmosDocumentStore: connection failed - {e}", exc_info=True)
            raise DocumentStoreConnectionError(f"Failed to connect to Cosmos DB at {self.endpoint}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: unexpected error during connect - {e}", exc_info=True)
            raise DocumentStoreConnectionError(f"Unexpected error connecting to Cosmos DB: {str(e)}") from e

    def disconnect(self) -> None:
        """Disconnect from Azure Cosmos DB.

        Note: CosmosClient doesn't require explicit disconnect, but we reset references.
        """
        if self.client:
            self.client = None
            self.database = None
            self.containers = {}
            logger.info("AzureCosmosDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document into the specified collection.

        Each collection routes to its own container with partition key /id.

        Args:
            collection: Name of the logical collection
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentAlreadyExistsError: If document with same ID already exists
            DocumentStoreError: If insertion fails
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        try:
            # Cosmos DB requires a native "id" field as the document key.
            # Our canonical identifier across services/schemas is "_id".
            # Keep them aligned when possible so services can remain storage-agnostic.
            if "id" in doc and doc.get("id") is not None:
                doc_id = doc["id"]
            elif "_id" in doc and doc.get("_id") is not None:
                doc_id = doc["_id"]
            else:
                doc_id = str(uuid.uuid4())

            # Validate document ID meets Cosmos DB requirements
            if not self._is_valid_document_id(doc_id):
                raise DocumentStoreError(
                    f"Invalid document ID '{doc_id}': IDs cannot contain '/', '\\', '#', '?', or control characters"
                )

            # Create a deep copy to avoid modifying the original (including nested structures)
            doc_copy = copy.deepcopy(doc)
            doc_copy["id"] = doc_id

            # Insert document
            container.create_item(body=doc_copy)
            logger.debug(f"AzureCosmosDocumentStore: inserted document {doc_id} into {collection}")

            return doc_id

        except cosmos_exceptions.CosmosResourceExistsError as e:
            logger.debug(f"AzureCosmosDocumentStore: document with id {doc_id} already exists - {e}")
            raise DocumentAlreadyExistsError(f"Document with id {doc_id} already exists in collection {collection}") from e
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during insert - {e}")
                raise DocumentStoreError(f"Throttled during insert: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: insert failed - {e}")
            raise DocumentStoreError(f"Failed to insert document into {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: insert failed - {e}")
            raise DocumentStoreError(f"Failed to insert document into {collection}") from e

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Returns a sanitized document without backend system fields or
        document store metadata fields.

        Args:
            collection: Name of the logical collection
            doc_id: Document ID

        Returns:
            Sanitized document data as dictionary, or None if not found

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If query operation fails
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        try:
            # Partition key is the document ID
            partition_key_value = doc_id

            # Read document using partition key
            doc = container.read_item(item=doc_id, partition_key=partition_key_value)

            logger.debug(f"AzureCosmosDocumentStore: retrieved document {doc_id} from {collection}")
            return sanitize_document(doc, collection)

        except cosmos_exceptions.CosmosResourceNotFoundError:
            logger.debug(f"AzureCosmosDocumentStore: document {doc_id} not found in {collection}")
            return None
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during get - {e}")
                raise DocumentStoreError(f"Throttled during get: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: get_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to retrieve document {doc_id} from {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: get_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to retrieve document {doc_id} from {collection}") from e

    def query_documents(
        self,
        collection: str,
        filter_dict: dict[str, Any],
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Returns sanitized documents without backend system fields or
        document store metadata fields.

        Supports MongoDB-style operators: $in, $eq

        Args:
            collection: Name of the logical collection
            filter_dict: Filter criteria as dictionary (supports equality and MongoDB operators)
            limit: Maximum number of documents to return
            sort_by: Optional field name to sort results by
            sort_order: Sort order ('asc' or 'desc', default 'desc')

        Returns:
            List of sanitized matching documents (empty list if no matches)

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If query operation fails
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        try:
            # Build SQL query for Cosmos DB
            # Each collection has its own container, so no collection filter needed
            query = "SELECT * FROM c WHERE 1=1"
            parameters: list[dict[str, object]] = []

            param_counter = 0

            # Add filter conditions
            for key, value in filter_dict.items():
                # Validate field name to prevent SQL injection
                if not self._is_valid_field_name(key):
                    logger.warning(f"AzureCosmosDocumentStore: skipping invalid field name '{key}'")
                    continue

                if isinstance(value, dict):
                    # Handle MongoDB-style operators
                    # Validate that all keys in the dict are operators (start with '$')
                    non_operators = [k for k in value.keys() if not k.startswith("$")]
                    if non_operators:
                        logger.warning(
                            f"AzureCosmosDocumentStore: filter dict for '{key}' contains non-operator keys "
                            f"{non_operators}, treating as invalid - skipping field"
                        )
                        continue

                    for op, op_value in value.items():
                        if op == "$in":
                            # Translate $in to Cosmos SQL IN operator
                            # Example: {"status": {"$in": ["pending", "processing"]}}
                            # becomes: AND c.status IN (@param0, @param1)
                            if not isinstance(op_value, list):
                                logger.warning(
                                    "AzureCosmosDocumentStore: $in operator requires list value, "
                                    f"got {type(op_value).__name__}"
                                )
                                continue
                            if not op_value:
                                # Empty list - no documents match
                                logger.debug(
                                    "AzureCosmosDocumentStore: $in operator with empty list " "- returning empty result"
                                )
                                return []

                            # Build parameter list for IN clause
                            param_names = []
                            for item in op_value:
                                param_name = f"@param{param_counter}"
                                param_counter += 1
                                param_names.append(param_name)
                                parameters.append({"name": param_name, "value": item})

                            query += f" AND c.{key} IN ({', '.join(param_names)})"
                        elif op == "$eq":
                            # Explicit equality
                            param_name = f"@param{param_counter}"
                            param_counter += 1
                            query += f" AND c.{key} = {param_name}"
                            parameters.append({"name": param_name, "value": op_value})
                        else:
                            logger.warning(
                                f"AzureCosmosDocumentStore: unsupported operator '{op}' in query_documents, skipping"
                            )
                else:
                    # Simple equality check
                    param_name = f"@param{param_counter}"
                    param_counter += 1
                    query += f" AND c.{key} = {param_name}"
                    parameters.append({"name": param_name, "value": value})

            # Add sorting if requested
            if sort_by:
                if not self._is_valid_field_name(sort_by):
                    raise DocumentStoreError(f"Invalid sort_by field name '{sort_by}'")
                if sort_order not in ("asc", "desc"):
                    raise DocumentStoreError(
                        f"Invalid sort_order '{sort_order}': must be 'asc' or 'desc'"
                    )
                order = "DESC" if sort_order == "desc" else "ASC"
                # Single-field ORDER BY works with the default /* range index.
                # Documents with missing/null sort fields sort as the lowest
                # value (first in ASC, last in DESC). This is Cosmos DB's
                # native behavior and the canonical contract for all backends.
                query += f" ORDER BY c.{sort_by} {order}"

            # Add limit (validate to prevent SQL injection)
            # Cosmos DB requires OFFSET...LIMIT syntax, not standalone LIMIT
            if not isinstance(limit, int) or limit < 1:
                raise DocumentStoreError(f"Invalid limit value '{limit}': must be a positive integer")
            query += f" OFFSET 0 LIMIT {limit}"

            # Execute query with cross-partition query (documents have different partition keys)
            items = list(
                container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True)
            )

            logger.debug(
                f"AzureCosmosDocumentStore: query on {collection} with {filter_dict} "
                f"returned {len(items)} documents"
            )
            return sanitize_documents(items, collection)

        except DocumentStoreError:
            # Re-raise our own validation errors without wrapping
            raise
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during query - {e}")
                raise DocumentStoreError(f"Throttled during query: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: query_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to query documents from {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: query_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to query documents from {collection}") from e

    def update_document(self, collection: str, doc_id: str, patch: dict[str, Any]) -> None:
        """Update a document with the provided patch.

        Args:
            collection: Name of the logical collection
            doc_id: Document ID
            patch: Update data as dictionary

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If update operation fails
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        try:
            # Partition key is the document ID
            partition_key_value = doc_id

            # Read the existing document
            try:
                existing_doc = container.read_item(item=doc_id, partition_key=partition_key_value)
            except cosmos_exceptions.CosmosResourceNotFoundError:
                logger.debug(f"AzureCosmosDocumentStore: document {doc_id} not found in {collection}")
                raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

            # Apply patch to a copy to avoid mutating the original document in-place
            merged_doc = dict(existing_doc)
            if patch:
                merged_doc.update(patch)

            # Ensure identifier fields cannot be changed via patch.
            # - `id` is the Cosmos DB partition/primary key and must remain equal to `doc_id`.
            # - `_id` and `collection` (when present) are treated as canonical metadata and are
            #   restored from the existing document or removed if they did not previously exist.
            merged_doc["id"] = doc_id

            if "_id" in existing_doc:
                merged_doc["_id"] = existing_doc["_id"]
            else:
                merged_doc.pop("_id", None)

            if "collection" in existing_doc:
                merged_doc["collection"] = existing_doc["collection"]
            else:
                merged_doc.pop("collection", None)

            # Replace document - partition key is inferred from body["id"]
            # Note: azure-cosmos 4.9.0's replace_item doesn't accept partition_key parameter
            # (unlike read_item and delete_item). The SDK uses the id from the body.
            container.replace_item(item=doc_id, body=merged_doc)

            logger.debug(f"AzureCosmosDocumentStore: updated document {doc_id} in {collection}")

        except DocumentNotFoundError:
            raise
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during update - {e}")
                raise DocumentStoreError(f"Throttled during update: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: update_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to update document {doc_id} in {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: update_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to update document {doc_id} in {collection}") from e

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.

        Args:
            collection: Name of the logical collection
            doc_id: Document ID

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If delete operation fails
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        try:
            # Partition key is the document ID
            partition_key_value = doc_id

            # Delete document
            container.delete_item(item=doc_id, partition_key=partition_key_value)

            logger.debug(f"AzureCosmosDocumentStore: deleted document {doc_id} from {collection}")

        except cosmos_exceptions.CosmosResourceNotFoundError:
            logger.debug(f"AzureCosmosDocumentStore: document {doc_id} not found in {collection}")
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during delete - {e}")
                raise DocumentStoreError(f"Throttled during delete: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: delete_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to delete document {doc_id} from {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: delete_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to delete document {doc_id} from {collection}") from e

    def aggregate_documents(self, collection: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute an aggregation pipeline on a collection.

        Returns sanitized documents without backend system fields or
        document store metadata fields.

        Note: This is a simplified implementation that supports common aggregation stages
        for compatibility with MongoDB-style pipelines. Cosmos DB uses SQL queries, so
        we translate simple pipelines to SQL where possible, and handle complex operations
        like $lookup with client-side processing.

        Supported stages: $match, $lookup, $limit

        Args:
            collection: Name of the logical collection
            pipeline: Aggregation pipeline (list of stage dictionaries)

        Returns:
            List of sanitized aggregation results

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If aggregation operation fails
        """
        try:
            # Process pipeline stages sequentially
            # Start by querying the initial collection with $match stages before any $lookup
            results = self._execute_initial_query(collection, pipeline)

            # Process remaining stages that require client-side processing
            results = self._process_client_side_stages(results, pipeline)

            logger.debug(f"AzureCosmosDocumentStore: aggregation on {collection} " f"returned {len(results)} documents")
            return sanitize_documents(results, collection, preserve_extra=True)

        except DocumentStoreError:
            # Re-raise our own validation errors without wrapping
            raise
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                logger.warning(f"AzureCosmosDocumentStore: throttled during aggregation - {e}")
                raise DocumentStoreError(f"Throttled during aggregation: {str(e)}") from e
            logger.error(f"AzureCosmosDocumentStore: aggregate_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to aggregate documents from {collection}") from e
        except Exception as e:
            logger.error(f"AzureCosmosDocumentStore: aggregate_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to aggregate documents from {collection}") from e

    def _execute_initial_query(self, collection: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute initial SQL query for stages that can be pushed down to Cosmos DB.

        This handles $match stages that appear before any $lookup stages, and
        $limit stages if there's no $lookup in the pipeline.

        Args:
            collection: Name of the logical collection
            pipeline: Full aggregation pipeline

        Returns:
            List of documents from initial query
        """
        # Get the target container for this collection
        container = self._get_container_for_collection(collection)

        # Build SQL query - each collection has its own container
        query = "SELECT * FROM c WHERE 1=1"
        parameters: list[dict[str, object]] = []

        param_counter = 0
        has_lookup = any(list(stage.keys())[0] == "$lookup" for stage in pipeline)

        # Process only initial $match stages (before any $lookup)
        for stage in pipeline:
            stage_name = list(stage.keys())[0]

            # Stop at first non-$match stage
            if stage_name != "$match":
                break

            stage_spec = stage[stage_name]

            # Add match conditions to WHERE clause
            for key, condition in stage_spec.items():
                # Validate field name to prevent SQL injection
                if not self._is_valid_field_name(key):
                    logger.warning(f"AzureCosmosDocumentStore: skipping invalid field name '{key}'")
                    continue

                if isinstance(condition, dict):
                    # Handle operators
                    # Validate that all keys in the dict are operators (start with '$')
                    non_operators = [k for k in condition.keys() if not k.startswith("$")]
                    if non_operators:
                        logger.warning(
                            f"AzureCosmosDocumentStore: $match condition for '{key}' contains "
                            f"non-operator keys {non_operators}, treating as invalid - skipping field"
                        )
                        continue

                    for op, value in condition.items():
                        if op == "$exists":
                            if value:
                                query += f" AND IS_DEFINED(c.{key})"
                            else:
                                query += f" AND NOT IS_DEFINED(c.{key})"
                        elif op == "$eq":
                            param_name = f"@param{param_counter}"
                            param_counter += 1
                            query += f" AND c.{key} = {param_name}"
                            parameters.append({"name": param_name, "value": value})
                        elif op == "$in":
                            # Translate $in to Cosmos SQL IN operator
                            if not isinstance(value, list):
                                logger.warning(
                                    "AzureCosmosDocumentStore: $in operator requires list value, "
                                    f"got {type(value).__name__}"
                                )
                                continue
                            if not value:
                                # Empty list - no documents match; short-circuit to avoid unnecessary query
                                logger.debug(
                                    "AzureCosmosDocumentStore: $in operator with empty list in aggregation "
                                    "- returning empty result"
                                )
                                return []

                            # Build parameter list for IN clause
                            param_names = []
                            for item in value:
                                param_name = f"@param{param_counter}"
                                param_counter += 1
                                param_names.append(param_name)
                                parameters.append({"name": param_name, "value": item})

                            query += f" AND c.{key} IN ({', '.join(param_names)})"
                        else:
                            logger.warning(f"AzureCosmosDocumentStore: unsupported operator '{op}' in $match, skipping")
                else:
                    # Simple equality check
                    param_name = f"@param{param_counter}"
                    param_counter += 1
                    query += f" AND c.{key} = {param_name}"
                    parameters.append({"name": param_name, "value": condition})

        # If there's no $lookup, we can add $limit to the SQL query
        # Cosmos DB requires OFFSET...LIMIT syntax, not standalone LIMIT
        if not has_lookup:
            for stage in pipeline:
                stage_name = list(stage.keys())[0]
                if stage_name == "$limit":
                    limit_value = stage[stage_name]
                    # Validate limit value to prevent SQL injection
                    if not isinstance(limit_value, int) or limit_value < 1:
                        raise DocumentStoreError(f"Invalid limit value '{limit_value}': must be a positive integer")
                    query += f" OFFSET 0 LIMIT {limit_value}"
                    break

        # Execute query with cross-partition query
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))

        return items

    def _process_client_side_stages(
        self, documents: list[dict[str, Any]], pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process pipeline stages that require client-side processing.

        This handles $lookup, $match (after $lookup), and $limit stages.

        Args:
            documents: Documents from initial query
            pipeline: Full aggregation pipeline

        Returns:
            Processed documents
        """
        results = documents
        skip_initial_matches = True  # Skip $match stages already processed in SQL

        for stage in pipeline:
            stage_name = list(stage.keys())[0]
            stage_spec = stage[stage_name]

            if stage_name == "$match":
                if skip_initial_matches:
                    # Already processed in SQL, continue until we hit a non-$match stage
                    continue
                else:
                    # Process $match that comes after $lookup
                    results = self._apply_match_stage(results, stage_spec)

            elif stage_name == "$lookup":
                # From this point on, we need to process all stages client-side
                skip_initial_matches = False
                results = self._apply_lookup_stage(results, stage_spec)

            elif stage_name == "$limit":
                # Validate and apply limit
                if not isinstance(stage_spec, int) or stage_spec < 1:
                    raise DocumentStoreError(f"Invalid limit value '{stage_spec}': must be a positive integer")
                results = results[:stage_spec]

            else:
                logger.warning(f"AzureCosmosDocumentStore: aggregation stage '{stage_name}' not implemented, skipping")

        return results

    def _apply_match_stage(self, documents: list[dict[str, Any]], match_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply a $match stage to filter documents.

        Args:
            documents: Documents to filter
            match_spec: Match specification

        Returns:
            Filtered documents
        """
        results = []

        for doc in documents:
            matches = True

            for key, condition in match_spec.items():
                if isinstance(condition, dict):
                    # Handle operators
                    for op, value in condition.items():
                        if op == "$eq":
                            # Get field value, handling missing fields and nested paths
                            doc_value = self._get_nested_field(doc, key)
                            # Direct equality comparison works for primitives and arrays
                            # Note: After $lookup, array fields will always be present (either empty [] or with items)
                            if doc_value != value:
                                matches = False
                                break
                        elif op == "$exists":
                            # For $exists, check if the nested field is present
                            doc_value = self._get_nested_field(doc, key)
                            if value and doc_value is None:
                                matches = False
                                break
                            elif not value and doc_value is not None:
                                matches = False
                                break
                        else:
                            logger.warning(
                                f"AzureCosmosDocumentStore: unsupported operator '{op}' in client-side $match"
                            )
                    if not matches:
                        break
                else:
                    # Simple equality check with nested field support
                    if self._get_nested_field(doc, key) != condition:
                        matches = False
                        break

            if matches:
                results.append(doc)

        return results

    def _apply_lookup_stage(self, documents: list[dict[str, Any]], lookup_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply a $lookup stage to join with another collection.

        Performs client-side join since Cosmos DB doesn't support joins.

        Args:
            documents: Documents to join with foreign collection
            lookup_spec: Lookup specification with from, localField, foreignField, as

        Returns:
            Documents with joined data
        """
        from_collection = lookup_spec.get("from")
        local_field = lookup_spec.get("localField")
        foreign_field = lookup_spec.get("foreignField")
        as_field = lookup_spec.get("as")

        # Validate that all required fields are present and have correct types
        required_fields = {
            "from": from_collection,
            "localField": local_field,
            "foreignField": foreign_field,
            "as": as_field,
        }

        # Check for missing or non-string values (but not empty strings yet)
        missing_or_invalid = [field_name for field_name, value in required_fields.items() if not isinstance(value, str)]
        if missing_or_invalid:
            raise DocumentStoreError(f"$lookup requires string values for {', '.join(missing_or_invalid)}")

        # Check for empty strings (all values are strings at this point)
        empty_fields = [field_name for field_name, value in required_fields.items() if value == ""]
        if empty_fields:
            raise DocumentStoreError(f"$lookup requires non-empty values for {', '.join(empty_fields)}")

        # At this point, all required fields are non-empty strings.
        from_collection = cast(str, from_collection)
        local_field = cast(str, local_field)
        foreign_field = cast(str, foreign_field)
        as_field = cast(str, as_field)

        # Validate field names (nested access allowed via dot notation)
        for field_value, field_name in (
            (local_field, "localField"),
            (foreign_field, "foreignField"),
            (as_field, "as"),
        ):
            if not self._is_valid_field_name(field_value):
                raise DocumentStoreError(f"Invalid {field_name} '{field_value}' in $lookup")

        # Get the target container for the foreign collection
        foreign_container = self._get_container_for_collection(from_collection)

        # Collect all unique local field values from documents
        # This allows us to query only the needed foreign documents instead of scanning the entire container
        local_values = set()
        for doc in documents:
            local_value = self._get_nested_field(doc, local_field)
            if local_value is not None:
                local_values.add(local_value)

        # If no documents have local values, return early with empty arrays
        if not local_values:
            results = []
            for doc in documents:
                doc_copy = dict(doc)
                doc_copy[as_field] = []
                results.append(doc_copy)
            return results

        # Query only the foreign documents that match the local field values
        # Use IN operator to fetch only needed documents, avoiding full container scan
        # Batch if there are too many values to avoid query size limits
        foreign_docs = []
        local_values_list = list(local_values)
        batch_size = 100  # Cosmos DB can handle large IN clauses, but we batch to be safe

        try:
            for i in range(0, len(local_values_list), batch_size):
                batch = local_values_list[i : i + batch_size]

                # Build parameterized query with IN clause
                param_names = []
                parameters: list[dict[str, object]] = []
                for idx, val in enumerate(batch):
                    param_name = f"@val{idx}"
                    param_names.append(param_name)
                    parameters.append({"name": param_name, "value": val})

                # Validate foreignField to prevent SQL injection
                if not self._is_valid_field_name(foreign_field):
                    raise DocumentStoreError(f"Invalid foreignField '{foreign_field}' in $lookup")

                query = f"SELECT * FROM c WHERE c.{foreign_field} IN ({', '.join(param_names)})"

                # Use cross-partition query
                batch_docs = list(
                    foreign_container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True)
                )
                foreign_docs.extend(batch_docs)

        except cosmos_exceptions.CosmosHttpResponseError as e:
            logger.error(
                f"AzureCosmosDocumentStore: failed to query foreign collection " f"'{from_collection}' in $lookup - {e}"
            )
            # Raise an exception rather than returning potentially incorrect results
            # If we return documents with empty arrays, subsequent $match stages could
            # produce incorrect results (e.g., matching all documents as having no related records)
            raise DocumentStoreError(
                f"Failed to query foreign collection '{from_collection}' during $lookup aggregation"
            ) from e

        # Build an index of foreign documents by foreign_field for efficient lookup
        foreign_index: dict[Any, list[dict[str, Any]]] = {}
        for foreign_doc in foreign_docs:
            # Handle nested field access (e.g., "user.email")
            foreign_value = self._get_nested_field(foreign_doc, foreign_field)
            if foreign_value is not None:
                if foreign_value not in foreign_index:
                    foreign_index[foreign_value] = []
                foreign_index[foreign_value].append(foreign_doc)

        # Perform the join
        results = []
        for doc in documents:
            # Make a shallow copy to avoid modifying the original
            # Note: This is a shallow copy which is sufficient since we only add a new top-level field
            # The original document's nested structures remain as references, which is acceptable
            # since we don't modify them
            doc_copy = dict(doc)

            # Get the local field value
            local_value = self._get_nested_field(doc, local_field)

            # Find matching foreign documents
            if local_value is not None and local_value in foreign_index:
                # Deep copy the foreign documents to avoid shared mutable state
                # Multiple documents may join with the same foreign documents, so we need
                # to ensure each gets independent copies to prevent modifications from
                # affecting other joined results
                doc_copy[as_field] = [copy.deepcopy(fdoc) for fdoc in foreign_index[local_value]]
            else:
                doc_copy[as_field] = []

            results.append(doc_copy)

        return results

    def _get_nested_field(self, doc: dict[str, Any], field_path: str) -> Any:
        """Get a nested field value from a document.

        Supports dot notation for nested fields (e.g., "user.email").

        Args:
            doc: Document to get field from
            field_path: Field path (may contain dots for nested access)

        Returns:
            Field value, or None if not found
        """
        if "." not in field_path:
            return doc.get(field_path)

        # Handle nested field access
        parts = field_path.split(".")
        value: Any = doc
        for part in parts:
            if not isinstance(value, dict):
                return None
            value = value.get(part)
            if value is None:
                return None

        return value
