# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for MongoDB document store against a real MongoDB instance."""

import os
import time

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Mongodb,
)
from copilot_storage import (
    DocumentNotFoundError,
    DocumentStoreNotConnectedError,
    create_document_store,
)
from copilot_storage.mongo_document_store import MongoDocumentStore
from copilot_storage.validating_document_store import ValidatingDocumentStore


def get_mongodb_config():
    """Get MongoDB configuration from environment variables."""
    return AdapterConfig_DocumentStore(
        doc_store_type="mongodb",
        driver=DriverConfig_DocumentStore_Mongodb(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", "27017")),
            username=os.getenv("MONGODB_USERNAME", "testuser"),
            password=os.getenv("MONGODB_PASSWORD", "testpass"),
            database=os.getenv("MONGODB_DATABASE", "test_copilot"),
        ),
    )


def get_underlying_database(store):
    """Get the underlying MongoDB database from a document store.

    This is used for test cleanup only. In production, tests should not
    access driver-specific implementation details.
    """
    if hasattr(store, 'database'):
        return store.database
    if hasattr(store, '_store') and hasattr(store._store, 'database'):
        return store._store.database
    return None


@pytest.fixture(scope="module")
def mongodb_store():
    """Create and connect to a real MongoDB instance for integration tests."""
    config = get_mongodb_config()
    # Disable validation for integration tests - we're testing the raw MongoDB store
    store = create_document_store(config, enable_validation=False)
    assert isinstance(store, MongoDocumentStore)

    # Attempt to connect with retries
    max_retries = 5
    for i in range(max_retries):
        try:
            store.connect()
            break
        except Exception:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                pytest.skip("Could not connect to MongoDB - skipping integration tests")

    yield store

    # Cleanup
    store.disconnect()


@pytest.fixture
def clean_collection(mongodb_store):
    """Ensure a clean collection for each test."""
    collection_name = "test_integration"

    # Clean up before test (access underlying MongoDB store)
    db = get_underlying_database(mongodb_store)
    if db is not None:
        db[collection_name].drop()

    yield collection_name

    # Clean up after test (access underlying MongoDB store)
    db = get_underlying_database(mongodb_store)
    if db is not None:
        db[collection_name].drop()


