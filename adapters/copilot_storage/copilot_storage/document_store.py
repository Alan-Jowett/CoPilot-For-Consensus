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
    store_type: str = None,
    **kwargs
) -> DocumentStore:
    """Factory function to create a document store.
    
    Args:
        store_type: Type of document store ("mongodb", "inmemory"). 
                   If None, reads from DOCUMENT_STORE_TYPE environment variable (defaults to "inmemory")
        **kwargs: Additional store-specific arguments. For MongoDB, if not provided, 
                 will read from MONGO_* environment variables.
        
    Returns:
        DocumentStore instance
        
    Raises:
        ValueError: If store_type is not recognized
    """
    import os
    
    # Auto-detect store type from environment if not provided
    if store_type is None:
        store_type = os.getenv("DOCUMENT_STORE_TYPE", "inmemory").lower()
    
    if store_type == "mongodb":
        from .mongo_document_store import MongoDocumentStore
        
        # If no kwargs provided, read from environment
        if not kwargs:
            kwargs = {
                "host": os.getenv("MONGO_HOST", "localhost"),
                "port": int(os.getenv("MONGO_PORT", "27017")),
                "database": os.getenv("MONGO_DB", "copilot"),
            }
            # Only add credentials if they're set
            if os.getenv("MONGO_USER"):
                kwargs["username"] = os.getenv("MONGO_USER")
            if os.getenv("MONGO_PASSWORD"):
                kwargs["password"] = os.getenv("MONGO_PASSWORD")
        
        return MongoDocumentStore(**kwargs)
    elif store_type == "inmemory":
        from .inmemory_document_store import InMemoryDocumentStore
        return InMemoryDocumentStore()
    else:
        raise ValueError(f"Unknown store_type: {store_type}")
