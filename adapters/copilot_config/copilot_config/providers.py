# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Additional configuration providers for schema-driven configuration."""

import os
from typing import Any, Dict, Optional
from pathlib import Path

from .config import ConfigProvider


class YamlConfigProvider(ConfigProvider):
    """Configuration provider that reads from YAML files.
    
    This provider reads configuration from a YAML file and supports
    type conversion for common types (bool, int).
    """

    def __init__(self, filepath: str):
        """Initialize the YAML config provider.
        
        Args:
            filepath: Path to YAML configuration file
        """
        self._filepath = filepath
        self._config: Dict[str, Any] = {}
        self._load_yaml()

    def _load_yaml(self) -> None:
        """Load configuration from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML required for YAML configuration. "
                "Install with: pip install copilot-config[yaml]"
            )
        
        if not os.path.exists(self._filepath):
            self._config = {}
            return
        
        with open(self._filepath, "r") as f:
            self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the YAML file.
        
        Supports nested keys using dot notation (e.g., "database.host").
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value from the YAML file.
        
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
        """Get an integer configuration value from the YAML file.
        
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
        self._cache: Optional[Dict[str, Any]] = None

    def _ensure_cache(self) -> None:
        """Ensure configuration cache is loaded."""
        if self._cache is not None:
            return
        
        # Try to load all config documents
        try:
            docs = self._doc_store.query_documents(self._collection, {}, limit=1000)
            self._cache = {}
            for doc in docs:
                # Assume documents have a 'key' and 'value' field
                if 'key' in doc and 'value' in doc:
                    self._cache[doc['key']] = doc['value']
        except Exception:
            # If query fails, use empty cache
            self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the document store.
        
        Supports dot notation for nested paths (e.g., "settings.database.host").
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        self._ensure_cache()
        
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
