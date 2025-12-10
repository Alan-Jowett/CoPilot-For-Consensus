# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""MongoDB-based schema provider for loading schemas from the database.

Used in production environments where schemas are stored in the MongoDB
event_schemas collection.
"""

from typing import Dict, Optional
import logging

from .schema_provider import SchemaProvider

logger = logging.getLogger(__name__)


class MongoSchemaProvider(SchemaProvider):
    """Schema provider that loads schemas from MongoDB event_schemas collection."""

    def __init__(
        self,
        mongo_uri: str,
        database_name: str = "copilot",
        collection_name: str = "event_schemas"
    ):
        """Initialize the MongoDB-based schema provider.

        Args:
            mongo_uri: MongoDB connection URI (e.g., 'mongodb://host:port/')
            database_name: Name of the database containing schemas (default: 'copilot')
            collection_name: Name of the collection containing schemas (default: 'event_schemas')
        """
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        self.collection_name = collection_name
        self._schema_cache: Dict[str, Dict] = {}
        self._client = None
        self._collection = None

        try:
            from pymongo import MongoClient
            self._pymongo_available = True
        except ImportError:
            self._pymongo_available = False
            logger.error(
                "pymongo is not installed. Install it with: pip install pymongo"
            )

    def _ensure_connected(self) -> bool:
        """Ensure MongoDB connection is established.

        Returns:
            True if connected, False otherwise
        """
        if not self._pymongo_available:
            return False

        if self._collection is not None:
            return True

        try:
            from pymongo import MongoClient
            self._client = MongoClient(self.mongo_uri)
            db = self._client[self.database_name]
            self._collection = db[self.collection_name]
            logger.info(
                f"Connected to MongoDB: {self.database_name}.{self.collection_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False

    def get_schema(self, event_type: str) -> Optional[Dict]:
        """Retrieve the JSON schema for a given event type from MongoDB.

        Args:
            event_type: The event type name (e.g., 'ArchiveIngested')

        Returns:
            The JSON schema as a dictionary, or None if not found
        """
        # Check cache first
        if event_type in self._schema_cache:
            return self._schema_cache[event_type]

        if not self._ensure_connected():
            logger.error("Cannot retrieve schema: MongoDB connection not available")
            return None

        try:
            # Query MongoDB for the schema document
            doc = self._collection.find_one({"name": event_type})
            if doc is None:
                logger.warning(f"Schema not found in MongoDB for event type: {event_type}")
                return None

            # Extract the schema field
            schema = doc.get("schema")
            if schema is None:
                logger.error(f"Schema document for '{event_type}' is missing 'schema' field")
                return None

            # Cache and return
            self._schema_cache[event_type] = schema
            logger.debug(f"Loaded schema from MongoDB for event type: {event_type}")
            return schema
        except Exception as e:
            logger.error(f"Error retrieving schema from MongoDB for '{event_type}': {e}")
            return None

    def list_event_types(self) -> list[str]:
        """List all available event types from MongoDB.

        Returns:
            List of event type names
        """
        if not self._ensure_connected():
            logger.error("Cannot list event types: MongoDB connection not available")
            return []

        try:
            # Query all documents and extract their names
            cursor = self._collection.find({}, {"name": 1, "_id": 0})
            event_types = [doc["name"] for doc in cursor if "name" in doc]
            return sorted(event_types)
        except Exception as e:
            logger.error(f"Error listing event types from MongoDB: {e}")
            return []

    def close(self):
        """Close MongoDB connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
            finally:
                self._client = None
                self._collection = None

    def __enter__(self):
        """Context manager entry."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
