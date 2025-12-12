# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for additional configuration providers."""

import os
import tempfile
from pathlib import Path

import pytest

from copilot_config.providers import YamlConfigProvider, DocStoreConfigProvider


class TestYamlConfigProvider:
    """Tests for YamlConfigProvider class."""

    def test_get_from_yaml_file(self, tmp_path):
        """Test getting configuration from YAML file."""
        # Create a YAML file
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
        database:
          host: localhost
          port: 5432
        app_name: test-app
        debug: true
        """)
        
        provider = YamlConfigProvider(str(yaml_file))
        
        assert provider.get("app_name") == "test-app"
        assert provider.get("database.host") == "localhost"
        assert provider.get("database.port") == 5432

    def test_get_missing_key_returns_default(self, tmp_path):
        """Test getting missing key returns default."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("app_name: test-app")
        
        provider = YamlConfigProvider(str(yaml_file))
        
        assert provider.get("missing_key", "default") == "default"

    def test_get_nested_missing_key_returns_default(self, tmp_path):
        """Test getting nested missing key returns default."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
        database:
          host: localhost
        """)
        
        provider = YamlConfigProvider(str(yaml_file))
        
        assert provider.get("database.missing", "default") == "default"

    def test_get_bool_from_yaml(self, tmp_path):
        """Test getting boolean values from YAML."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
        debug: true
        production: false
        enabled: "yes"
        disabled: "no"
        """)
        
        provider = YamlConfigProvider(str(yaml_file))
        
        assert provider.get_bool("debug") is True
        assert provider.get_bool("production") is False
        assert provider.get_bool("enabled") is True
        assert provider.get_bool("disabled") is False

    def test_get_int_from_yaml(self, tmp_path):
        """Test getting integer values from YAML."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
        port: 8080
        count: "42"
        """)
        
        provider = YamlConfigProvider(str(yaml_file))
        
        assert provider.get_int("port") == 8080
        assert provider.get_int("count") == 42

    def test_nonexistent_file_returns_defaults(self, tmp_path):
        """Test that nonexistent file returns defaults."""
        provider = YamlConfigProvider(str(tmp_path / "nonexistent.yaml"))
        
        assert provider.get("key", "default") == "default"
        assert provider.get_bool("bool_key", True) is True
        assert provider.get_int("int_key", 42) == 42


class MockDocumentStore:
    """Mock document store for testing."""
    
    def __init__(self, documents=None):
        self.documents = documents or []
    
    def query_documents(self, collection, filter_dict, limit=100):
        return self.documents


class TestDocStoreConfigProvider:
    """Tests for DocStoreConfigProvider class."""

    def test_get_from_document_store(self):
        """Test getting configuration from document store."""
        mock_store = MockDocumentStore([
            {"key": "app_name", "value": "test-app"},
            {"key": "port", "value": 8080},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get("app_name") == "test-app"
        assert provider.get("port") == 8080

    def test_get_missing_key_returns_default(self):
        """Test getting missing key returns default."""
        mock_store = MockDocumentStore([
            {"key": "app_name", "value": "test-app"},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get("missing_key", "default") == "default"

    def test_get_bool_from_document_store(self):
        """Test getting boolean values from document store."""
        mock_store = MockDocumentStore([
            {"key": "debug", "value": True},
            {"key": "production", "value": False},
            {"key": "enabled", "value": "yes"},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get_bool("debug") is True
        assert provider.get_bool("production") is False
        assert provider.get_bool("enabled") is True

    def test_get_int_from_document_store(self):
        """Test getting integer values from document store."""
        mock_store = MockDocumentStore([
            {"key": "port", "value": 8080},
            {"key": "count", "value": "42"},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get_int("port") == 8080
        assert provider.get_int("count") == 42

    def test_caching_behavior(self):
        """Test that provider caches documents."""
        mock_store = MockDocumentStore([
            {"key": "app_name", "value": "test-app"},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        # First access should query
        assert provider.get("app_name") == "test-app"
        
        # Modify the store
        mock_store.documents = [
            {"key": "app_name", "value": "modified-app"},
        ]
        
        # Second access should use cache
        assert provider.get("app_name") == "test-app"

    def test_nested_values_in_cache(self):
        """Test accessing nested values from cache."""
        mock_store = MockDocumentStore([
            {"key": "database", "value": {"host": "localhost", "port": 5432}},
        ])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get("database.host") == "localhost"
        assert provider.get("database.port") == 5432

    def test_empty_store_returns_defaults(self):
        """Test that empty store returns defaults."""
        mock_store = MockDocumentStore([])
        
        provider = DocStoreConfigProvider(mock_store)
        
        assert provider.get("key", "default") == "default"
        assert provider.get_bool("bool_key", True) is True
        assert provider.get_int("int_key", 42) == 42
