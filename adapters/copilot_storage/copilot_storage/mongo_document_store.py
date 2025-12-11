# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""MongoDB document store implementation."""

import logging
from typing import Dict, Any, List, Optional

from .document_store import DocumentStore, DocumentStoreNotConnectedError

logger = logging.getLogger(__name__)


class MongoDocumentStore(DocumentStore):
    """MongoDB document store implementation."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "copilot",
        **kwargs
    ):
        """Initialize MongoDB document store.
        
        Args:
            host: MongoDB host
            port: MongoDB port
            username: MongoDB username (optional)
            password: MongoDB password (optional)
            database: Database name
            **kwargs: Additional MongoDB client options
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database_name = database
        self.client_options = kwargs
        self.client = None
        self.database = None

    def connect(self) -> bool:
        """Connect to MongoDB.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure
        except ImportError:
            logger.error("MongoDocumentStore: pymongo not installed")
            return False
        
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
            return True
            
        except ConnectionFailure as e:
            logger.error("MongoDocumentStore: connection failed - %s", e)
            return False
        except Exception as e:
            logger.error("MongoDocumentStore: unexpected error during connect - %s", e)
            return False

    def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            logger.info("MongoDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: Dict[str, Any]) -> str:
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

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            
        Returns:
            Document data as dictionary, or None if not found
        """
        if self.database is None:
            logger.error("MongoDocumentStore: not connected")
            return None
        
        try:
            from bson import ObjectId
            
            coll = self.database[collection]
            
            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError):
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
            logger.error(f"MongoDocumentStore: get_document failed - {e}")
            return None

    def query_documents(
        self, collection: str, filter_dict: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query documents matching the filter criteria.
        
        Args:
            collection: Name of the collection
            filter_dict: Filter criteria as dictionary (MongoDB query format)
            limit: Maximum number of documents to return
            
        Returns:
            List of matching documents
        """
        if self.database is None:
            logger.error("MongoDocumentStore: not connected")
            return []
        
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
            logger.error(f"MongoDocumentStore: query_documents failed - {e}")
            return []

    def update_document(
        self, collection: str, doc_id: str, patch: Dict[str, Any]
    ) -> bool:
        """Update a document with the provided patch.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            patch: Update data as dictionary
            
        Returns:
            True if document exists and update succeeded, False if document not found
        """
        if self.database is None:
            logger.error("MongoDocumentStore: not connected")
            return False
        
        try:
            from bson import ObjectId
            
            coll = self.database[collection]
            
            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError):
                query = {"_id": doc_id}
            
            # Use $set operator for patch updates
            result = coll.update_one(query, {"$set": patch})
            
            success = result.modified_count > 0 or result.matched_count > 0
            if success:
                logger.debug(f"MongoDocumentStore: updated document {doc_id} in {collection}")
            else:
                logger.debug(f"MongoDocumentStore: document {doc_id} not found in {collection}")
            
            return success
            
        except Exception as e:
            logger.error(f"MongoDocumentStore: update_document failed - {e}")
            return False

    def delete_document(self, collection: str, doc_id: str) -> bool:
        """Delete a document by its ID.
        
        Args:
            collection: Name of the collection
            doc_id: Document ID
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        if self.database is None:
            logger.error("MongoDocumentStore: not connected")
            return False
        
        try:
            from bson import ObjectId
            
            coll = self.database[collection]
            
            # Try to convert to ObjectId if possible
            try:
                query = {"_id": ObjectId(doc_id)}
            except (TypeError, ValueError):
                query = {"_id": doc_id}
            
            result = coll.delete_one(query)
            
            success = result.deleted_count > 0
            if success:
                logger.debug(f"MongoDocumentStore: deleted document {doc_id} from {collection}")
            else:
                logger.debug(f"MongoDocumentStore: document {doc_id} not found in {collection}")
            
            return success
            
        except Exception as e:
            logger.error(f"MongoDocumentStore: delete_document failed - {e}")
            return False
