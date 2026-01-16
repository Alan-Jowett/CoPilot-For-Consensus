# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the orchestration service."""

from pathlib import Path

import pytest
from app.service import OrchestrationService
from copilot_message_bus import create_publisher, create_subscriber
from copilot_storage import create_document_store
from copilot_config.generated.adapters.document_store import AdapterConfig_DocumentStore, DriverConfig_DocumentStore_Inmemory
from copilot_config.generated.adapters.message_bus import AdapterConfig_MessageBus, DriverConfig_MessageBus_Noop

pytestmark = pytest.mark.integration


def create_query_with_in_support(original_query):
    """Create a custom query function that supports MongoDB $in operator.

    Args:
        original_query: The original query_documents method from the document store

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
        # Handle $in operator for _id (canonical document primary key)
        if "_id" in filter_dict and isinstance(filter_dict["_id"], dict):
            doc_ids = filter_dict["_id"].get("$in", [])
            results = []
            for doc_id in doc_ids:
                doc_results = original_query(collection, {"_id": doc_id}, limit)
                results.extend(doc_results)
            return results[:limit]
        # Handle $in operator for message_doc_id (chunk foreign key reference)
        elif "message_doc_id" in filter_dict and isinstance(filter_dict["message_doc_id"], dict):
            message_doc_ids = filter_dict["message_doc_id"].get("$in", [])
            results = []
            for message_doc_id in message_doc_ids:
                msg_results = original_query(collection, {"message_doc_id": message_doc_id}, limit)
                results.extend(msg_results)
            return results[:limit]  # Respect limit
        else:
            return original_query(collection, filter_dict, limit)

    return custom_query


@pytest.fixture
def document_store():
    """Create an in-memory document store with schema validation for testing."""
    # Create base in-memory store using factory
    base_store = create_document_store(
        AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
        enable_validation=False,
    )
    base_store.connect()

    # Override query_documents to support $in operator
    base_store.query_documents = create_query_with_in_support(base_store.query_documents)

    # Note: Schema validation is handled by the factory-created store
    return base_store


@pytest.fixture
def prompt_files(tmp_path_factory):
    """Create temporary prompt files for testing.

    Uses tmp_path_factory to ensure temporary directory persists for the entire
    test session, avoiding file not found errors if OrchestrationService reloads
    prompts or if tests run in different orders.
    """
    tmpdir = tmp_path_factory.mktemp("prompts")

    # Create system prompt file
    system_path = tmpdir / "system.txt"
    system_path.write_text("You are a professional summarizer. Summarize the following email thread.")

    # Create user prompt file
    user_path = tmpdir / "user.txt"
    user_path.write_text("Thread: {thread_id}\n\nMessages:\n{email_chunks}")

    yield str(system_path), str(user_path)


@pytest.fixture
def publisher():
    """Create a noop publisher for testing."""
    pub = create_publisher(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    pub.connect()
    return pub


@pytest.fixture
def subscriber():
    """Create a noop subscriber for testing."""
    sub = create_subscriber(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    sub.connect()
    return sub


@pytest.fixture
def service(document_store, publisher, subscriber, prompt_files):
    """Create an orchestration service for integration testing."""
    system_path, user_path = prompt_files
    return OrchestrationService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
        top_k=5,
        context_window_tokens=1000,
        system_prompt_path=system_path,
        user_prompt_path=user_path,
    )


@pytest.mark.integration
def test_end_to_end_orchestration(service, document_store):
    """Test end-to-end orchestration flow."""
    from datetime import datetime, timezone

    # Setup test data in document store
    now = datetime.now(timezone.utc).isoformat()

    # Insert chunks
    chunk_ids = []
    chunks = [
        {
            "_id": "aaaa1111bbbb2222",
            "message_doc_id": "abc123def4567890",
            "message_id": "<msg-1@example.com>",
            "thread_id": "1111222233334444",
            "text": "This is a test chunk about QUIC protocol.",
            "chunk_index": 0,
            "token_count": 10,
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "_id": "cccc3333dddd4444",
            "message_doc_id": "fedcba9876543210",
            "message_id": "<msg-2@example.com>",
            "thread_id": "1111222233334444",
            "text": "Discussion about connection migration in QUIC.",
            "chunk_index": 0,
            "token_count": 8,
            "embedding_generated": True,
            "created_at": now,
        },
    ]

    for chunk in chunks:
        chunk_ids.append(chunk["_id"])
        document_store.insert_document("chunks", chunk)

    # Insert messages
    messages = [
        {
            "_id": "abc123def4567890",
            "message_id": "<msg-1@example.com>",
            "archive_id": "a1b2c3d4e5f67890",
            "thread_id": "1111222233334444",
            "body_normalized": "This is a test message about QUIC protocol.",
            "subject": "QUIC Protocol Discussion",
            "from": {"name": "Alice", "email": "alice@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": ["draft-ietf-quic-transport-34"],
            "created_at": now,
        },
        {
            "_id": "fedcba9876543210",
            "message_id": "<msg-2@example.com>",
            "archive_id": "a1b2c3d4e5f67890",
            "thread_id": "1111222233334444",
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

    now = datetime.now(timezone.utc).isoformat()

    # Setup chunks from different threads
    chunk_ids = []
    chunks = [
        {
            "_id": "eeee5555ffff6666",
            "message_doc_id": "aaa1111bbb222222",
            "message_id": "<msg-1@example.com>",
            "thread_id": "2222333344445555",
            "chunk_index": 0,
            "text": "Thread 1 content",
            "token_count": 5,
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "_id": "aaaa7777bbbb8888",
            "message_doc_id": "ccc3333ddd444444",
            "message_id": "<msg-2@example.com>",
            "thread_id": "6666777788889999",
            "chunk_index": 0,
            "text": "Thread 2 content",
            "token_count": 5,
            "embedding_generated": True,
            "created_at": now,
        },
        {
            "_id": "cccc9999ddddaaaa",
            "message_doc_id": "eee5555fff666666",
            "message_id": "<msg-3@example.com>",
            "thread_id": "2222333344445555",
            "chunk_index": 0,
            "text": "More thread 1 content",
            "token_count": 6,
            "embedding_generated": True,
            "created_at": now,
        },
    ]

    for chunk in chunks:
        chunk_ids.append(chunk["_id"])
        document_store.insert_document("chunks", chunk)

    # Insert corresponding messages
    messages = [
        {
            "_id": "aaa1111bbb222222",
            "message_id": "<msg-1@example.com>",
            "archive_id": "a1b2c3d4e5f67890",
            "thread_id": "2222333344445555",
            "body_normalized": "Test message content 1",
            "subject": "Test Subject 1",
            "created_at": now,
            "from": {"email": "user1@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        },
        {
            "_id": "ccc3333ddd444444",
            "message_id": "<msg-2@example.com>",
            "archive_id": "a1b2c3d4e5f67890",
            "thread_id": "6666777788889999",
            "body_normalized": "Test message content 2",
            "subject": "Test Subject 2",
            "created_at": now,
            "from": {"email": "user2@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        },
        {
            "_id": "eee5555fff666666",
            "message_id": "<msg-3@example.com>",
            "archive_id": "a1b2c3d4e5f67890",
            "thread_id": "2222333344445555",
            "body_normalized": "Test message content 3",
            "subject": "Test Subject 3",
            "created_at": now,
            "from": {"email": "user3@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        },
    ]

    for msg in messages:
        document_store.insert_document("messages", msg)

    # Process embeddings event
    event_data = {
        "chunk_ids": chunk_ids,
        "embedding_count": 3,
    }

    service.process_embeddings(event_data)

    # Should orchestrate 2 threads
    assert service.threads_orchestrated == 2
