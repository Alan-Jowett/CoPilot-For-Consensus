# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for additional configuration providers."""

from copilot_config.providers import DocStoreConfigProvider


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

    def test_connection_error_returns_empty(self):
        """Test that ConnectionError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise ConnectionError("Connection refused")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []

    def test_os_error_returns_empty(self):
        """Test that OSError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise OSError("I/O error")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []

    def test_timeout_error_returns_empty(self):
        """Test that TimeoutError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise TimeoutError("Operation timed out")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []

    def test_attribute_error_returns_empty(self):
        """Test that AttributeError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise AttributeError("'NoneType' object has no attribute 'query'")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []

    def test_type_error_returns_empty(self):
        """Test that TypeError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise TypeError("expected str, got int")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []

    def test_key_error_returns_empty(self):
        """Test that KeyError during query returns empty result."""
        class FailingDocStore:
            def query_documents(self, collection, filter_dict, limit=100):
                raise KeyError("missing required key")

        provider = DocStoreConfigProvider(FailingDocStore())

        # is_connected should return False
        assert provider.is_connected() is False

        # query_documents_from_collection should return empty list
        assert provider.query_documents_from_collection("test_collection") == []
