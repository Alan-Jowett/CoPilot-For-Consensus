# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""MongoDB document store implementation."""

import logging
from typing import Any

from copilot_config import DriverConfig

from .document_store import (
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
)

logger = logging.getLogger(__name__)


class MongoDocumentStore(DocumentStore):
    """MongoDB document store implementation."""

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "MongoDocumentStore":
        """Create a MongoDocumentStore from configuration.

        Args:
            driver_config: Configuration object with host, port, database, username, password attributes.

        Returns:
            Configured MongoDocumentStore instance

        Raises:
            AttributeError: If required config attributes are missing
        """
        host = getattr(driver_config, "host", None)
        port = getattr(driver_config, "port", None)
        username = getattr(driver_config, "username", None)
        password = getattr(driver_config, "password", None)
        database = getattr(driver_config, "database", None)

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        **kwargs
    ):
        """Initialize MongoDB document store.

        Args:
            host: MongoDB host (required)
            port: MongoDB port (required)
            username: MongoDB username (optional)
            password: MongoDB password (optional)
            database: Database name (required)
            **kwargs: Additional MongoDB client options

        Raises:
            ValueError: If required parameters (host, port, database) are not provided
        """
        if not host:
            raise ValueError(
                "MongoDB host is required. "
                "Provide the MongoDB server hostname or IP address."
            )
        if port is None:
            raise ValueError(
                "MongoDB port is required. "
                "Provide the MongoDB server port number."
            )
        if not database:
            raise ValueError(
                "MongoDB database is required. "
                "Provide the database name to use."
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database_name = database
        self.client_options = kwargs
        self.client = None
        self.database = None

    def connect(self) -> None:
        """Connect to MongoDB.

        Raises:
            DocumentStoreConnectionError: If connection fails
        """
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure
        except ImportError as e:
            logger.error("MongoDocumentStore: pymongo not installed")
            raise DocumentStoreConnectionError("pymongo not installed") from e

        try:
            # Build connection using separate auth parameters (more secure than URI)
            connection_params = {
                "host": self.host,
                "port": self.port,
            }

            # Add authentication if provided
            if self.username and self.password:
                connection_params["username"] = self.username
                connection_params["password"] = self.password
                # Use admin database for authentication by default if not specified
                if "authSource" not in self.client_options:
                    connection_params["authSource"] = "admin"

            # Merge additional client options
            connection_params.update(self.client_options)

            # Create client with options
            self.client = MongoClient(**connection_params)

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.database = self.client[self.database_name]

            logger.info("MongoDocumentStore: connected to %s:%s/%s", self.host, self.port, self.database_name)

        except ConnectionFailure as e:
            logger.error("MongoDocumentStore: connection failed - %s", e, exc_info=True)
            raise DocumentStoreConnectionError(f"Failed to connect to MongoDB at {self.host}:{self.port}") from e
        except Exception as e:
            logger.error("MongoDocumentStore: unexpected error during connect - %s", e, exc_info=True)
            raise DocumentStoreConnectionError(f"Unexpected error connecting to MongoDB: {str(e)}") from e

    def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            logger.info("MongoDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document into the specified collection.

        Args:
            collection: Name of the collection
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            coll = self.database[collection]
            result = coll.insert_one(doc)
            doc_id = str(result.inserted_id)
            logger.debug(f"MongoDocumentStore: inserted document {doc_id} into {collection}")
            return doc_id
        except Exception as e:
            logger.error(f"MongoDocumentStore: insert failed - {e}")
            raise

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Args:
            collection: Name of the collection
            doc_id: Document ID

        Returns:
            Document data as dictionary, or None if not found

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
            DocumentStoreError: If query operation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            from bson import ObjectId
            from bson.errors import InvalidId

            coll = self.database[collection]

            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError, InvalidId):
                # Use as string if not a valid ObjectId
                query = {"_id": doc_id}

            doc = coll.find_one(query)

            if doc:
                # Convert ObjectId to string for serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                logger.debug(f"MongoDocumentStore: retrieved document {doc_id} from {collection}")
                return doc

            logger.debug(f"MongoDocumentStore: document {doc_id} not found in {collection}")
            return None

        except Exception as e:
            logger.error(f"MongoDocumentStore: get_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to retrieve document {doc_id} from {collection}") from e

    def query_documents(
        self, collection: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Args:
            collection: Name of the collection
            filter_dict: Filter criteria as dictionary (MongoDB query format)
            limit: Maximum number of documents to return

        Returns:
            List of matching documents (empty list if no matches)

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
            DocumentStoreError: If query operation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            coll = self.database[collection]
            cursor = coll.find(filter_dict).limit(limit)

            results = []
            for doc in cursor:
                # Convert ObjectId to string for serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                results.append(doc)

            logger.debug(
                f"MongoDocumentStore: query on {collection} with {filter_dict} "
                f"returned {len(results)} documents"
            )
            return results

        except Exception as e:
            logger.error(f"MongoDocumentStore: query_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to query documents from {collection}") from e

    def update_document(
        self, collection: str, doc_id: str, patch: dict[str, Any]
    ) -> None:
        """Update a document with the provided patch.

        Args:
            collection: Name of the collection
            doc_id: Document ID
            patch: Update data as dictionary

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If update operation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            from bson import ObjectId
            from bson.errors import InvalidId

            coll = self.database[collection]

            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError, InvalidId):
                query = {"_id": doc_id}

            # Use $set operator for patch updates
            result = coll.update_one(query, {"$set": patch})

            if result.matched_count == 0:
                logger.debug(f"MongoDocumentStore: document {doc_id} not found in {collection}")
                raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

            logger.debug(f"MongoDocumentStore: updated document {doc_id} in {collection}")

        except (DocumentStoreNotConnectedError, DocumentNotFoundError):
            raise
        except Exception as e:
            logger.error(f"MongoDocumentStore: update_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to update document {doc_id} in {collection}") from e

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.

        Args:
            collection: Name of the collection
            doc_id: Document ID

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If delete operation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            from bson import ObjectId
            from bson.errors import InvalidId

            coll = self.database[collection]

            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError, InvalidId):
                query = {"_id": doc_id}

            result = coll.delete_one(query)

            if result.deleted_count == 0:
                logger.debug(f"MongoDocumentStore: document {doc_id} not found in {collection}")
                raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

            logger.debug(f"MongoDocumentStore: deleted document {doc_id} from {collection}")

        except (DocumentStoreNotConnectedError, DocumentNotFoundError):
            raise
        except Exception as e:
            logger.error(f"MongoDocumentStore: delete_document failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to delete document {doc_id} from {collection}") from e

    def aggregate_documents(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute an aggregation pipeline on a collection.

        **Note**: ObjectId values are recursively converted to strings for JSON
        serialization compatibility. This handles ObjectIds in nested documents
        (e.g., from $lookup stages).

        Args:
            collection: Name of the collection
            pipeline: MongoDB aggregation pipeline (list of stage dictionaries)

        Returns:
            List of aggregation results

        Raises:
            DocumentStoreNotConnectedError: If not connected to MongoDB
            DocumentStoreError: If aggregation operation fails
        """
        if self.database is None:
            raise DocumentStoreNotConnectedError("Not connected to MongoDB")

        try:
            coll = self.database[collection]
            cursor = coll.aggregate(pipeline)

            results = []
            for doc in cursor:
                # Recursively convert all ObjectId instances to strings
                self._convert_objectids_to_strings(doc)
                results.append(doc)

            logger.debug(
                f"MongoDocumentStore: aggregation on {collection} "
                f"returned {len(results)} documents"
            )
            return results

        except Exception as e:
            logger.error(f"MongoDocumentStore: aggregate_documents failed - {e}", exc_info=True)
            raise DocumentStoreError(f"Failed to aggregate documents from {collection}") from e

    def _convert_objectids_to_strings(self, obj: Any) -> None:
        """Recursively convert ObjectId instances to strings in-place.

        Args:
            obj: Object to convert (dict, list, or primitive)
        """
        from bson import ObjectId

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, ObjectId):
                    obj[key] = str(value)
                elif isinstance(value, dict | list):
                    self._convert_objectids_to_strings(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, ObjectId):
                    obj[i] = str(item)
                elif isinstance(item, dict | list):
                    self._convert_objectids_to_strings(item)
