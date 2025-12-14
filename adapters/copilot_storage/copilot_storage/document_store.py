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
    store_type: str = None,
    **kwargs
) -> DocumentStore:
    """Factory function to create a document store.
    
    Args:
        store_type: Type of document store ("mongodb", "inmemory"). 
                   If None, reads from DOCUMENT_STORE_TYPE environment variable (defaults to "inmemory")
        **kwargs: Additional store-specific arguments. For MongoDB, if not provided, 
                 will read from DOC_DB_* environment variables (with fallback to MONGO_* for backward compatibility).
        
    Returns:
        DocumentStore instance
        
    Raises:
        ValueError: If store_type is not recognized
    """
    import os
    import warnings
    
    # Auto-detect store type from environment if not provided
    if store_type is None:
        store_type = os.getenv("DOCUMENT_STORE_TYPE", "inmemory").lower()
    
    if store_type == "mongodb":
        from .mongo_document_store import MongoDocumentStore
        
        # Build kwargs with environment variable fallback for individual parameters
        # Explicit parameters take precedence over environment variables
        # DOC_DB_* variables take precedence over MONGO_* (deprecated)
        mongo_kwargs = {}
        
        # Host - use provided value or DOC_DB_HOST or MONGO_HOST (deprecated)
        if "host" in kwargs:
            mongo_kwargs["host"] = kwargs["host"]
        else:
<<<<<<< HEAD
            mongo_kwargs["host"] = os.getenv("DOC_DB_HOST", "localhost")
=======
            doc_db_host = os.getenv("DOC_DB_HOST")
            mongo_host = os.getenv("MONGO_HOST")
            if doc_db_host:
                mongo_kwargs["host"] = doc_db_host
            elif mongo_host:
                warnings.warn(
                    "MONGO_HOST is deprecated. Please use DOC_DB_HOST instead.",
                    DeprecationWarning,
                    stacklevel=2
                )
                mongo_kwargs["host"] = mongo_host
            else:
                mongo_kwargs["host"] = "localhost"
>>>>>>> 7faf98c (Standardize env vars on DOC_DB_* in docker-compose and add backward compatibility)
        
        # Port - use provided value or DOC_DB_PORT or MONGO_PORT (deprecated)
        if "port" in kwargs:
            mongo_kwargs["port"] = kwargs["port"]
        else:
<<<<<<< HEAD
            mongo_kwargs["port"] = int(os.getenv("DOC_DB_PORT", "27017"))
=======
            doc_db_port = os.getenv("DOC_DB_PORT")
            mongo_port = os.getenv("MONGO_PORT")
            if doc_db_port:
                mongo_kwargs["port"] = int(doc_db_port)
            elif mongo_port:
                warnings.warn(
                    "MONGO_PORT is deprecated. Please use DOC_DB_PORT instead.",
                    DeprecationWarning,
                    stacklevel=2
                )
                mongo_kwargs["port"] = int(mongo_port)
            else:
                mongo_kwargs["port"] = 27017
>>>>>>> 7faf98c (Standardize env vars on DOC_DB_* in docker-compose and add backward compatibility)
        
        # Database - use provided value or DOC_DB_NAME or MONGO_DB (deprecated)
        if "database" in kwargs:
            mongo_kwargs["database"] = kwargs["database"]
        else:
<<<<<<< HEAD
            mongo_kwargs["database"] = os.getenv("DOC_DB_NAME", "copilot")
=======
            doc_db_name = os.getenv("DOC_DB_NAME")
            mongo_db = os.getenv("MONGO_DB")
            if doc_db_name:
                mongo_kwargs["database"] = doc_db_name
            elif mongo_db:
                warnings.warn(
                    "MONGO_DB is deprecated. Please use DOC_DB_NAME instead.",
                    DeprecationWarning,
                    stacklevel=2
                )
                mongo_kwargs["database"] = mongo_db
            else:
                mongo_kwargs["database"] = "copilot"
>>>>>>> 7faf98c (Standardize env vars on DOC_DB_* in docker-compose and add backward compatibility)
        
        # Username - use provided value or DOC_DB_USER or MONGO_USER (deprecated)
        if "username" in kwargs:
            mongo_kwargs["username"] = kwargs["username"]
        else:
            doc_db_user = os.getenv("DOC_DB_USER")
<<<<<<< HEAD
            if doc_db_user is not None:
                mongo_kwargs["username"] = doc_db_user
=======
            mongo_user = os.getenv("MONGO_USER")
            if doc_db_user is not None:
                mongo_kwargs["username"] = doc_db_user
            elif mongo_user is not None:
                warnings.warn(
                    "MONGO_USER is deprecated. Please use DOC_DB_USER instead.",
                    DeprecationWarning,
                    stacklevel=2
                )
                mongo_kwargs["username"] = mongo_user
>>>>>>> 7faf98c (Standardize env vars on DOC_DB_* in docker-compose and add backward compatibility)
        
        # Password - use provided value or DOC_DB_PASSWORD or MONGO_PASSWORD (deprecated)
        if "password" in kwargs:
            mongo_kwargs["password"] = kwargs["password"]
        else:
            doc_db_password = os.getenv("DOC_DB_PASSWORD")
<<<<<<< HEAD
            if doc_db_password is not None:
                mongo_kwargs["password"] = doc_db_password
=======
            mongo_password = os.getenv("MONGO_PASSWORD")
            if doc_db_password is not None:
                mongo_kwargs["password"] = doc_db_password
            elif mongo_password is not None:
                warnings.warn(
                    "MONGO_PASSWORD is deprecated. Please use DOC_DB_PASSWORD instead.",
                    DeprecationWarning,
                    stacklevel=2
                )
                mongo_kwargs["password"] = mongo_password
>>>>>>> 7faf98c (Standardize env vars on DOC_DB_* in docker-compose and add backward compatibility)
        
        # Pass any other kwargs that aren't MongoDB-specific
        for key, value in kwargs.items():
            if key not in ("host", "port", "database", "username", "password"):
                mongo_kwargs[key] = value
        
        return MongoDocumentStore(**mongo_kwargs)
    elif store_type == "inmemory":
        from .inmemory_document_store import InMemoryDocumentStore
        return InMemoryDocumentStore()
    else:
        raise ValueError(f"Unknown store_type: {store_type}")
