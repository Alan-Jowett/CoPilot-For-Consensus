# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""In-memory document store for testing and local development."""

import copy
import logging
import uuid
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .document_store import (
    DocumentStore,
    DocumentNotFoundError
)

logger = logging.getLogger(__name__)


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store implementation for testing."""

    def __init__(self):
        """Initialize in-memory document store."""
        self.collections: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.connected = False

    def connect(self) -> None:
        """Pretend to connect.
        
        Note: Always succeeds for in-memory store
        """
        self.connected = True
        logger.debug("InMemoryDocumentStore: connected")

    def disconnect(self) -> None:
        """Pretend to disconnect."""
        self.connected = False
        logger.debug("InMemoryDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: Dict[str, Any]) -> str:
        """Insert a document into the specified collection.
        
        Args:
            collection: Name of the collection
            doc: Document data as dictionary
            
        Returns:
            Document ID as string
        """
        # Generate ID if not provided
        doc_id = doc.get("_id", str(uuid.uuid4()))
        
        # Make a deep copy to avoid external mutations affecting stored data
        doc_copy = copy.deepcopy(doc)
        doc_copy["_id"] = doc_id
        
        self.collections[collection][doc_id] = doc_copy
        logger.debug(f"InMemoryDocumentStore: inserted document {doc_id} into {collection}")
        
        return doc_id

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            
        Returns:
            Document data as dictionary, or None if not found
        """
        doc = self.collections[collection].get(doc_id)
        if doc:
            logger.debug(f"InMemoryDocumentStore: retrieved document {doc_id} from {collection}")
            # Return a deep copy to prevent external mutations affecting stored data
            return copy.deepcopy(doc)
        logger.debug(f"InMemoryDocumentStore: document {doc_id} not found in {collection}")
        return None

    def query_documents(
        self, collection: str, filter_dict: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query documents matching the filter criteria.
        
        Args:
            collection: Name of the collection
            filter_dict: Filter criteria as dictionary (simple equality checks)
            limit: Maximum number of documents to return
            
        Returns:
            List of matching documents
        """
        results = []
        
        for doc in self.collections[collection].values():
            # Check if document matches all filter criteria
            matches = all(
                doc.get(key) == value
                for key, value in filter_dict.items()
            )
            
            if matches:
                # Use deep copy to prevent external mutations affecting stored data
                results.append(copy.deepcopy(doc))
                if len(results) >= limit:
                    break
        
        logger.debug(
            f"InMemoryDocumentStore: query on {collection} with {filter_dict} "
            f"returned {len(results)} documents"
        )
        return results

    def update_document(
        self, collection: str, doc_id: str, patch: Dict[str, Any]
    ) -> None:
        """Update a document with the provided patch.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            patch: Update data as dictionary
            
        Raises:
            DocumentNotFoundError: If document does not exist
        """
        if doc_id not in self.collections[collection]:
            logger.debug(
                f"InMemoryDocumentStore: document {doc_id} not found in {collection}"
            )
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")
        
        # Apply patch to document
        self.collections[collection][doc_id].update(patch)
        logger.debug(f"InMemoryDocumentStore: updated document {doc_id} in {collection}")

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            
        Raises:
            DocumentNotFoundError: If document does not exist
        """
        if doc_id in self.collections[collection]:
            del self.collections[collection][doc_id]
            logger.debug(f"InMemoryDocumentStore: deleted document {doc_id} from {collection}")
        else:
            logger.debug(f"InMemoryDocumentStore: document {doc_id} not found in {collection}")
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

    def clear_collection(self, collection: str) -> None:
        """Clear all documents in a collection (useful for testing).
        
        Args:
            collection: Name of the collection
        """
        self.collections[collection].clear()
        logger.debug(f"InMemoryDocumentStore: cleared collection {collection}")

    def clear_all(self) -> None:
        """Clear all collections (useful for testing)."""
        self.collections.clear()
        logger.debug("InMemoryDocumentStore: cleared all collections")