@pytest.mark.integration
class TestMongoDBIntegration:
    """Integration tests for MongoDB document store."""

    def test_connection(self, mongodb_store):
        """Test that we can connect to MongoDB."""
        # mongodb_store is now a raw MongoDocumentStore (not wrapped)
        assert mongodb_store.client is not None
        assert mongodb_store.database is not None

    def test_insert_and_get_document(self, mongodb_store, clean_collection):
        """Test inserting and retrieving a document."""
        doc = {
            "name": "Integration Test User",
            "email": "integration@test.com",
            "age": 30,
        }

        doc_id = mongodb_store.insert_document(clean_collection, doc)
        assert doc_id is not None

        retrieved = mongodb_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert retrieved["name"] == "Integration Test User"
        assert retrieved["email"] == "integration@test.com"
        assert retrieved["age"] == 30

    def test_insert_multiple_documents(self, mongodb_store, clean_collection):
        """Test inserting multiple documents."""
        docs = [
            {"name": "User 1", "age": 25},
            {"name": "User 2", "age": 30},
            {"name": "User 3", "age": 35},
        ]

        doc_ids = []
        for doc in docs:
            doc_id = mongodb_store.insert_document(clean_collection, doc)
            doc_ids.append(doc_id)

        assert len(doc_ids) == 3

        # Verify all documents can be retrieved
        for doc_id in doc_ids:
            retrieved = mongodb_store.get_document(clean_collection, doc_id)
            assert retrieved is not None

    def test_query_documents(self, mongodb_store, clean_collection):
        """Test querying documents with filters."""
        # Insert test documents
        mongodb_store.insert_document(clean_collection, {"name": "Alice", "age": 30, "city": "NYC"})
        mongodb_store.insert_document(clean_collection, {"name": "Bob", "age": 25, "city": "LA"})
        mongodb_store.insert_document(clean_collection, {"name": "Charlie", "age": 30, "city": "NYC"})

        # Query by age
        results = mongodb_store.query_documents(clean_collection, {"age": 30})
        assert len(results) == 2
        assert all(doc["age"] == 30 for doc in results)

        # Query by city
        results = mongodb_store.query_documents(clean_collection, {"city": "NYC"})
        assert len(results) == 2
        assert all(doc["city"] == "NYC" for doc in results)

        # Query with multiple filters
        results = mongodb_store.query_documents(clean_collection, {"age": 30, "city": "NYC"})
        assert len(results) == 2

    def test_query_documents_with_limit(self, mongodb_store, clean_collection):
        """Test querying documents with a limit."""
        # Insert multiple documents
        for i in range(10):
            mongodb_store.insert_document(clean_collection, {"index": i, "type": "test"})

        # Query with limit
        results = mongodb_store.query_documents(clean_collection, {"type": "test"}, limit=5)
        assert len(results) == 5

    def test_update_document(self, mongodb_store, clean_collection):
        """Test updating a document."""
        # Insert a document
        doc_id = mongodb_store.insert_document(
            clean_collection, {"name": "Update Test", "age": 25, "city": "NYC"}
        )

        # Update the document
        mongodb_store.update_document(
            clean_collection, doc_id, {"age": 26, "city": "LA"}
        )

        # Verify the update
        updated = mongodb_store.get_document(clean_collection, doc_id)
        assert updated["age"] == 26
        assert updated["city"] == "LA"
        assert updated["name"] == "Update Test"  # Unchanged field

    def test_update_nonexistent_document(self, mongodb_store, clean_collection):
        """Test updating a document that doesn't exist."""

        with pytest.raises(DocumentNotFoundError):
            mongodb_store.update_document(
                clean_collection, "nonexistent_id", {"age": 50}
            )

    def test_delete_document(self, mongodb_store, clean_collection):
        """Test deleting a document."""
        # Insert a document
        doc_id = mongodb_store.insert_document(
            clean_collection, {"name": "Delete Test", "age": 30}
        )

        # Verify it exists
        doc = mongodb_store.get_document(clean_collection, doc_id)
        assert doc is not None

        # Delete the document
        mongodb_store.delete_document(clean_collection, doc_id)

        # Verify it's gone
        doc = mongodb_store.get_document(clean_collection, doc_id)
        assert doc is None

    def test_delete_nonexistent_document(self, mongodb_store, clean_collection):
        """Test deleting a document that doesn't exist."""

        with pytest.raises(DocumentNotFoundError):
            mongodb_store.delete_document(clean_collection, "nonexistent_id")

    def test_complex_document(self, mongodb_store, clean_collection):
        """Test storing and retrieving a complex document with nested structures."""
        complex_doc = {
            "user": {
                "name": "Complex User",
                "email": "complex@test.com",
                "profile": {
                    "bio": "Test bio",
                    "interests": ["coding", "testing", "mongodb"],
                },
            },
            "metadata": {
                "created": "2025-01-01",
                "tags": ["test", "integration"],
            },
            "stats": {
                "login_count": 5,
                "last_login": "2025-01-10",
            },
        }

        doc_id = mongodb_store.insert_document(clean_collection, complex_doc)
        assert doc_id is not None

        retrieved = mongodb_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert retrieved["user"]["name"] == "Complex User"
        assert "coding" in retrieved["user"]["profile"]["interests"]
        assert retrieved["stats"]["login_count"] == 5

    def test_concurrent_operations(self, mongodb_store, clean_collection):
        """Test multiple concurrent operations."""
        # Insert multiple documents
        doc_ids = []
        for i in range(5):
            doc_id = mongodb_store.insert_document(
                clean_collection, {"index": i, "name": f"User {i}"}
            )
            doc_ids.append(doc_id)

        # Update some documents
        for i in [0, 2, 4]:
            mongodb_store.update_document(
                clean_collection, doc_ids[i], {"updated": True}
            )

        # Query and verify
        results = mongodb_store.query_documents(clean_collection, {"updated": True})
        assert len(results) == 3

        # Delete some documents
        for i in [1, 3]:
            mongodb_store.delete_document(clean_collection, doc_ids[i])

        # Verify remaining documents
        all_docs = mongodb_store.query_documents(clean_collection, {})
        assert len(all_docs) == 3

    def test_empty_query(self, mongodb_store, clean_collection):
        """Test querying an empty collection."""
        results = mongodb_store.query_documents(clean_collection, {})
        assert len(results) == 0

    def test_document_with_special_characters(self, mongodb_store, clean_collection):
        """Test documents with special characters."""
        doc = {
            "name": "User with 特殊字符 and émojis 🎉",
            "email": "test@example.com",
            "description": "Line 1\nLine 2\tTabbed",
        }

        doc_id = mongodb_store.insert_document(clean_collection, doc)
        retrieved = mongodb_store.get_document(clean_collection, doc_id)

        assert retrieved["name"] == doc["name"]
        assert retrieved["description"] == doc["description"]

    def test_large_document(self, mongodb_store, clean_collection):
        """Test storing and retrieving a large document."""
        # Create a document with a large array
        large_doc = {
            "name": "Large Document",
            "data": [{"index": i, "value": f"value_{i}"} for i in range(1000)],
        }

        doc_id = mongodb_store.insert_document(clean_collection, large_doc)
        retrieved = mongodb_store.get_document(clean_collection, doc_id)

        assert len(retrieved["data"]) == 1000
        assert retrieved["data"][0]["index"] == 0
        assert retrieved["data"][999]["index"] == 999


