# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Cosmos DB document store implementation."""

import copy
import logging
import re
import uuid
from typing import Any

from .document_store import (
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
)

logger = logging.getLogger(__name__)

# Import azure.cosmos at module level to avoid repeated imports in methods
try:
    from azure.cosmos import exceptions as cosmos_exceptions
except ImportError:
    # Will be handled in connect() method
    cosmos_exceptions = None


class AzureCosmosDocumentStore(DocumentStore):
    """Azure Cosmos DB document store implementation using Core (SQL) API."""

    def __init__(
        self,
        endpoint: str = None,
        key: str = None,
        database: str = "copilot",
        container: str = "documents",
        partition_key: str = "/collection",
        **kwargs
    ):
        """Initialize Azure Cosmos DB document store.

        Args:
            endpoint: Cosmos DB endpoint URL (e.g., https://myaccount.documents.azure.com:443/)
            key: Cosmos DB account key (optional; if None, managed identity via DefaultAzureCredential will be used)
            database: Database name
            container: Container name
            partition_key: Partition key path (default: /collection)
            **kwargs: Additional Cosmos client options (e.g., connection_timeout, request_timeout)
        """
        self.endpoint = endpoint
        self.key = key
        self.database_name = database
        self.container_name = container
        self.partition_key = partition_key
        self.client_options = kwargs
        self.client = None
        self.database = None
        self.container = None

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
        if not re.match(r'^[a-zA-Z0-9_.]+$', field_name):
            return False

        # Then, validate each component between dots to prevent empty segments
        # or other invalid patterns (e.g., "user..email")
        components = field_name.split(".")
        if any(not component or not re.match(r'^[a-zA-Z0-9_]+$', component) for component in components):
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
        invalid_chars = ['/', '\\', '#', '?']
        if any(char in doc_id for char in invalid_chars):
            return False

        # Check for control characters
        if any(ord(char) < 32 for char in doc_id):
            return False

        return True

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
                self.database = self.client.create_database_if_not_exists(id=self.database_name)
                logger.info(f"AzureCosmosDocumentStore: using database '{self.database_name}'")
            except cosmos_exceptions.CosmosHttpResponseError as e:
                logger.error(f"AzureCosmosDocumentStore: failed to create/access database - {e}")
                raise DocumentStoreConnectionError(f"Failed to create/access database '{self.database_name}'") from e

            # Get or create container with partition key
            try:
                self.container = self.database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key={"paths": [self.partition_key], "kind": "Hash"}
                )
                logger.info(
                    f"AzureCosmosDocumentStore: using container '{self.container_name}' "
                    f"with partition key '{self.partition_key}'"
                )
            except cosmos_exceptions.CosmosHttpResponseError as e:
                logger.error(
                    f"AzureCosmosDocumentStore: failed to create/access container - {e}"
                )
                raise DocumentStoreConnectionError(
                    f"Failed to create/access container '{self.container_name}'"
                ) from e

            logger.info(
                f"AzureCosmosDocumentStore: connected to "
                f"{self.endpoint}/{self.database_name}/{self.container_name}"
            )

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
            self.container = None
            logger.info("AzureCosmosDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document into the specified collection.

        In Cosmos DB, we store all collections in a single container, using the
        'collection' field as the logical collection name and partition key.

        Args:
            collection: Name of the logical collection
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If insertion fails
        """
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Generate ID if not provided
            doc_id = doc.get("id", str(uuid.uuid4()))

            # Validate document ID meets Cosmos DB requirements
            if not self._is_valid_document_id(doc_id):
                raise DocumentStoreError(
                    f"Invalid document ID '{doc_id}': IDs cannot contain '/', '\\', '#', '?', or control characters"
                )

            # Create a deep copy to avoid modifying the original (including nested structures)
            doc_copy = copy.deepcopy(doc)
            doc_copy["id"] = doc_id
            doc_copy["collection"] = collection  # Add collection field for partitioning

            # Insert document
            self.container.create_item(body=doc_copy)
            logger.debug(f"AzureCosmosDocumentStore: inserted document {doc_id} into {collection}")

            return doc_id

        except cosmos_exceptions.CosmosResourceExistsError as e:
            logger.error(f"AzureCosmosDocumentStore: document with id {doc_id} already exists - {e}")
            raise DocumentStoreError(f"Document with id {doc_id} already exists in collection {collection}") from e
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

        Args:
            collection: Name of the logical collection
            doc_id: Document ID

        Returns:
            Document data as dictionary, or None if not found

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If query operation fails
        """
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Read document using partition key
            doc = self.container.read_item(
                item=doc_id,
                partition_key=collection
            )

            logger.debug(f"AzureCosmosDocumentStore: retrieved document {doc_id} from {collection}")
            return doc

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
        self, collection: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Args:
            collection: Name of the logical collection
            filter_dict: Filter criteria as dictionary (simple equality checks)
            limit: Maximum number of documents to return

        Returns:
            List of matching documents (empty list if no matches)

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If query operation fails
        """
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Build SQL query for Cosmos DB
            query = "SELECT * FROM c WHERE c.collection = @collection"
            parameters = [{"name": "@collection", "value": collection}]

            # Add filter conditions
            for idx, (key, value) in enumerate(filter_dict.items()):
                # Validate field name to prevent SQL injection
                if not self._is_valid_field_name(key):
                    logger.warning(f"AzureCosmosDocumentStore: skipping invalid field name '{key}'")
                    continue
                param_name = f"@param{idx}"
                query += f" AND c.{key} = {param_name}"
                parameters.append({"name": param_name, "value": value})

            # Add limit (validate to prevent SQL injection)
            # Cosmos DB requires OFFSET...LIMIT syntax, not standalone LIMIT
            if not isinstance(limit, int) or limit < 1:
                raise DocumentStoreError(f"Invalid limit value '{limit}': must be a positive integer")
            query += f" OFFSET 0 LIMIT {limit}"

            # Execute query
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=False,
                partition_key=collection
            ))

            logger.debug(
                f"AzureCosmosDocumentStore: query on {collection} with {filter_dict} "
                f"returned {len(items)} documents"
            )
            return items

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

    def update_document(
        self, collection: str, doc_id: str, patch: dict[str, Any]
    ) -> None:
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
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Read the existing document
            try:
                existing_doc = self.container.read_item(
                    item=doc_id,
                    partition_key=collection
                )
            except cosmos_exceptions.CosmosResourceNotFoundError:
                logger.debug(f"AzureCosmosDocumentStore: document {doc_id} not found in {collection}")
                raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

            # Apply patch to a copy to avoid mutating the original document in-place
            merged_doc = dict(existing_doc)
            if patch:
                merged_doc.update(patch)

            # Ensure collection field is not modified
            merged_doc["collection"] = collection

            # Replace document
            self.container.replace_item(
                item=doc_id,
                body=merged_doc
            )

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
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Delete document
            self.container.delete_item(
                item=doc_id,
                partition_key=collection
            )

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

    def aggregate_documents(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute an aggregation pipeline on a collection.

        Note: This is a simplified implementation that supports common aggregation stages
        for compatibility with MongoDB-style pipelines. Cosmos DB uses SQL queries, so
        we translate simple pipelines to SQL.

        Supported stages: $match, $limit

        Args:
            collection: Name of the logical collection
            pipeline: Aggregation pipeline (list of stage dictionaries)

        Returns:
            List of aggregation results

        Raises:
            DocumentStoreNotConnectedError: If not connected to Cosmos DB
            DocumentStoreError: If aggregation operation fails
        """
        if self.container is None:
            raise DocumentStoreNotConnectedError("Not connected to Cosmos DB")

        try:
            # Build SQL query from pipeline
            query = "SELECT * FROM c WHERE c.collection = @collection"
            parameters = [{"name": "@collection", "value": collection}]
            limit_value = None
            param_counter = 0  # Track unique parameter names

            for stage in pipeline:
                stage_name = list(stage.keys())[0]
                stage_spec = stage[stage_name]

                if stage_name == "$match":
                    # Add match conditions to WHERE clause
                    for key, condition in stage_spec.items():
                        # Validate field name to prevent SQL injection
                        if not self._is_valid_field_name(key):
                            logger.warning(f"AzureCosmosDocumentStore: skipping invalid field name '{key}'")
                            continue

                        if isinstance(condition, dict):
                            # Handle operators
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
                                else:
                                    logger.warning(
                                        f"AzureCosmosDocumentStore: unsupported operator '{op}' in $match, skipping"
                                    )
                        else:
                            # Simple equality check
                            param_name = f"@param{param_counter}"
                            param_counter += 1
                            query += f" AND c.{key} = {param_name}"
                            parameters.append({"name": param_name, "value": condition})

                elif stage_name == "$limit":
                    limit_value = stage_spec

                elif stage_name == "$lookup":
                    # Cosmos DB doesn't support joins like MongoDB
                    # This would require multiple queries and client-side joining
                    logger.warning(
                        "AzureCosmosDocumentStore: $lookup not supported, skipping"
                    )

                else:
                    logger.warning(
                        f"AzureCosmosDocumentStore: aggregation stage '{stage_name}' not implemented, skipping"
                    )

            # Add limit if specified
            # Cosmos DB requires OFFSET...LIMIT syntax, not standalone LIMIT
            if limit_value is not None:
                # Validate limit value to prevent SQL injection
                if not isinstance(limit_value, int) or limit_value < 1:
                    raise DocumentStoreError(f"Invalid limit value '{limit_value}': must be a positive integer")
                query += f" OFFSET 0 LIMIT {limit_value}"

            # Execute query
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=False,
                partition_key=collection
            ))

            logger.debug(
                f"AzureCosmosDocumentStore: aggregation on {collection} "
                f"returned {len(items)} documents"
            )
            return items

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
