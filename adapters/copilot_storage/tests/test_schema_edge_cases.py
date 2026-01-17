# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Additional tests for schema registry edge cases and preserve_extra flag.

These tests address edge cases and features not covered by the basic
sanitization tests.
"""

import json
import tempfile
from pathlib import Path

import pytest

from copilot_storage import DocumentStore, reset_registry
from copilot_storage.inmemory_document_store import InMemoryDocumentStore
from copilot_storage.schema_registry import _initialize_registry, get_collection_fields


@pytest.fixture
def store() -> DocumentStore:
    """Create an in-memory document store for testing."""
    store = InMemoryDocumentStore()
    store.connect()
    return store


@pytest.fixture(autouse=True)
def reset_schema_registry():
    """Reset the schema registry before each test."""
    reset_registry()
    yield
    reset_registry()


def test_preserve_extra_flag_with_aggregations(store: DocumentStore):
    """Test that aggregate_documents preserves extra fields from $lookup."""
    # Insert messages
    store.insert_document("messages", {
        "_id": "msg1",
        "message_id": "<msg1@example.com>",
        "archive_id": "a" * 16,
        "thread_id": "t" * 16,
        "body_normalized": "Hello",
        "created_at": "2025-01-01T00:00:00Z",
    })
    
    # Insert chunks for msg1
    store.insert_document("chunks", {
        "_id": "chunk1",
        "message_doc_id": "msg1",
        "message_id": "<msg1@example.com>",
        "thread_id": "t" * 16,
        "chunk_index": 0,
        "text": "chunk text",
        "created_at": "2025-01-01T00:00:00Z",
        "embedding_generated": True,
    })
    
    # Perform aggregation with $lookup
    pipeline = [
        {
            "$lookup": {
                "from": "chunks",
                "localField": "message_id",
                "foreignField": "message_id",
                "as": "chunks"
            }
        }
    ]
    
    results = store.aggregate_documents("messages", pipeline)
    
    assert len(results) == 1
    result = results[0]
    
    # Verify schema fields are present
    assert result["_id"] == "msg1"
    assert result["message_id"] == "<msg1@example.com>"
    
    # Verify the enriched field from $lookup is preserved
    assert "chunks" in result
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["_id"] == "chunk1"


def test_get_document_does_not_preserve_extra_fields(store: DocumentStore):
    """Test that get_document removes unknown fields (preserve_extra=False by default)."""
    # Insert a document with an unknown field directly
    doc = {
        "_id": "source1",
        "name": "test-source",
        "source_type": "local",
        "url": "/data/test.mbox",
        "enabled": True,
        "unknown_extra_field": "should be removed",
    }
    store.collections["sources"]["source1"] = doc.copy()
    
    result = store.get_document("sources", "source1")
    
    assert result is not None
    assert result["name"] == "test-source"
    # Unknown field should be removed
    assert "unknown_extra_field" not in result


def test_query_documents_does_not_preserve_extra_fields(store: DocumentStore):
    """Test that query_documents removes unknown fields (preserve_extra=False by default)."""
    # Insert a document with an unknown field directly
    doc = {
        "_id": "source1",
        "name": "test-source",
        "source_type": "local",
        "url": "/data/test.mbox",
        "enabled": True,
        "unknown_extra_field": "should be removed",
    }
    store.collections["sources"]["source1"] = doc.copy()
    
    results = store.query_documents("sources", {"name": "test-source"})
    
    assert len(results) == 1
    result = results[0]
    assert result["name"] == "test-source"
    # Unknown field should be removed
    assert "unknown_extra_field" not in result


def test_schema_load_failure_graceful_degradation():
    """Test that schema load failures are handled gracefully."""
    # Reset registry first to clear any previously loaded schemas
    reset_registry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_dir = Path(tmpdir)
        
        # Create an invalid JSON schema file
        invalid_schema = schema_dir / "sources.schema.json"
        invalid_schema.write_text("{ invalid json }")
        
        # Create a valid schema for another collection to ensure registry is populated
        valid_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "_id": {"type": "string"}
            }
        }
        (schema_dir / "archives.schema.json").write_text(json.dumps(valid_schema))
        
        # Try to initialize with the invalid schema
        _initialize_registry(schema_dir)
        
        # Should return None for sources since schema failed to load
        # but archives should work
        sources_fields = get_collection_fields("sources")
        assert sources_fields is None
        
        archives_fields = get_collection_fields("archives")
        assert archives_fields == {"_id"}


def test_schema_with_empty_properties():
    """Test handling of schema with empty properties object."""
    # Reset registry first to clear any previously loaded schemas
    reset_registry()
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_dir = Path(tmpdir)
        
        # Create a schema with empty properties
        empty_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {}
        }
        schema_file = schema_dir / "sources.schema.json"
        schema_file.write_text(json.dumps(empty_schema))
        
        # Initialize with the empty schema
        _initialize_registry(schema_dir)
        
        # Should return empty set for the collection
        fields = get_collection_fields("sources")
        assert fields == set()


def test_missing_schema_file_for_collection():
    """Test handling when schema directory exists but specific collection's schema is missing."""
    # Reset registry first to clear any previously loaded schemas
    reset_registry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_dir = Path(tmpdir)
        
        # Create schema for one collection but not another
        archives_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "_id": {"type": "string"},
                "file_hash": {"type": "string"}
            }
        }
        (schema_dir / "archives.schema.json").write_text(json.dumps(archives_schema))
        
        # Initialize with the directory (sources.schema.json doesn't exist)
        _initialize_registry(schema_dir)
        
        # archives should have schema
        archives_fields = get_collection_fields("archives")
        assert archives_fields == {"_id", "file_hash"}
        
        # sources should not have schema
        sources_fields = get_collection_fields("sources")
        assert sources_fields is None


