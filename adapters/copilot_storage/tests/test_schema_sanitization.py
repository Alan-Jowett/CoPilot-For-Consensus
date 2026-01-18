# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema-based document sanitization.

These tests verify that DocumentStore implementations return clean documents
without backend system fields or unknown fields, regardless of the underlying
storage driver (Cosmos/Mongo/InMemory).
"""

import pytest
from typing import Any

from copilot_storage import DocumentStore
from copilot_storage.inmemory_document_store import InMemoryDocumentStore


@pytest.fixture
def store() -> DocumentStore:
    """Create an in-memory document store for testing."""
    store = InMemoryDocumentStore()
    store.connect()
    return store


def _insert_with_backend_fields(store: InMemoryDocumentStore, collection: str, doc: dict[str, Any]) -> None:
    """Helper to insert a document with simulated backend system fields.
    
    This helper directly accesses internal storage to simulate what backend
    implementations (Cosmos/Mongo) actually store, including system fields
    that would normally be added by those backends.
    
    This is necessary for testing sanitization because:
    1. insert_document() goes through the public API which may not add system fields
    2. We need to verify that system fields added by backends are properly removed
    3. This pattern is only used for testing - production code uses public API
    
    Args:
        store: InMemoryDocumentStore instance
        collection: Collection name
        doc: Document with system fields to store
    """
    store.collections[collection][doc["_id"]] = doc.copy()


def test_get_document_removes_system_fields(store: DocumentStore):
    """Test that get_document removes backend system fields."""
    # Insert a document with system fields (simulating Cosmos DB)
    doc_with_system_fields = {
        "_id": "test-id-123",
        "name": "test-source",
        "source_type": "local",
        "url": "/data/test.mbox",
        "enabled": True,
        # System fields that would be added by Cosmos DB
        "_etag": "00000000-0000-0000-0000-000000000000",
        "_rid": "abc123==",
        "_ts": 1700000000,
        "_self": "dbs/abc/colls/def/docs/ghi/",
        "_attachments": "attachments/",
        "id": "cosmos-id",
        "collection": "sources",
    }
    
    # Use helper to simulate backend behavior
    _insert_with_backend_fields(store, "sources", doc_with_system_fields)
    
    # Retrieve the document
    result = store.get_document("sources", "test-id-123")
    
    assert result is not None
    assert result["_id"] == "test-id-123"
    assert result["name"] == "test-source"
    assert result["source_type"] == "local"
    assert result["url"] == "/data/test.mbox"
    assert result["enabled"] is True
    
    # Verify system fields are removed
    assert "_etag" not in result
    assert "_rid" not in result
    assert "_ts" not in result
    assert "_self" not in result
    assert "_attachments" not in result
    assert "id" not in result
    assert "collection" not in result


def test_get_document_removes_unknown_fields(store: DocumentStore):
    """Test that get_document removes unknown fields not in schema."""
    # Insert a document with unknown fields
    doc_with_unknown_fields = {
        "_id": "test-id-456",
        "name": "test-source",
        "source_type": "http",
        "url": "http://example.com/archive.mbox",
        "enabled": True,
        # Unknown fields that should be removed
        "unknown_field_1": "some value",
        "random_metadata": {"nested": "data"},
        "legacy_field": 12345,
    }
    
    _insert_with_backend_fields(store, "sources", doc_with_unknown_fields)
    
    # Retrieve the document
    result = store.get_document("sources", "test-id-456")
    
    assert result is not None
    assert result["_id"] == "test-id-456"
    assert result["name"] == "test-source"
    
    # Verify unknown fields are removed
    assert "unknown_field_1" not in result
    assert "random_metadata" not in result
    assert "legacy_field" not in result


def test_get_document_preserves_required_fields(store: DocumentStore):
    """Test that get_document preserves all required schema fields."""
    # Insert a complete source document
    complete_doc = {
        "_id": "test-id-789",
        "name": "complete-source",
        "source_type": "imap",
        "url": "imap.example.com",
        "port": 993,
        "username": "user@example.com",
        "password": "secret",
        "folder": "INBOX",
        "enabled": True,
        "schedule": "0 */6 * * *",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "last_run_at": "2025-01-01T06:00:00Z",
        "last_run_status": "success",
        "last_error": None,
        "next_run_at": "2025-01-01T12:00:00Z",
        "files_processed": 10,
        "files_skipped": 5,
    }
    
    _insert_with_backend_fields(store, "sources", complete_doc)
    
    # Retrieve the document
    result = store.get_document("sources", "test-id-789")
    
    assert result is not None
    
    # Verify all schema fields are preserved
    assert result["_id"] == "test-id-789"
    assert result["name"] == "complete-source"
    assert result["source_type"] == "imap"
    assert result["url"] == "imap.example.com"
    assert result["port"] == 993
    assert result["username"] == "user@example.com"
    assert result["password"] == "secret"
    assert result["folder"] == "INBOX"
    assert result["enabled"] is True
    assert result["schedule"] == "0 */6 * * *"
    assert result["created_at"] == "2025-01-01T00:00:00Z"
    assert result["updated_at"] == "2025-01-01T00:00:00Z"
    assert result["last_run_at"] == "2025-01-01T06:00:00Z"
    assert result["last_run_status"] == "success"
    assert result["last_error"] is None
    assert result["next_run_at"] == "2025-01-01T12:00:00Z"
    assert result["files_processed"] == 10
    assert result["files_skipped"] == 5


def test_query_documents_removes_system_fields(store: DocumentStore):
    """Test that query_documents removes backend system fields from all results."""
    # Insert multiple documents with system fields
    doc1 = {
        "_id": "archive-1",
        "file_hash": "a" * 64,
        "file_size_bytes": 1024,
        "source": "test-source",
        "ingestion_date": "2025-01-01T00:00:00Z",
        "status": "completed",
        "_etag": "etag-1",
        "_rid": "rid-1",
        "_ts": 1700000001,
        "id": "cosmos-id-1",
        "collection": "archives",
    }
    
    doc2 = {
        "_id": "archive-2",
        "file_hash": "b" * 64,
        "file_size_bytes": 2048,
        "source": "test-source",
        "ingestion_date": "2025-01-02T00:00:00Z",
        "status": "completed",
        "_etag": "etag-2",
        "_rid": "rid-2",
        "_ts": 1700000002,
        "id": "cosmos-id-2",
        "collection": "archives",
    }
    
    _insert_with_backend_fields(store, "archives", doc1)
    _insert_with_backend_fields(store, "archives", doc2)
    
    # Query documents
    results = store.query_documents("archives", {"source": "test-source"})
    
    assert len(results) == 2
    
    for result in results:
        # Verify schema fields are present
        assert "_id" in result
        assert "file_hash" in result
        assert "source" in result
        
        # Verify system fields are removed
        assert "_etag" not in result
        assert "_rid" not in result
        assert "_ts" not in result
        assert "id" not in result
        assert "collection" not in result


def test_query_documents_removes_unknown_fields(store: DocumentStore):
    """Test that query_documents removes unknown fields from all results."""
    # Insert documents with unknown fields
    doc1 = {
        "_id": "msg-1",
        "message_id": "<msg1@example.com>",
        "archive_id": "a" * 16,
        "thread_id": "t" * 16,
        "body_normalized": "Message content",
        "created_at": "2025-01-01T00:00:00Z",
        "unknown_field": "should be removed",
        "legacy_metadata": {"old": "data"},
    }
    
    _insert_with_backend_fields(store, "messages", doc1)
    
    # Query documents
    results = store.query_documents("messages", {"thread_id": "t" * 16})
    
    assert len(results) == 1
    result = results[0]
    
    # Verify schema fields are present
    assert result["_id"] == "msg-1"
    assert result["message_id"] == "<msg1@example.com>"
    assert result["body_normalized"] == "Message content"
    
    # Verify unknown fields are removed
    assert "unknown_field" not in result
    assert "legacy_metadata" not in result


def test_aggregate_documents_removes_system_fields(store: DocumentStore):
    """Test that aggregate_documents removes system fields from results."""
    # Insert a document with system fields
    doc = {
        "_id": "thread-1",
        "subject": "Test Thread",
        "summary_id": None,
        "_etag": "etag-1",
        "id": "cosmos-id-1",
        "collection": "threads",
    }
    
    _insert_with_backend_fields(store, "threads", doc)
    
    # Aggregate with $match
    results = store.aggregate_documents(
        "threads",
        [{"$match": {"summary_id": None}}]
    )
    
    assert len(results) == 1
    result = results[0]
    
    # Verify schema fields are present
    assert result["_id"] == "thread-1"
    assert result["subject"] == "Test Thread"
    
    # Verify system fields are removed
    assert "_etag" not in result
    assert "id" not in result
    assert "collection" not in result


def test_sanitization_with_unknown_collection(store: DocumentStore):
    """Test that sanitization works gracefully with unknown collections.
    
    For collections without a registered schema, only system fields should
    be removed (not unknown fields, since we can't determine what's unknown).
    """
    # Insert a document into an unknown collection
    doc = {
        "_id": "doc-1",
        "custom_field_1": "value1",
        "custom_field_2": "value2",
        "_etag": "etag-1",
        "id": "cosmos-id-1",
        "collection": "unknown_collection",
    }
    
    _insert_with_backend_fields(store, "unknown_collection", doc)
    
    # Retrieve the document
    result = store.get_document("unknown_collection", "doc-1")
    
    assert result is not None
    
    # Custom fields should be preserved (no schema to filter against)
    assert result["_id"] == "doc-1"
    assert result["custom_field_1"] == "value1"
    assert result["custom_field_2"] == "value2"
    
    # System fields should still be removed
    assert "_etag" not in result
    assert "id" not in result
    assert "collection" not in result


def test_get_document_returns_none_when_not_found(store: DocumentStore):
    """Test that get_document returns None for non-existent documents."""
    result = store.get_document("sources", "non-existent-id")
    assert result is None


def test_query_documents_returns_empty_list_when_no_matches(store: DocumentStore):
    """Test that query_documents returns empty list when no documents match."""
    # Insert a document that won't match the query
    doc = {
        "_id": "source-1",
        "name": "test-source",
        "source_type": "local",
        "url": "/data/test.mbox",
        "enabled": True,
    }
    _insert_with_backend_fields(store, "sources", doc)
    
    # Query for a different name
    results = store.query_documents("sources", {"name": "other-source"})
    assert results == []
