# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Schema-Aware Testing Guide

This guide explains how to write tests that respect schema validation boundaries in the Copilot-for-Consensus project.

## Overview

Schema validation is a critical contract boundary in the system. Tests that bypass validation create a false sense of safety and may allow subtle bugs or integration mismatches to propagate into production.

This project enforces schema validation at two key layers:
1. **ValidatingDocumentStore** - Validates documents before database operations
2. **ValidatingEventPublisher** - Validates events before publishing to the message bus

## Test Fixtures

The `tests/fixtures` module provides helpers to generate schema-compliant test data.

### Document Fixtures

Located in `tests/fixtures/document_fixtures.py`:

```python
from tests.fixtures.document_fixtures import (
    create_valid_message,
    create_valid_chunk,
    create_valid_thread,
    create_valid_archive,
)

# Create a schema-compliant message
message = create_valid_message(
    message_id="<test@example.com>",
    subject="Test Subject",
    body_normalized="Test message body",
    from_email="sender@example.com",
)

# Create a schema-compliant chunk
chunk = create_valid_chunk(
    message_id="<test@example.com>",
    chunk_index=0,
    text="Chunk text content",
    token_count=10,
)
```

### Event Fixtures

Located in `tests/fixtures/event_fixtures.py`:

```python
from tests/fixtures.event_fixtures import (
    create_valid_event,
    create_archive_ingested_event,
    create_json_parsed_event,
    create_chunks_prepared_event,
)

# Create a generic schema-compliant event
event = create_valid_event(
    event_type="ArchiveIngested",
    data={"archive_id": "abc123def4567890"}
)

# Or use event-specific helpers
event = create_archive_ingested_event(
    archive_id="abc123def4567890",
    source_name="test-source",
)
```

## Validation Helpers

Each service's `test_helpers.py` module includes validation functions:

```python
from .test_helpers import (
    assert_valid_document_schema,
    assert_valid_event_schema,
)

# Validate a document against its schema
document = create_valid_message()
assert_valid_document_schema(document, "messages")

# Validate an event against its schema
event = create_archive_ingested_event()
assert_valid_event_schema(event)
```

## Writing Schema-Aware Tests

### Good Practice: Use Schema-Compliant Fixtures

```python
def test_chunk_message_success(chunking_service):
    """Test chunking a message successfully."""
    # Use schema-compliant fixture
    message = create_valid_message(
        message_id="<test@example.com>",
        body_normalized="Test content " * 100,
    )

    chunks = chunking_service._chunk_message(message)

    # Validate results
    assert len(chunks) > 0
    for chunk in chunks:
        assert_valid_document_schema(chunk, "chunks")
```

### Bad Practice: Raw Test Data (Avoid This)

```python
def test_chunk_message_bad(chunking_service):
    """AVOID: Using raw test data bypasses schema validation."""
    message = {
        "_id": "abc123",  # Wrong format - should be 16 hex chars
        "message_id": "<test@example.com>",
        # Missing required fields like thread_id, archive_id, etc.
    }
    
    # This may pass but doesn't validate schema compliance
    chunks = chunking_service._chunk_message(message)
```

## When to Use Mocks vs Real Validation

### Use Mocks For:
- **External dependencies** (APIs, network calls, file system)
- **Isolating unit behavior** when testing a single function
- **Performance** when full validation is too expensive

### Use Real Validation For:
- **Document creation** - Always use `create_valid_message()`, `create_valid_chunk()`, etc.
- **Event generation** - Always use event fixture helpers
- **Integration tests** - Enable `enable_validation=True` on document stores and publishers
- **Service tests** - Validate outputs with `assert_valid_document_schema()`

## Example: Refactoring a Test

### Before (Bypasses Validation)
```python
def test_process_chunks(embedding_service, mock_store):
    """Old approach: raw test data."""
    chunks = [
        {
            "_id": "chunk-1",
            "text": "Test",
            # Missing many required fields...
        }
    ]
    mock_store.query_documents.return_value = chunks
    embedding_service.process_chunks({"chunk_ids": ["chunk-1"]})
```

### After (Schema-Aware)
```python
def test_process_chunks(embedding_service, mock_store):
    """New approach: schema-compliant fixtures."""
    chunks = [
        create_valid_chunk(
            text="Test",
            chunk_index=0,
            **{"_id": "abc123def4567890"}  # Override _id if needed
        )
    ]
    
    # Verify schema compliance
    for chunk in chunks:
        assert_valid_document_schema(chunk, "chunks")
    
    mock_store.query_documents.return_value = chunks
    embedding_service.process_chunks({"chunk_ids": ["abc123def4567890"]})
```

## Adding Schema Validation Tests

Every service test suite should include at least one explicit schema validation test:

```python
def test_schema_validation_enforced(service):
    """Verify that generated documents are schema-compliant."""
    # Create input using fixtures
    input_data = create_valid_message()
    
    # Process
    output = service.process(input_data)
    
    # Explicitly validate output
    assert_valid_document_schema(output, "expected_collection")
```

## Testing Invalid Data

When testing error handling for invalid data:

```python
def test_rejects_invalid_document(validating_store):
    """Test that invalid documents are rejected."""
    invalid_doc = {
        "_id": "too-short",  # Invalid: not 16 hex chars
        # Missing required fields...
    }
    
    with pytest.raises(DocumentValidationError):
        validating_store.insert_document("messages", invalid_doc)
```

## Integration Tests

Integration tests should use real validation:

```python
@pytest.fixture
def document_store_with_validation():
    """Create a document store with validation enabled."""
    from copilot_storage import create_document_store
    
    store = create_document_store(
        driver_name="inmemory",
        enable_validation=True,  # Enable validation
    )
    store.connect()
    return store

def test_end_to_end_with_validation(document_store_with_validation):
    """Integration test with real validation."""
    message = create_valid_message()
    
    # This will raise if message is invalid
    doc_id = document_store_with_validation.insert_document("messages", message)
    assert doc_id
```

## When to Opt-Out of Validation

In rare cases, you may need to bypass validation:

1. **Testing validation itself** - When testing ValidatingDocumentStore behavior
2. **Performance benchmarks** - When measuring raw throughput
3. **Legacy test compatibility** - During gradual refactoring (temporary only)

If you must bypass validation, use `enable_validation=False` explicitly and document why:

```python
@pytest.fixture
def unvalidated_store():
    """Create store without validation.
    
    NOTE: Used only for testing ValidatingDocumentStore wrapper behavior.
    Regular tests should use validation.
    """
    return create_document_store(
        driver_name="inmemory",
        enable_validation=False,  # Explicit opt-out
    )
```

## Summary

- **Always** use fixture helpers like `create_valid_message()` and `create_valid_chunk()`
- **Always** validate outputs with `assert_valid_document_schema()` or `assert_valid_event_schema()`
- **Enable** validation in integration tests with `enable_validation=True`
- **Mock** external dependencies, not schema validation
- **Add** explicit schema validation tests to each service
- **Document** any opt-outs with clear reasoning

Following these practices ensures that tests accurately reflect production behavior and catch schema violations early.