def test_schema_directory_does_not_exist():
    """Test handling when schema directory doesn't exist."""
    # Reset registry first to clear any previously loaded schemas
    reset_registry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        non_existent = Path(tmpdir) / "does_not_exist"
        
        # Try to initialize with non-existent directory
        _initialize_registry(non_existent)
        
        # Registry should be empty (not lazily initialized with default dir)
        # because we explicitly initialized it
        # The function should have logged a warning but not loaded any schemas
        # Check the registry directly to avoid triggering lazy init
        from copilot_storage.schema_registry import _COLLECTION_SCHEMAS
        
        # After init with non-existent dir, registry should be empty
        assert len(_COLLECTION_SCHEMAS) == 0


def test_reset_registry_clears_schemas():
    """Test that reset_registry clears loaded schemas."""
    # Initialize with default schemas
    _initialize_registry()
    
    # Verify a schema was loaded
    fields_before = get_collection_fields("sources")
    assert fields_before is not None
    
    # Reset the registry
    reset_registry()
    
    # After reset, schemas should be reloaded on next access
    fields_after = get_collection_fields("sources")
    assert fields_after is not None
    # Should be the same schema
    assert fields_after == fields_before


def test_aggregate_with_computed_fields_preserved(store: DocumentStore):
    """Test that aggregation with computed fields preserves them."""
    # Insert some threads
    store.insert_document("threads", {
        "_id": "thread1",
        "subject": "Test Thread 1",
        "summary_id": None,
    })
    store.insert_document("threads", {
        "_id": "thread2",
        "subject": "Test Thread 2",
        "summary_id": "summary1",
    })
    
    # Simple aggregation with $match
    pipeline = [
        {"$match": {"summary_id": None}}
    ]
    
    results = store.aggregate_documents("threads", pipeline)
    
    assert len(results) == 1
    assert results[0]["_id"] == "thread1"
    # Even though preserve_extra=True in aggregate, system fields should still be removed
    assert "id" not in results[0]
    assert "collection" not in results[0]
