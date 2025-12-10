# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract document store interface for NoSQL backends."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class DocumentStoreError(Exception):
    """Base exception for document store errors."""
    pass


class DocumentStoreNotConnectedError(DocumentStoreError):
    """Exception raised when attempting operations on a disconnected store."""
    pass


class DocumentStore(ABC):
    """Abstract base class for document storage backends."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the document store.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the document store."""
        pass

    @abstractmethod
    def insert_document(self, collection: str, doc: Dict[str, Any]) -> str:
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
    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
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
        self, collection: str, filter_dict: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
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
        self, collection: str, doc_id: str, patch: Dict[str, Any]
    ) -> bool:
        """Update a document with the provided patch.
        
        Args:
            collection: Name of the collection/table
            doc_id: Document ID
            patch: Update data as dictionary
            
        Returns:
            True if document exists and update succeeded, False if document not found
            (Note: Returns True even if no fields were actually modified)
        """
        pass

    @abstractmethod
    def delete_document(self, collection: str, doc_id: str) -> bool:
        """Delete a document by its ID.
        
        Args:
            collection: Name of the collection/table
            doc_id: Document ID
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        pass


def create_document_store(
    store_type: str = "inmemory",
    host: str = "localhost",
    port: int = 27017,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: str = "copilot",
    **kwargs
) -> DocumentStore:
    """Factory function to create a document store.
    
    Args:
        store_type: Type of document store ("mongodb", "inmemory")
        host: Database host (for mongodb)
        port: Database port (for mongodb)
        username: Database username (for mongodb)
        password: Database password (for mongodb)
        database: Database name (for mongodb)
        **kwargs: Additional store-specific arguments
        
    Returns:
        DocumentStore instance
        
    Raises:
        ValueError: If store_type is not recognized
    """
    if store_type == "mongodb":
        from .mongo_document_store import MongoDocumentStore
        return MongoDocumentStore(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            **kwargs
        )
    elif store_type == "inmemory":
        from .inmemory_document_store import InMemoryDocumentStore
        return InMemoryDocumentStore()
    else:
        raise ValueError(f"Unknown store_type: {store_type}")
