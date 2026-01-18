# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for validating document store."""

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_storage import DocumentNotFoundError, create_document_store
from copilot_storage.validating_document_store import DocumentValidationError, ValidatingDocumentStore

# Check if copilot_schema_validation is available
try:
    import copilot_schema_validation  # noqa: F401

    HAS_SCHEMA_VALIDATION = True
except ImportError:
    HAS_SCHEMA_VALIDATION = False

# Skip marker for tests that require schema validation
requires_schema_validation = pytest.mark.skipif(
    not HAS_SCHEMA_VALIDATION,
    reason="copilot_schema_validation not installed (install with: pip install copilot-storage[validation])",
)


class MockSchemaProvider:
    """Mock schema provider for testing."""

    def __init__(self, schemas=None):
        """Initialize with optional schemas dictionary."""
        self.schemas = schemas or {}

    def get_schema(self, schema_name: str):
        """Return schema for schema name or None if not found."""
        return self.schemas.get(schema_name)


def _create_base_inmemory_store():
    """Create an unwrapped, in-memory document store for tests."""
    config = AdapterConfig_DocumentStore(
        doc_store_type="inmemory",
        driver=DriverConfig_DocumentStore_Inmemory(),
    )
    return create_document_store(config, enable_validation=False)


class TestValidatingDocumentStore:
    """Tests for ValidatingDocumentStore."""

    def test_init(self):
        """Test initializing a validating document store."""
        base = _create_base_inmemory_store()
        provider = MockSchemaProvider()

        store = ValidatingDocumentStore(store=base, schema_provider=provider, strict=True, validate_reads=False)

        assert store._store is base
        assert store._schema_provider is provider
        assert store._strict is True
        assert store._validate_reads is False

    def test_collection_to_schema_name(self):
        """Test conversion of collection names to schema names."""
        base = _create_base_inmemory_store()
        store = ValidatingDocumentStore(base)

        # Schema names match collection names (lowercase)
        assert store._collection_to_schema_name("archives") == "archives"
        assert store._collection_to_schema_name("messages") == "messages"
        assert store._collection_to_schema_name("chunks") == "chunks"
        assert store._collection_to_schema_name("summaries") == "summaries"

    def test_update_document_falls_back_to_query_by__id_when_missing(self):
        """If get_document misses, allow update via query({_id: doc_id}).

        This models Cosmos DB behavior where the native document id ("id") can
        differ from the application-level canonical key (often stored in "_id").
        """

        class FakeStore:
            def __init__(self):
                self.updated: list[tuple[str, str, dict]] = []

            def connect(self):
                return None

            def disconnect(self):
                return None

            def insert_document(self, collection: str, doc: dict):
                raise NotImplementedError

            def get_document(self, collection: str, doc_id: str):
                # Simulate "miss" when asked by canonical id
                return None

            def query_documents(self, collection: str, filter_dict: dict, limit: int = 100):
                if collection == "archives" and filter_dict == {"_id": "9b548dcbf26aec88"}:
                    return [{"id": "cosmos-generated-id", "_id": "9b548dcbf26aec88", "status": "pending"}]
                return []

            def update_document(self, collection: str, doc_id: str, patch: dict):
                self.updated.append((collection, doc_id, patch))

            def delete_document(self, collection: str, doc_id: str):
                raise NotImplementedError

        base = FakeStore()
        store = ValidatingDocumentStore(store=base, schema_provider=None, strict=True)

        store.update_document(
            "archives",
            "9b548dcbf26aec88",
            {"status": "completed"},
        )

        assert base.updated == [("archives", "cosmos-generated-id", {"status": "completed"})]

    @requires_schema_validation
    def test_insert_valid_document_strict_mode(self):
        """Test inserting a valid document in strict mode."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {
            "type": "object",
            "properties": {"archive_id": {"type": "string"}, "status": {"type": "string"}},
            "required": ["archive_id", "status"],
        }

        provider = MockSchemaProvider({"archives": schema})
        store = ValidatingDocumentStore(base, provider, strict=True)

        doc = {"archive_id": "abc", "status": "success"}
        doc_id = store.insert_document("archives", doc)

        assert doc_id is not None
        assert len(doc_id) > 0

    @requires_schema_validation
    def test_insert_invalid_document_strict_mode(self):
        """Test inserting an invalid document in strict mode raises DocumentValidationError."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {
            "type": "object",
            "properties": {"archive_id": {"type": "string"}, "status": {"type": "string"}},
            "required": ["archive_id", "status"],
        }

        provider = MockSchemaProvider({"archives": schema})
        store = ValidatingDocumentStore(base, provider, strict=True)

        # Missing required status field
        doc = {"archive_id": "abc"}

        with pytest.raises(DocumentValidationError) as exc_info:
            store.insert_document("archives", doc)

        assert exc_info.value.collection == "archives"
        assert len(exc_info.value.errors) > 0
        assert any("status" in err for err in exc_info.value.errors)

    def test_insert_invalid_document_non_strict_mode(self):
        """Test inserting an invalid document in non-strict mode succeeds with warning."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {
            "type": "object",
            "properties": {"archive_id": {"type": "string"}, "status": {"type": "string"}},
            "required": ["archive_id", "status"],
        }

        provider = MockSchemaProvider({"archives": schema})
        store = ValidatingDocumentStore(base, provider, strict=False)

        # Missing required status field
        doc = {"archive_id": "abc"}

        # Should succeed despite validation failure
        doc_id = store.insert_document("archives", doc)
        assert doc_id is not None

    def test_insert_without_schema_provider(self):
        """Test inserting without schema provider skips validation."""
        base = _create_base_inmemory_store()
        base.connect()

        store = ValidatingDocumentStore(base, schema_provider=None, strict=True)

        # Even invalid document should pass without schema provider
        doc = {"anything": "goes"}

        doc_id = store.insert_document("test_collection", doc)
        assert doc_id is not None

    def test_insert_schema_not_found_strict_mode(self):
        """Test inserting document with no schema in strict mode fails."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider({})  # Empty schemas
        store = ValidatingDocumentStore(base, provider, strict=True)

        doc = {"data": "test"}

        with pytest.raises(DocumentValidationError) as exc_info:
            store.insert_document("unknown_collection", doc)

        assert "unknown_collection" in str(exc_info.value)

    def test_insert_schema_not_found_non_strict_mode(self):
        """Test inserting document with no schema in non-strict mode succeeds."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider({})  # Empty schemas
        store = ValidatingDocumentStore(base, provider, strict=False)

        doc = {"data": "test"}

        # Should succeed in non-strict mode
        doc_id = store.insert_document("unknown_collection", doc)
        assert doc_id is not None

    def test_get_document_without_validation(self):
        """Test getting a document without read validation."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider, validate_reads=False)

        # Insert document directly to base store
        doc = {"data": "test"}
        doc_id = base.insert_document("test_collection", doc)

        # Retrieve through validating store (no validation)
        retrieved = store.get_document("test_collection", doc_id)
        assert retrieved is not None
        assert retrieved["data"] == "test"

    @requires_schema_validation
    def test_get_document_with_validation_valid(self):
        """Test getting a valid document with read validation."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}

        provider = MockSchemaProvider({"test_collection": schema})
        store = ValidatingDocumentStore(base, provider, validate_reads=True, strict=True)

        # Insert valid document
        doc = {"data": "test"}
        doc_id = base.insert_document("test_collection", doc)

        # Retrieve with validation
        retrieved = store.get_document("test_collection", doc_id)
        assert retrieved is not None
        assert retrieved["data"] == "test"

    def test_get_document_with_validation_invalid_strict(self):
        """Test getting an invalid document with read validation in strict mode fails."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}

        provider = MockSchemaProvider({"test_collection": schema})
        store = ValidatingDocumentStore(base, provider, validate_reads=True, strict=True)

        # Insert invalid document directly to base store
        doc = {"wrong_field": "test"}
        doc_id = base.insert_document("test_collection", doc)

        # Retrieve with validation should fail
        with pytest.raises(DocumentValidationError):
            store.get_document("test_collection", doc_id)

    def test_get_document_not_found(self):
        """Test getting a non-existent document returns None."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        retrieved = store.get_document("test_collection", "nonexistent")
        assert retrieved is None

    @requires_schema_validation
    def test_update_valid_document_strict_mode(self):
        """Test updating with a valid patch in strict mode."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {"type": "object", "properties": {"status": {"type": "string"}}}

        provider = MockSchemaProvider({"test_collection": schema})
        store = ValidatingDocumentStore(base, provider, strict=True)

        # Insert document
        doc_id = base.insert_document("test_collection", {"data": "test"})

        # Update with valid patch
        patch = {"status": "updated"}
        store.update_document("test_collection", doc_id, patch)
        # Verify the update
        updated = store.get_document("test_collection", doc_id)
        assert updated["status"] == "updated"

    @requires_schema_validation
    def test_update_invalid_document_strict_mode(self):
        """Test updating with an invalid patch in strict mode fails."""
        base = _create_base_inmemory_store()
        base.connect()

        schema = {"type": "object", "properties": {"status": {"type": "string"}}}

        provider = MockSchemaProvider({"test_collection": schema})
        store = ValidatingDocumentStore(base, provider, strict=True)

        # Insert document
        doc_id = base.insert_document("test_collection", {"data": "test"})

        # Update with invalid patch (wrong type)
        patch = {"status": 123}

        with pytest.raises(DocumentValidationError) as exc_info:
            store.update_document("test_collection", doc_id, patch)

        assert "status" in str(exc_info.value).lower()

    @requires_schema_validation
    def test_update_document_ignores_store_metadata_fields(self):
        """Updating should ignore store-injected metadata for schema validation.

        Some backends (e.g., Azure Cosmos DB) inject system/envelope properties
        on read (id, collection, _etag, etc.). Our schemas often set
        additionalProperties=false, so validation must strip these keys.
        """

        class _MetadataInjectingStore:
            def __init__(self, inner):
                self._inner = inner

            def connect(self):
                return self._inner.connect()

            def disconnect(self):
                return self._inner.disconnect()

            def insert_document(self, collection, doc):
                return self._inner.insert_document(collection, doc)

            def get_document(self, collection, doc_id):
                doc = self._inner.get_document(collection, doc_id)
                if doc is None:
                    return None
                return {
                    **doc,
                    "id": "cosmos-id",
                    "collection": collection,
                    "_etag": "etag",
                    "_rid": "rid",
                    "_self": "self",
                    "_ts": 123,
                    "_attachments": "att",
                }

            def update_document(self, collection, doc_id, patch):
                return self._inner.update_document(collection, doc_id, patch)

            def delete_document(self, collection, doc_id):
                return self._inner.delete_document(collection, doc_id)

            def query_documents(self, collection, filter_dict, limit=100):
                return self._inner.query_documents(collection, filter_dict, limit)

        base = _create_base_inmemory_store()
        base.connect()

        schema = {
            "type": "object",
            "properties": {
                "_id": {"type": "string"},
                "name": {"type": "string"},
                "enabled": {"type": "boolean"},
            },
            "required": ["name"],
            "additionalProperties": False,
        }

        provider = MockSchemaProvider({"sources": schema})
        metadata_base = _MetadataInjectingStore(base)
        store = ValidatingDocumentStore(metadata_base, provider, strict=True)

        doc_id = base.insert_document("sources", {"name": "test-source", "enabled": True})

        # Should not raise, even though current_doc has extra store metadata.
        store.update_document("sources", doc_id, {"enabled": False})

        updated = base.get_document("sources", doc_id)
        assert updated["enabled"] is False

    def test_update_nonexistent_document(self):
        """Test updating a non-existent document raises DocumentNotFoundError."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Try to update a document that doesn't exist
        with pytest.raises(DocumentNotFoundError):
            store.update_document("test_collection", "nonexistent", {"status": "updated"})

    def test_query_documents(self):
        """Test querying documents."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Insert documents
        base.insert_document("test_collection", {"status": "active"})
        base.insert_document("test_collection", {"status": "inactive"})

        # Query through validating store
        results = store.query_documents("test_collection", {"status": "active"})
        assert len(results) == 1
        assert results[0]["status"] == "active"

    def test_delete_document(self):
        """Test deleting a document."""
        base = _create_base_inmemory_store()
        base.connect()

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Insert document
        doc_id = base.insert_document("test_collection", {"data": "test"})

        # Delete through validating store
        store.delete_document("test_collection", doc_id)

        # Verify deletion
        retrieved = store.get_document("test_collection", doc_id)
        assert retrieved is None

    def test_connect_delegates_to_underlying_store(self):
        """Test that connect is delegated to underlying store."""
        base = _create_base_inmemory_store()
        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        store.connect()

    def test_disconnect_delegates_to_underlying_store(self):
        """Test that disconnect is delegated to underlying store."""
        base = _create_base_inmemory_store()
        base.connect()
        assert base.connected is True

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Disconnect through validating store
        store.disconnect()

        # Verify underlying store was disconnected
        assert base.connected is False

    def test_aggregate_documents_delegates_to_underlying_store(self):
        """Test that aggregate_documents is delegated to underlying store."""
        base = _create_base_inmemory_store()
        base.connect()

        # Insert test data
        base.insert_document("messages", {"_id": "msg1", "archive_id": "archive1", "body": "test"})
        base.insert_document("messages", {"_id": "msg2", "archive_id": "archive1", "body": "test2"})
        base.insert_document("chunks", {"_id": "chunk1", "message_doc_id": "msg1"})

        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Execute aggregation through validating store
        pipeline = [
            {
                "$match": {
                    "_id": {"$exists": True},
                }
            },
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "_id",
                    "foreignField": "message_doc_id",
                    "as": "chunks",
                }
            },
            {
                "$match": {
                    "chunks": {"$eq": []},
                }
            },
        ]

        results = store.aggregate_documents("messages", pipeline)

        # Should find msg2 which has no chunks
        assert len(results) == 1
        assert results[0]["_id"] == "msg2"

    def test_aggregate_documents_raises_error_when_not_supported(self):
        """Test that aggregate_documents raises AttributeError when underlying store doesn't support it."""

        # Create a mock store without aggregate_documents method
        class MockStoreWithoutAggregation:
            def connect(self):
                pass

            def disconnect(self):
                pass

        base = MockStoreWithoutAggregation()
        provider = MockSchemaProvider()
        store = ValidatingDocumentStore(base, provider)

        # Should raise AttributeError when aggregate_documents is not supported
        with pytest.raises(AttributeError, match="does not support aggregation"):
            store.aggregate_documents("test", [])
