# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema provider backed by the document store abstraction.

This keeps persistence concerns inside copilot-storage and avoids direct
MongoDB coupling. Compatible with Mongo via the MongoDocumentStore backend,
but flexible for other implementations.
"""

from typing import Dict, Optional
import logging

from copilot_storage import create_document_store, DocumentStore

from .schema_provider import SchemaProvider

logger = logging.getLogger(__name__)


class DocumentStoreSchemaProvider(SchemaProvider):
    """Schema provider that loads schemas from a document store collection."""

    def __init__(
        self,
        mongo_uri: Optional[str] = None,
        store_uri: Optional[str] = None,
        database_name: str = "copilot",
        collection_name: str = "event_schemas",
        document_store: Optional[DocumentStore] = None,
        list_limit: int = 1000,
        **store_kwargs,
    ):
        """Initialize the provider.

        Args:
            mongo_uri: Optional MongoDB connection string; kept for backward
                compatibility. Use store_uri for generic naming.
            store_uri: Optional connection string; when provided, builds a
                Mongo-backed DocumentStore via create_document_store.
            database_name: Database name for Mongo-backed stores.
            collection_name: Collection that stores event schemas.
            document_store: Optional pre-built DocumentStore instance.
            **store_kwargs: Extra arguments forwarded to create_document_store.
        """
        self.mongo_uri = store_uri or mongo_uri
        self.database_name = database_name
        self.collection_name = collection_name
        self._schema_cache: Dict[str, Dict] = {}
        self._store = document_store
        self._owns_store = document_store is None
        self._store_kwargs = store_kwargs
        self._list_limit = list_limit

    def _ensure_store(self) -> Optional[DocumentStore]:
        if self._store is None:
            if not self.mongo_uri:
                logger.error(
                    "Either document_store must be provided or mongo_uri/store_uri must be specified to create a document store"
                )
                return None
            is_uri = isinstance(self.mongo_uri, str) and (
                self.mongo_uri.startswith("mongodb://")
                or self.mongo_uri.startswith("mongodb+srv://")
            )
            store_kwargs = dict(self._store_kwargs)
            if is_uri and "port" in store_kwargs:
                store_kwargs.pop("port")

            self._store = create_document_store(
                store_type="mongodb",
                host=self.mongo_uri,  # may be a URI string; Mongo client accepts this via host
                database=self.database_name,
                **store_kwargs,
            )
        return self._store

    def _ensure_connected(self) -> bool:
        store = self._ensure_store()
        if store is None:
            return False
        try:
            return store.connect()
        except Exception as exc:
            logger.error(f"Failed to connect document store: {exc}")
            return False

    def get_schema(self, event_type: str) -> Optional[Dict]:
        if event_type in self._schema_cache:
            return self._schema_cache[event_type]

        if not self._ensure_connected():
            logger.error("Cannot retrieve schema: document store not available")
            return None

        try:
            store = self._ensure_store()
            if store is None:
                return None
            docs = store.query_documents(self.collection_name, {"name": event_type}, limit=1)
            if not docs:
                logger.warning(f"Schema not found in document store for event type: {event_type}")
                return None

            doc = docs[0]
            schema = doc.get("schema")
            if schema is None:
                logger.error(f"Schema document for '{event_type}' is missing 'schema' field")
                return None

            self._schema_cache[event_type] = schema
            logger.debug(f"Loaded schema from document store for event type: {event_type}")
            return schema
        except Exception as exc:
            logger.error(f"Error retrieving schema from document store for '{event_type}': {exc}")
            return None

    def list_event_types(self) -> list[str]:
        if not self._ensure_connected():
            logger.error("Cannot list event types: document store not available")
            return []

        try:
            store = self._ensure_store()
            if store is None:
                return []
            docs = store.query_documents(self.collection_name, {}, limit=self._list_limit)
            event_types = [doc.get("name") for doc in docs if "name" in doc]
            if len(event_types) >= self._list_limit:
                logger.warning(
                    "Schema list may be truncated; increase list_limit if more than %s schemas exist",
                    self._list_limit,
                )
            return sorted(event_types)
        except Exception as exc:
            logger.error(f"Error listing event types from document store: {exc}")
            return []

    def close(self):
        if self._store and self._owns_store:
            try:
                self._store.disconnect()
            except Exception as exc:
                logger.error(f"Error closing document store: {exc}")

    def __enter__(self):
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
