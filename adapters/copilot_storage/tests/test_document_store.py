# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for document stores."""

import pytest

from copilot_storage import (
    create_document_store,
    DocumentStore,
    MongoDocumentStore,
    InMemoryDocumentStore,
    DocumentStoreConnectionError,
    DocumentNotFoundError,
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

        store.connect()

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

        store.update_document("users", doc_id, {"age": 31})

        updated = store.get_document("users", doc_id)
        assert updated["age"] == 31
        assert updated["name"] == "Alice"  # Unchanged

    def test_update_nonexistent_document(self):
        """Test updating a non-existent document."""
        
        store = InMemoryDocumentStore()
        store.connect()

        with pytest.raises(DocumentNotFoundError):
            store.update_document("users", "nonexistent", {"age": 50})

    def test_delete_document(self):
        """Test deleting a document."""
        store = InMemoryDocumentStore()
        store.connect()

        doc_id = store.insert_document("users", {"name": "Alice"})

        store.delete_document("users", doc_id)

        assert store.get_document("users", doc_id) is None

    def test_delete_nonexistent_document(self):
        """Test deleting a non-existent document."""
        
        store = InMemoryDocumentStore()
        store.connect()

        with pytest.raises(DocumentNotFoundError):
            store.delete_document("users", "nonexistent")

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

    def test_nested_document_isolation(self):
        """Test that nested structures in documents are also isolated."""
        store = InMemoryDocumentStore()
        store.connect()

        # Insert document with nested structures
        doc_id = store.insert_document("users", {
            "name": "Alice",
            "metadata": {
                "tags": ["python", "developer"],
                "scores": {"skill": 85, "experience": 90}
            }
        })

        # Get document and modify nested structures
        retrieved = store.get_document("users", doc_id)
        retrieved["metadata"]["tags"].append("hacker")
        retrieved["metadata"]["scores"]["skill"] = 100

        # Get document again and verify nested structures weren't affected
        retrieved_again = store.get_document("users", doc_id)
        assert "hacker" not in retrieved_again["metadata"]["tags"]
        assert len(retrieved_again["metadata"]["tags"]) == 2
        assert retrieved_again["metadata"]["scores"]["skill"] == 85

    def test_deep_nested_document_isolation(self):
        """Ensure deeply nested dict/list structures are isolated from stored state."""
        store = InMemoryDocumentStore()
        store.connect()

        doc_id = store.insert_document("users", {
            "name": "Dana",
            "projects": [
                {
                    "title": "alpha",
                    "contributors": [
                        {"id": 1, "roles": ["dev", "reviewer"]},
                        {"id": 2, "roles": ["dev"]},
                    ],
                },
                {
                    "title": "beta",
                    "contributors": [
                        {"id": 3, "roles": ["pm"]}
                    ],
                },
            ],
        })

        # Mutate a deep copy returned from get_document
        retrieved = store.get_document("users", doc_id)
        retrieved["projects"][0]["contributors"][0]["roles"].append("admin")
        retrieved["projects"][1]["contributors"].append({"id": 4, "roles": ["qa"]})

        # Fetch again to ensure stored state was not affected
        retrieved_again = store.get_document("users", doc_id)
        assert retrieved_again["projects"][0]["contributors"][0]["roles"] == ["dev", "reviewer"]
        assert len(retrieved_again["projects"][1]["contributors"]) == 1
        assert retrieved_again["projects"][1]["contributors"][0]["roles"] == ["pm"]

    def test_aggregate_documents_simple_match(self):
        """Test aggregation with $match stage."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("messages", {"message_key": "msg1", "status": "pending"})
        store.insert_document("messages", {"message_key": "msg2", "status": "complete"})
        store.insert_document("messages", {"message_key": "msg3", "status": "pending"})

        pipeline = [
            {"$match": {"status": "pending"}}
        ]

        results = store.aggregate_documents("messages", pipeline)

        assert len(results) == 2
        assert all(doc["status"] == "pending" for doc in results)

    def test_aggregate_documents_match_exists(self):
        """Test aggregation with $match and $exists operator."""
        store = InMemoryDocumentStore()
        store.connect()

        store.insert_document("messages", {"message_key": "msg1", "archive_id": 1})
        store.insert_document("messages", {"message_key": "msg2"})
        store.insert_document("messages", {"message_key": "msg3", "archive_id": 2})

        pipeline = [
            {"$match": {"message_key": {"$exists": True}}}
        ]

        results = store.aggregate_documents("messages", pipeline)

        assert len(results) == 3

    def test_aggregate_documents_lookup(self):
        """Test aggregation with $lookup stage to join collections."""
        store = InMemoryDocumentStore()
        store.connect()

        # Insert messages
        store.insert_document("messages", {"message_key": "msg1", "text": "Hello"})
        store.insert_document("messages", {"message_key": "msg2", "text": "World"})

        # Insert chunks (some messages have chunks, some don't)
        store.insert_document("chunks", {"message_key": "msg1", "chunk_id": "chunk1"})
        store.insert_document("chunks", {"message_key": "msg1", "chunk_id": "chunk2"})

        # Lookup chunks for each message
        pipeline = [
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "message_key",
                    "foreignField": "message_key",
                    "as": "chunks"
                }
            }
        ]

        results = store.aggregate_documents("messages", pipeline)

        assert len(results) == 2
        # Find msg1 - should have 2 chunks
        msg1 = next(r for r in results if r["message_key"] == "msg1")
        assert len(msg1["chunks"]) == 2
        # Find msg2 - should have 0 chunks
        msg2 = next(r for r in results if r["message_key"] == "msg2")
        assert len(msg2["chunks"]) == 0

    def test_aggregate_documents_lookup_and_match(self):
        """Test aggregation with $lookup followed by $match to find messages without chunks."""
        store = InMemoryDocumentStore()
        store.connect()

        # Insert messages
        store.insert_document("messages", {"message_key": "msg1", "text": "Hello"})
        store.insert_document("messages", {"message_key": "msg2", "text": "World"})
        store.insert_document("messages", {"message_key": "msg3", "text": "Foo"})

        # Insert chunks (only for msg1)
        store.insert_document("chunks", {"message_key": "msg1", "chunk_id": "chunk1"})

        # Find messages without chunks
        pipeline = [
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "message_key",
                    "foreignField": "message_key",
                    "as": "chunks"
                }
            },
            {
                "$match": {
                    "chunks": {"$eq": []}
                }
            }
        ]

        results = store.aggregate_documents("messages", pipeline)

        # Should find msg2 and msg3 (no chunks)
        assert len(results) == 2
        message_keys = [r["message_key"] for r in results]
        assert "msg1" not in message_keys
        assert "msg2" in message_keys
        assert "msg3" in message_keys

    def test_aggregate_documents_with_limit(self):
        """Test aggregation with $limit stage."""
        store = InMemoryDocumentStore()
        store.connect()

        for i in range(10):
            store.insert_document("items", {"index": i, "type": "test"})

        pipeline = [
            {"$match": {"type": "test"}},
            {"$limit": 3}
        ]

        results = store.aggregate_documents("items", pipeline)

        assert len(results) == 3

    def test_aggregate_documents_complex_pipeline(self):
        """Test aggregation with a complex pipeline similar to chunking requeue."""
        store = InMemoryDocumentStore()
        store.connect()

        # Insert messages
        store.insert_document("messages", {"message_key": "msg1", "archive_id": 1})
        store.insert_document("messages", {"message_key": "msg2", "archive_id": 1})
        store.insert_document("messages", {"message_key": "msg3", "archive_id": 2})

        # Insert chunks (only for msg1)
        store.insert_document("chunks", {"message_key": "msg1", "chunk_id": "chunk1"})

        # Find messages without chunks (similar to chunking requeue logic)
        pipeline = [
            {
                "$match": {
                    "message_key": {"$exists": True},
                }
            },
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "message_key",
                    "foreignField": "message_key",
                    "as": "chunks",
                }
            },
            {
                "$match": {
                    "chunks": {"$eq": []},
                }
            },
            {
                "$limit": 1000,
            },
        ]

        results = store.aggregate_documents("messages", pipeline)

        # Should find msg2 and msg3
        assert len(results) == 2
        message_keys = [r["message_key"] for r in results]
        assert "msg1" not in message_keys
        assert "msg2" in message_keys
        assert "msg3" in message_keys

    def test_aggregate_documents_nonexistent_collection(self):
        """Test aggregation on a collection that doesn't exist."""
        store = InMemoryDocumentStore()
        store.connect()

        pipeline = [{"$match": {"status": "pending"}}]

        # Should return empty list, not raise an error
        results = store.aggregate_documents("nonexistent", pipeline)
        assert results == []

    def test_aggregate_documents_lookup_nonexistent_foreign_collection(self):
        """Test $lookup with a foreign collection that doesn't exist."""
        store = InMemoryDocumentStore()
        store.connect()

        # Insert messages but no chunks collection
        store.insert_document("messages", {"message_key": "msg1", "text": "Hello"})

        pipeline = [
            {
                "$lookup": {
                    "from": "nonexistent_chunks",
                    "localField": "message_key",
                    "foreignField": "message_key",
                    "as": "chunks"
                }
            }
        ]

        results = store.aggregate_documents("messages", pipeline)

        # Should return messages with empty chunks array
        assert len(results) == 1
        assert "chunks" in results[0]
        assert results[0]["chunks"] == []


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

    def test_connect_pymongo_not_installed(self, monkeypatch):
        """Test that connect() raises DocumentStoreConnectionError when pymongo is not installed."""
        store = MongoDocumentStore()
        
        # Mock the pymongo import to raise ImportError
        import builtins
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == "pymongo":
                raise ImportError("No module named 'pymongo'")
            return original_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(DocumentStoreConnectionError, match="pymongo not installed"):
            store.connect()

    def test_connect_connection_failure(self, monkeypatch):
        """Test that connect() raises DocumentStoreConnectionError on connection failure."""
        store = MongoDocumentStore(host="nonexistent.host.invalid", port=27017)
        
        # Mock pymongo to raise ConnectionFailure
        from unittest.mock import MagicMock, patch
        from pymongo.errors import ConnectionFailure
        
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ConnectionFailure("Connection refused")
        
        with patch("pymongo.MongoClient", return_value=mock_client):
            with pytest.raises(DocumentStoreConnectionError, match="Failed to connect to MongoDB"):
                store.connect()

    def test_connect_unexpected_error(self, monkeypatch):
        """Test that connect() raises DocumentStoreConnectionError on unexpected errors."""
        store = MongoDocumentStore()
        
        # Mock pymongo to raise an unexpected exception
        from unittest.mock import MagicMock, patch
        
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = RuntimeError("Unexpected error")
        
        with patch("pymongo.MongoClient", return_value=mock_client):
            with pytest.raises(DocumentStoreConnectionError, match="Unexpected error connecting to MongoDB"):
                store.connect()

    # Note: Actual connection and operation tests would require a running MongoDB instance
    # or mocking the pymongo library. These are integration tests better suited for
    # a separate test suite with docker-compose.
