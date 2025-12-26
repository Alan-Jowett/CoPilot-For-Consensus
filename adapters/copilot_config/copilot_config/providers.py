# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Additional configuration providers for schema-driven configuration."""

from typing import Any

from .base import ConfigProvider


class DocStoreConfigProvider(ConfigProvider):
    """Configuration provider that reads from a document store.

    This provider reads configuration values from a document store
    (MongoDB, etc.) and supports type conversion.
    """

    def __init__(self, doc_store, collection: str = "config"):
        """Initialize the document store config provider.

        Args:
            doc_store: DocumentStore instance
            collection: Collection name for configuration documents
        """
        self._doc_store = doc_store
        self._collection = collection
        self._cache: dict[str, Any] | None = None

    def is_connected(self) -> bool:
        """Check if the document store is connected.

        Returns:
            True if document store is available, False otherwise
        """
        try:
            # Try to ensure cache is loaded to verify connection
            self._ensure_cache()
            return self._cache is not None
        except (ConnectionError, OSError, TimeoutError, AttributeError, TypeError, KeyError):
            # Network/connection errors, or document store not available
            # AttributeError/TypeError can occur if document store is not properly initialized
            # KeyError can occur if documents have unexpected structure
            return False

    def query_documents_from_collection(self, collection_name: str, limit: int = 10000) -> list:
        """Query all documents from a collection.

        Args:
            collection_name: Name of the collection to query
            limit: Maximum number of documents to return

        Returns:
            List of documents from the collection
        """
        try:
            documents = self._doc_store.query_documents(
                collection=collection_name,
                filter_dict={},
                limit=limit
            )
            return documents if documents else []
        except (ConnectionError, OSError, TimeoutError, AttributeError, TypeError, KeyError):
            # Network/connection errors, or document store not available
            # AttributeError/TypeError can occur if document store is not properly initialized
            # KeyError can occur if required fields are missing
            return []

    def _ensure_cache(self) -> None:
        """Ensure configuration cache is loaded.

        Raises:
            ConnectionError, OSError, TimeoutError, AttributeError, TypeError, KeyError:
                If document store is unavailable or fails to load
        """
        if self._cache is not None:
            return

        # Try to load all config documents
        # Let exceptions propagate to caller (typically is_connected or get)
        docs = self._doc_store.query_documents(self._collection, {}, limit=1000)
        self._cache = {}
        for doc in docs:
            # Assume documents have a 'key' and 'value' field
            if 'key' in doc and 'value' in doc:
                self._cache[doc['key']] = doc['value']

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the document store.

        Supports dot notation for nested paths (e.g., "settings.database.host").

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key is not found

        Returns:
            Configuration value or default
        """
        try:
            self._ensure_cache()
        except (ConnectionError, OSError, TimeoutError, AttributeError, TypeError, KeyError):
            # If cache loading fails, return default
            return default

        # If cache is still None after _ensure_cache, return default
        if self._cache is None:
            return default

        # Try direct key lookup first
        if key in self._cache:
            return self._cache[key]

        # Try nested path lookup
        keys = key.split('.')
        value = self._cache

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value from the document store.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            Boolean value or default
        """
        value = self.get(key)
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ("true", "1", "yes", "on"):
                return True
            elif value_lower in ("false", "0", "no", "off"):
                return False

        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value from the document store.

        Args:
            key: Configuration key
            default: Default value if key is not found or cannot be converted

        Returns:
            Integer value or default
        """
        value = self.get(key)
        if value is None:
            return default

        if isinstance(value, int):
            return value

        try:
            return int(value)
        except (ValueError, TypeError):
            return default
