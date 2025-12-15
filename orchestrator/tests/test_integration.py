# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the orchestration service."""

import pytest
from pathlib import Path

from copilot_events import NoopPublisher, NoopSubscriber
from copilot_storage import InMemoryDocumentStore, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider

from app.service import OrchestrationService


def create_query_with_in_support(original_query):
    """Create a custom query function that supports MongoDB $in operator.

    Args:
        original_query: The original query_documents method from InMemoryDocumentStore

    Returns:
        A custom query function that supports $in operator
    """
    def custom_query(collection, filter_dict, limit=100):
        # Handle $in operator for chunk_ids
        if "chunk_id" in filter_dict and isinstance(filter_dict["chunk_id"], dict):
            chunk_ids = filter_dict["chunk_id"].get("$in", [])
            results = []
            for chunk_id in chunk_ids:
                chunk_results = original_query(collection, {"chunk_id": chunk_id}, limit)
                results.extend(chunk_results)
            return results[:limit]  # Respect limit
        # Handle $in operator for message_ids
        elif "message_id" in filter_dict and isinstance(filter_dict["message_id"], dict):
            message_ids = filter_dict["message_id"].get("$in", [])
            results = []
            for message_id in message_ids:
                msg_results = original_query(collection, {"message_id": message_id}, limit)
                results.extend(msg_results)
            return results[:limit]  # Respect limit
        else:
            return original_query(collection, filter_dict, limit)

    return custom_query


@pytest.fixture
def document_store():
    """Create an in-memory document store with schema validation for testing."""
    # Create base in-memory store
    base_store = InMemoryDocumentStore()
    
    # Override query_documents to support $in operator
    base_store.query_documents = create_query_with_in_support(base_store.query_documents)
    
    # Wrap with validation using document schemas
    schema_dir = Path(__file__).parent.parent.parent / "documents" / "schemas" / "documents"
    schema_provider = FileSchemaProvider(schema_dir=schema_dir)
    validating_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider
    )
    
    return validating_store


@pytest.fixture
def publisher():
    """Create a noop publisher for testing."""
    return NoopPublisher()


@pytest.fixture
def subscriber():
    """Create a noop subscriber for testing."""
    return NoopSubscriber()


@pytest.fixture
def service(document_store, publisher, subscriber):
    """Create an orchestration service for integration testing."""
    return OrchestrationService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
        top_k=5,
        context_window_tokens=1000,
    )


@pytest.mark.integration
def test_end_to_end_orchestration(service, document_store):
    """Test end-to-end orchestration flow."""
    from datetime import datetime, timezone
    import uuid
    
    # Setup test data in document store
    thread_id = "<thread-1@example.com>"
    now = datetime.now(timezone.utc).isoformat()

    # Insert chunks
    chunk_ids = []
    chunks = [
        {
            "chunk_id": str(uuid.uuid4()),
            "message_id": "<msg-1@example.com>",
            "thread_id": thread_id,
            "text": "This is a test chunk about QUIC protocol.",
            "chunk_index": 0,
            "token_count": 10,
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "chunk_id": str(uuid.uuid4()),
            "message_id": "<msg-2@example.com>",
            "thread_id": thread_id,
            "text": "Discussion about connection migration in QUIC.",
            "chunk_index": 0,
            "token_count": 8,
            "embedding_generated": True,
            "created_at": now,
        },
    ]

    for chunk in chunks:
        chunk_ids.append(chunk["chunk_id"])
        document_store.insert_document("chunks", chunk)

    # Insert messages
    messages = [
        {
            "message_id": "<msg-1@example.com>",
            "archive_id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "body_normalized": "This is a test message about QUIC protocol.",
            "subject": "QUIC Protocol Discussion",
            "from": {"name": "Alice", "email": "alice@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": ["draft-ietf-quic-transport-34"],
            "created_at": now,
        },
        {
            "message_id": "<msg-2@example.com>",
            "archive_id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "body_normalized": "Discussion about connection migration in QUIC.",
            "subject": "Re: QUIC Protocol Discussion",
            "from": {"name": "Bob", "email": "bob@example.com"},
            "date": "2023-10-15T13:00:00Z",
            "draft_mentions": [],
            "created_at": now,
        },
    ]

    for message in messages:
        document_store.insert_document("messages", message)

    # Process embeddings event
    event_data = {
        "chunk_ids": chunk_ids,
        "embedding_count": 2,
        "embedding_model": "all-MiniLM-L6-v2",
    }

    service.process_embeddings(event_data)

    # Verify service state
    assert service.events_processed == 0  # process_embeddings doesn't increment this
    assert service.threads_orchestrated == 1
    assert service.failures_count == 0


@pytest.mark.integration
def test_orchestration_with_no_chunks(service, document_store):
    """Test orchestration when no chunks are found."""
    # Process event with non-existent chunk IDs
    event_data = {
        "chunk_ids": ["non-existent-1", "non-existent-2"],
        "embedding_count": 2,
    }

    service.process_embeddings(event_data)

    # Should not orchestrate any threads
    assert service.threads_orchestrated == 0


@pytest.mark.integration
def test_orchestration_with_multiple_threads(service, document_store):
    """Test orchestration with chunks from multiple threads."""
    from datetime import datetime, timezone
    import uuid
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Setup chunks from different threads
    chunk_ids = []
    chunks = [
        {
            "chunk_id": str(uuid.uuid4()),
            "message_id": "<msg-1@example.com>",
            "thread_id": "<thread-1@example.com>",
            "chunk_index": 0,
            "text": "Thread 1 content",
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "chunk_id": str(uuid.uuid4()),
            "message_id": "<msg-2@example.com>",
            "thread_id": "<thread-2@example.com>",
            "chunk_index": 0,
            "text": "Thread 2 content",
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "chunk_id": str(uuid.uuid4()),
            "message_id": "<msg-3@example.com>",
            "thread_id": "<thread-1@example.com>",
            "chunk_index": 0,
            "text": "More thread 1 content",
            "embedding_generated": True,
            "created_at": now,
        },
    ]

    for chunk in chunks:
        chunk_ids.append(chunk["chunk_id"])
        document_store.insert_document("chunks", chunk)

    # Insert corresponding messages
    for i in range(1, 4):
        document_store.insert_document("messages", {
            "message_id": f"<msg-{i}@example.com>",
            "archive_id": str(uuid.uuid4()),
            "thread_id": f"<thread-{1 if i != 2 else 2}@example.com>",
            "body_normalized": f"Test message content {i}",
            "subject": f"Test Subject {i}",
            "created_at": now,
            "from": {"email": f"user{i}@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        })

    # Process embeddings event
    event_data = {
        "chunk_ids": chunk_ids,
        "embedding_count": 3,
    }

    service.process_embeddings(event_data)

    # Should orchestrate 2 threads
    assert service.threads_orchestrated == 2
