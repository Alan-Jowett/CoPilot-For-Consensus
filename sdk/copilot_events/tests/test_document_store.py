# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for document stores."""

import pytest

from copilot_events import (
    create_document_store,
    DocumentStore,
    MongoDocumentStore,
    InMemoryDocumentStore,
)


class TestDocumentStoreFactory:
    """Tests for create_document_store factory function."""

    def test_create_inmemory_store(self):
        """Test creating an in-memory document store."""
        store = create_document_store(store_type="inmemory")

        assert isinstance(store, InMemoryDocumentStore)
        assert isinstance(store, DocumentStore)

    def test_create_mongodb_store(self):
        """Test creating a MongoDB document store."""
        store = create_document_store(
            store_type="mongodb",
            host="localhost",
            port=27017,
            database="test_db"
        )

        assert isinstance(store, MongoDocumentStore)
        assert isinstance(store, DocumentStore)
        assert store.host == "localhost"
        assert store.port == 27017
        assert store.database_name == "test_db"

    def test_create_unknown_store_type(self):
        """Test that unknown store type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown store_type"):
            create_document_store(store_type="invalid")


class TestInMemoryDocumentStore:
    """Tests for InMemoryDocumentStore."""

    def test_connect(self):
        """Test connecting to in-memory store."""
        store = InMemoryDocumentStore()

        result = store.connect()

        assert result is True
        assert store.connected is True

    def test_disconnect(self):
        """Test disconnecting from in-memory store."""
        store = InMemoryDocumentStore()
        store.connect()

        store.disconnect()

        assert store.connected is False

    def test_insert_document(self):
        """Test inserting a document."""
        store = InMemoryDocumentStore()
        store.connect()

        doc = {"name": "Alice", "age": 30}
        doc_id = store.insert_document("users", doc)

        assert doc_id is not None
        assert isinstance(doc_id, str)

    def test_insert_document_with_id(self):
        """Test inserting a document with a pre-defined ID."""
        store = InMemoryDocumentStore()
        store.connect()

        doc = {"_id": "user-123", "name": "Bob", "age": 25}
        doc_id = store.insert_document("users", doc)

        assert doc_id == "user-123"

    def test_get_document(self):
        """Test retrieving a document by ID."""
        store = InMemoryDocumentStore()
        store.connect()

        doc = {"_id": "user-456", "name": "Charlie", "age": 35}
        store.insert_document("users", doc)

        retrieved = store.get_document("users", "user-456")

        assert retrieved is not None
        assert retrieved["name"] == "Charlie"
        assert retrieved["age"] == 35

    def test_get_nonexistent_document(self):
        """Test retrieving a non-existent document."""
        store = InMemoryDocumentStore()
        store.connect()

        retrieved = store.get_document("users", "nonexistent")

        assert retrieved is None

    def test_query_documents(self):
        """Test querying documents."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("users", {"name": "Alice", "age": 30, "city": "NYC"})
        store.insert_document("users", {"name": "Bob", "age": 25, "city": "LA"})
        store.insert_document("users", {"name": "Charlie", "age": 30, "city": "NYC"})

        results = store.query_documents("users", {"age": 30})

        assert len(results) == 2
        assert all(doc["age"] == 30 for doc in results)

    def test_query_documents_multiple_filters(self):
        """Test querying documents with multiple filters."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("users", {"name": "Alice", "age": 30, "city": "NYC"})
        store.insert_document("users", {"name": "Bob", "age": 25, "city": "LA"})
        store.insert_document("users", {"name": "Charlie", "age": 30, "city": "LA"})

        results = store.query_documents("users", {"age": 30, "city": "NYC"})

        assert len(results) == 1
        assert results[0]["name"] == "Alice"

    def test_query_documents_with_limit(self):
        """Test querying documents with limit."""
        store = InMemoryDocumentStore()
        store.connect()

        for i in range(10):
            store.insert_document("items", {"index": i, "type": "test"})

        results = store.query_documents("items", {"type": "test"}, limit=5)

        assert len(results) == 5

    def test_update_document(self):
        """Test updating a document."""
        store = InMemoryDocumentStore()
        store.connect()

        doc_id = store.insert_document("users", {"name": "Alice", "age": 30})

        result = store.update_document("users", doc_id, {"age": 31})

        assert result is True
        updated = store.get_document("users", doc_id)
        assert updated["age"] == 31
        assert updated["name"] == "Alice"  # Unchanged

    def test_update_nonexistent_document(self):
        """Test updating a non-existent document."""
        store = InMemoryDocumentStore()
        store.connect()

        result = store.update_document("users", "nonexistent", {"age": 50})

        assert result is False

    def test_delete_document(self):
        """Test deleting a document."""
        store = InMemoryDocumentStore()
        store.connect()

        doc_id = store.insert_document("users", {"name": "Alice"})

        result = store.delete_document("users", doc_id)

        assert result is True
        assert store.get_document("users", doc_id) is None

    def test_delete_nonexistent_document(self):
        """Test deleting a non-existent document."""
        store = InMemoryDocumentStore()
        store.connect()

        result = store.delete_document("users", "nonexistent")

        assert result is False

    def test_clear_collection(self):
        """Test clearing a collection."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("users", {"name": "Alice"})
        store.insert_document("users", {"name": "Bob"})

        store.clear_collection("users")

        results = store.query_documents("users", {})
        assert len(results) == 0

    def test_clear_all(self):
        """Test clearing all collections."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("users", {"name": "Alice"})
        store.insert_document("products", {"name": "Widget"})

        store.clear_all()

        assert len(store.query_documents("users", {})) == 0
        assert len(store.query_documents("products", {})) == 0

    def test_multiple_collections(self):
        """Test working with multiple collections."""
        store = InMemoryDocumentStore()
        store.connect()

        user_id = store.insert_document("users", {"name": "Alice"})
        product_id = store.insert_document("products", {"name": "Widget"})

        assert store.get_document("users", user_id) is not None
        assert store.get_document("products", product_id) is not None
        assert store.get_document("users", product_id) is None  # Wrong collection

    def test_document_isolation(self):
        """Test that returned documents are isolated from internal storage."""
        store = InMemoryDocumentStore()
        store.connect()

        doc_id = store.insert_document("users", {"name": "Alice", "age": 30})

        # Get document and modify it
        retrieved = store.get_document("users", doc_id)
        retrieved["age"] = 99

        # Get document again and verify it wasn't affected
        retrieved_again = store.get_document("users", doc_id)
        assert retrieved_again["age"] == 30


class TestMongoDocumentStore:
    """Tests for MongoDocumentStore."""

    def test_initialization(self):
        """Test MongoDB store initialization."""
        store = MongoDocumentStore(
            host="testhost",
            port=27018,
            username="testuser",
            password="testpass",
            database="testdb"
        )

        assert store.host == "testhost"
        assert store.port == 27018
        assert store.username == "testuser"
        assert store.password == "testpass"
        assert store.database_name == "testdb"

    def test_default_values(self):
        """Test default initialization values."""
        store = MongoDocumentStore()

        assert store.host == "localhost"
        assert store.port == 27017
        assert store.username is None
        assert store.password is None
        assert store.database_name == "copilot"

    # Note: Actual connection and operation tests would require a running MongoDB instance
    # or mocking the pymongo library. These are integration tests better suited for
    # a separate test suite with docker-compose.
