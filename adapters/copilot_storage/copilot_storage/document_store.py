# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract document store interface for NoSQL backends."""

from abc import ABC, abstractmethod
from typing import Any


class DocumentStoreError(Exception):
    """Base exception for document store errors."""
    pass


class DocumentStoreNotConnectedError(DocumentStoreError):
    """Exception raised when attempting operations on a disconnected store."""
    pass


class DocumentStoreConnectionError(DocumentStoreError):
    """Exception raised when connection to the document store fails."""
    pass


class DocumentNotFoundError(DocumentStoreError):
    """Exception raised when a document is not found."""
    pass


class DocumentStore(ABC):
    """Abstract base class for document storage backends."""

    @abstractmethod
    def connect(self) -> None:
        """Connect to the document store.

        Raises:
            DocumentStoreConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the document store."""
        pass

    @abstractmethod
    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document into the specified collection.

        Args:
            collection: Name of the collection/table
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            Exception: If insertion fails
        """
        pass

    @abstractmethod
    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID

        Returns:
            Document data as dictionary, or None if not found
        """
        pass

    @abstractmethod
    def query_documents(
        self, collection: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Args:
            collection: Name of the collection/table
            filter_dict: Filter criteria as dictionary
            limit: Maximum number of documents to return

        Returns:
            List of matching documents
        """
        pass

    @abstractmethod
    def update_document(
        self, collection: str, doc_id: str, patch: dict[str, Any]
    ) -> None:
        """Update a document with the provided patch.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID
            patch: Update data as dictionary

        Raises:
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If update operation fails
        """
        pass

    @abstractmethod
    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID

        Raises:
            DocumentNotFoundError: If document does not exist
            DocumentStoreError: If delete operation fails
        """
        pass


def create_document_store(
    store_type: str | None = None,
    **kwargs
) -> DocumentStore:
    """Factory function to create a document store.

    Args:
        store_type: Type of document store ("mongodb", "azurecosmos", "cosmos", "inmemory").
               Required parameter - must be explicitly provided.
               Note: "cosmos" is an alias for "azurecosmos"
        **kwargs: Additional store-specific arguments.

    Returns:
        DocumentStore instance

    Raises:
        ValueError: If store_type is not provided
        ValueError: If store_type is not recognized
    """
    if not store_type:
        raise ValueError("store_type is required for create_document_store (choose: 'mongodb', 'azurecosmos', 'cosmos', or 'inmemory')")

    # Normalize store type: "cosmos" is an alias for "azurecosmos"
    if store_type == "cosmos":
        store_type = "azurecosmos"

    if store_type == "mongodb":
        from .mongo_document_store import MongoDocumentStore

        # Build kwargs with caller-provided values (no defaults - let adapter validate)
        mongo_kwargs = {}

        # Host - use provided value only
        if "host" in kwargs:
            mongo_kwargs["host"] = kwargs["host"]

        # Port - use provided value only
        if "port" in kwargs:
            mongo_kwargs["port"] = kwargs["port"]

        # Database - use provided value only
        if "database" in kwargs:
            mongo_kwargs["database"] = kwargs["database"]

        # Username/password - use provided values if present
        if "username" in kwargs:
            mongo_kwargs["username"] = kwargs["username"]
        if "password" in kwargs:
            mongo_kwargs["password"] = kwargs["password"]

        # Pass any other kwargs that aren't MongoDB-specific
        for key, value in kwargs.items():
            if key not in ("host", "port", "database", "username", "password"):
                mongo_kwargs[key] = value

        return MongoDocumentStore(**mongo_kwargs)
    elif store_type == "azurecosmos":
        from .azure_cosmos_document_store import AzureCosmosDocumentStore

        # Build kwargs with caller-provided values or safe defaults
        cosmos_kwargs = {}

        # Endpoint - use provided value only
        if "endpoint" in kwargs:
            cosmos_kwargs["endpoint"] = kwargs["endpoint"]

        # Key - use provided value only
        if "key" in kwargs:
            cosmos_kwargs["key"] = kwargs["key"]

        # Database - use provided value or default
        if "database" in kwargs:
            cosmos_kwargs["database"] = kwargs["database"]
        else:
            cosmos_kwargs["database"] = "copilot"

        # Container - use provided value or default
        if "container" in kwargs:
            cosmos_kwargs["container"] = kwargs["container"]
        else:
            cosmos_kwargs["container"] = "documents"

        # Partition key - use provided value or default
        if "partition_key" in kwargs:
            cosmos_kwargs["partition_key"] = kwargs["partition_key"]
        else:
            cosmos_kwargs["partition_key"] = "/collection"

        # Validate required parameters
        if not cosmos_kwargs.get("endpoint") or not cosmos_kwargs.get("key"):
            raise ValueError("Azure Cosmos configuration requires 'endpoint' and 'key'")

        # Pass any other kwargs that aren't Cosmos-specific or MongoDB-specific
        # MongoDB-specific parameters (host, port, username, password) should be filtered out
        # to avoid passing them to the Azure Cosmos SDK which doesn't understand them
        mongodb_params = {"host", "port", "username", "password"}
        cosmos_params = {"endpoint", "key", "database", "container", "partition_key"}
        for key, value in kwargs.items():
            if key not in cosmos_params and key not in mongodb_params:
                cosmos_kwargs[key] = value

        return AzureCosmosDocumentStore(**cosmos_kwargs)
    elif store_type == "inmemory":
        from .inmemory_document_store import InMemoryDocumentStore
        return InMemoryDocumentStore()
    else:
        raise ValueError(f"Unknown store_type: {store_type}")
