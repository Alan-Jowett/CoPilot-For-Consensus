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


class DocumentAlreadyExistsError(DocumentStoreError):
    """Exception raised when attempting to insert a document that already exists."""

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
            DocumentAlreadyExistsError: If document with same ID already exists
            Exception: If insertion fails
        """
        pass

    @abstractmethod
    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Returned documents are sanitized to remove backend system fields
        (e.g., Cosmos _etag/_rid/_ts) and document store metadata fields
        (e.g., id/collection), and contain only schema-defined fields.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID

        Returns:
            Sanitized document data as dictionary, or None if not found
        """
        pass

    @abstractmethod
    def query_documents(
        self,
        collection: str,
        filter_dict: dict[str, Any],
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Returned documents are sanitized to remove backend system fields
        (e.g., Cosmos _etag/_rid/_ts) and document store metadata fields
        (e.g., id/collection), and contain only schema-defined fields.

        Args:
            collection: Name of the collection/table
            filter_dict: Filter criteria as dictionary
            limit: Maximum number of documents to return
            sort_by: Optional field name to sort results by
            sort_order: Sort order ('asc' or 'desc', default 'desc')

        Returns:
            List of sanitized matching documents

        Note:
            Documents with missing/null sort fields sort as the lowest value
            (first in ASC, last in DESC), matching Cosmos DB native behavior.
        """
        pass

    @abstractmethod
    def update_document(self, collection: str, doc_id: str, patch: dict[str, Any]) -> None:
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