@pytest.mark.integration
class TestMongoDBEdgeCases:
    """Test edge cases and error handling."""

    def test_insert_without_connection(self):
        """Test that operations fail gracefully without connection."""
        config = load_driver_config(
            service=None,
            adapter="document_store",
            driver="mongodb",
            fields={
                "host": "nonexistent_host",
                "port": 27017,
                "database": "test_db",
            },
        )
        store = MongoDocumentStore.from_config(config)
        # Don't connect

        with pytest.raises(DocumentStoreNotConnectedError) as excinfo:
            store.insert_document("test", {"name": "test"})
        assert str(excinfo.value) == "Not connected to MongoDB"

    def test_invalid_document_id(self, mongodb_store, clean_collection):
        """Test getting a document with an invalid ID format."""
        # MongoDB should handle invalid ObjectId gracefully
        result = mongodb_store.get_document(clean_collection, "invalid_id_format")
        assert result is None

    def test_empty_document(self, mongodb_store, clean_collection):
        """Test inserting an empty document."""
        doc_id = mongodb_store.insert_document(clean_collection, {})
        assert doc_id is not None

        retrieved = mongodb_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert "_id" in retrieved


@pytest.mark.integration
class TestValidationAtAdapterLayer:
    """Test that validation is handled at the adapter layer, not MongoDB."""

    def test_mongodb_has_no_collection_validators(self, mongodb_store, clean_collection):
        """Verify that MongoDB collections do not have validators.

        This test ensures that schema validation is handled at the application
        layer (via ValidatingDocumentStore) and not at the MongoDB level.
        Any document should be accepted by the raw MongoDB store, regardless
        of schema compliance.
        """
        # Insert a test document to ensure collection exists
        mongodb_store.insert_document(clean_collection, {"test": "data"})

        # Get the collection info (access underlying MongoDB database)
        db = get_underlying_database(mongodb_store)
        if db is None:
            pytest.skip("Could not access underlying MongoDB database")

        collection_infos = list(db.list_collections(
            filter={"name": clean_collection}
        ))

        # If collection exists, check it has no validator
        if collection_infos:
            collection_info = collection_infos[0]
            # Verify no validator is present
            assert "options" not in collection_info or "validator" not in collection_info.get("options", {}), \
                "MongoDB collection should NOT have a validator - validation should be at adapter layer"

    def test_invalid_document_accepted_by_raw_store(self, mongodb_store, clean_collection):
        """Verify that invalid documents are accepted by the raw MongoDB store.

        This proves that validation is NOT happening at the MongoDB level.
        The raw store should accept any document structure.
        """
        # Insert a document that would fail most schemas
        # (missing fields, wrong types, etc.)
        invalid_doc = {
            "completely": "invalid",
            "random": 12345,
            "nested": {"structure": True},
            "array": [1, "two", 3.0, None],
        }

        # This should succeed because there's no MongoDB-level validation
        doc_id = mongodb_store.insert_document(clean_collection, invalid_doc)
        assert doc_id is not None

        # Verify we can retrieve it
        retrieved = mongodb_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert retrieved["completely"] == "invalid"
        assert retrieved["random"] == 12345


@pytest.mark.integration
class TestMongoDBAggregate:
    """Integration tests for MongoDB aggregation functionality."""

    def test_aggregate_simple_match(self, mongodb_store, clean_collection):
        """Test aggregation with a simple $match stage."""
        # Insert test documents
        mongodb_store.insert_document(clean_collection, {"status": "pending", "value": 10})
        mongodb_store.insert_document(clean_collection, {"status": "complete", "value": 20})
        mongodb_store.insert_document(clean_collection, {"status": "pending", "value": 30})

        # Aggregate with $match
        pipeline = [
            {"$match": {"status": "pending"}}
        ]

        results = mongodb_store.aggregate_documents(clean_collection, pipeline)

        assert len(results) == 2
        assert all(doc["status"] == "pending" for doc in results)

    def test_aggregate_lookup(self, mongodb_store):
        """Test aggregation with $lookup to join collections."""
        messages_col = "test_messages"
        chunks_col = "test_chunks"

        try:
            # Clean up collections
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[chunks_col].drop()

            # Insert messages
            mongodb_store.insert_document(messages_col, {"message_key": "msg1", "text": "Hello"})
            mongodb_store.insert_document(messages_col, {"message_key": "msg2", "text": "World"})

            # Insert chunks (only for msg1)
            mongodb_store.insert_document(chunks_col, {"message_key": "msg1", "chunk_id": "chunk1"})
            mongodb_store.insert_document(chunks_col, {"message_key": "msg1", "chunk_id": "chunk2"})

            # Aggregate with $lookup
            pipeline = [
                {
                    "$lookup": {
                        "from": chunks_col,
                        "localField": "message_key",
                        "foreignField": "message_key",
                        "as": "chunks"
                    }
                }
            ]

            results = mongodb_store.aggregate_documents(messages_col, pipeline)

            assert len(results) == 2

            # Find msg1 - should have 2 chunks
            msg1 = next(r for r in results if r["message_key"] == "msg1")
            assert len(msg1["chunks"]) == 2

            # Find msg2 - should have 0 chunks
            msg2 = next(r for r in results if r["message_key"] == "msg2")
            assert len(msg2["chunks"]) == 0

        finally:
            # Clean up
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[chunks_col].drop()

    def test_aggregate_complex_pipeline(self, mongodb_store):
        """Test aggregation with complex pipeline similar to chunking requeue."""
        messages_col = "test_messages_complex"
        chunks_col = "test_chunks_complex"

        try:
            # Clean up collections
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[chunks_col].drop()

            # Insert messages
            mongodb_store.insert_document(messages_col, {"message_key": "msg1", "archive_id": 1})
            mongodb_store.insert_document(messages_col, {"message_key": "msg2", "archive_id": 1})
            mongodb_store.insert_document(messages_col, {"message_key": "msg3", "archive_id": 2})

            # Insert chunks (only for msg1)
            mongodb_store.insert_document(chunks_col, {"message_key": "msg1", "chunk_id": "chunk1"})

            # Find messages without chunks (chunking requeue logic)
            pipeline = [
                {
                    "$match": {
                        "message_key": {"$exists": True},
                    }
                },
                {
                    "$lookup": {
                        "from": chunks_col,
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

            results = mongodb_store.aggregate_documents(messages_col, pipeline)

            # Should find msg2 and msg3 (no chunks)
            assert len(results) == 2
            message_keys = [r["message_key"] for r in results]
            assert "msg1" not in message_keys
            assert "msg2" in message_keys
            assert "msg3" in message_keys

        finally:
            # Clean up
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[chunks_col].drop()

    def test_aggregate_objectid_serialization(self, mongodb_store):
        """Test that ObjectIds are properly serialized to strings in aggregation results."""
        messages_col = "test_messages_objectid"
        refs_col = "test_refs_objectid"

        try:
            # Clean up collections
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[refs_col].drop()

            # Insert messages and references
            mongodb_store.insert_document(messages_col, {"message_key": "msg1", "text": "Test"})
            mongodb_store.insert_document(refs_col, {"message_key": "msg1", "ref_id": "ref1"})

            # Aggregate with $lookup to bring in referenced documents
            pipeline = [
                {
                    "$lookup": {
                        "from": refs_col,
                        "localField": "message_key",
                        "foreignField": "message_key",
                        "as": "refs"
                    }
                }
            ]

            results = mongodb_store.aggregate_documents(messages_col, pipeline)

            assert len(results) == 1
            result = results[0]

            # Verify ObjectIds are serialized to strings at all levels
            assert isinstance(result["_id"], str)
            assert len(result["refs"]) == 1
            assert isinstance(result["refs"][0]["_id"], str)

            # Verify they can be JSON serialized
            import json
            json_str = json.dumps(result)
            assert json_str is not None

        finally:
            # Clean up
            db = get_underlying_database(mongodb_store)
            if db is not None:
                db[messages_col].drop()
                db[refs_col].drop()

    def test_aggregate_empty_collection(self, mongodb_store, clean_collection):
        """Test aggregation on an empty collection."""
        pipeline = [{"$match": {"status": "pending"}}]

        results = mongodb_store.aggregate_documents(clean_collection, pipeline)

        assert results == []

    def test_aggregate_with_limit(self, mongodb_store, clean_collection):
        """Test aggregation with $limit stage."""
        # Insert multiple documents
        for i in range(10):
            mongodb_store.insert_document(clean_collection, {"index": i, "type": "test"})

        pipeline = [
            {"$match": {"type": "test"}},
            {"$limit": 3}
        ]

        results = mongodb_store.aggregate_documents(clean_collection, pipeline)

        assert len(results) == 3
