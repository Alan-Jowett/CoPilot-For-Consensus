# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the embedding service."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from app.service import EmbeddingService
from copilot_embedding import create_embedding_provider
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store
from copilot_vectorstore import create_vector_store

pytestmark = pytest.mark.integration


def _add_in_operator_support(store):
    original_query = store.query_documents

    def query_with_in_support(collection: str, filter_dict: dict[str, object], limit: int = 100):
        if isinstance(filter_dict, dict):
            if "_id" in filter_dict and isinstance(filter_dict["_id"], dict):
                doc_ids = filter_dict["_id"].get("$in", [])
                results = []
                for doc_id in doc_ids:
                    results.extend(original_query(collection, {"_id": doc_id}, limit))
                return results[:limit]
        return original_query(collection, filter_dict, limit)

    return query_with_in_support


@pytest.fixture
def in_memory_document_store():
    """Create an in-memory document store with MongoDB-like $in support."""
    schema_provider = create_schema_provider(
        schema_dir=str(Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"),
        schema_type="documents"
    )

    document_store = create_document_store(
        driver_name="inmemory",
        driver_config={"schema_provider": schema_provider},
        enable_validation=True,
    )
    document_store.connect()

    # Add $in operator support on the underlying store
    if hasattr(document_store, "_store"):
        document_store._store.query_documents = _add_in_operator_support(document_store._store)
    else:
        document_store.query_documents = _add_in_operator_support(document_store)

    return document_store


@pytest.fixture
def in_memory_vector_store():
    """Create an in-memory vector store."""
    return create_vector_store(driver_name="inmemory", driver_config={})


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    return create_embedding_provider(driver_name="mock", driver_config={"dimension": 384})


@pytest.fixture
def mock_publisher():
    """Create a mock event publisher."""
    publisher = Mock()
    publisher.publish = Mock()
    return publisher


@pytest.fixture
def mock_subscriber():
    """Create a mock event subscriber."""
    subscriber = Mock()
    subscriber.subscribe = Mock()
    return subscriber


@pytest.fixture
def embedding_service(
    in_memory_document_store,
    in_memory_vector_store,
    mock_embedding_provider,
    mock_publisher,
    mock_subscriber,
):
    """Create an embedding service with in-memory adapters."""
    return EmbeddingService(
        document_store=in_memory_document_store,
        vector_store=in_memory_vector_store,
        embedding_provider=mock_embedding_provider,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        embedding_model="all-MiniLM-L6-v2",
        embedding_backend="sentencetransformers",
        embedding_dimension=384,
        batch_size=2,  # Small batch for testing
    )


@pytest.mark.integration
def test_end_to_end_embedding_generation(
    embedding_service,
    in_memory_document_store,
    in_memory_vector_store,
    mock_publisher,
):
    """Test end-to-end embedding generation flow."""
    # Insert test chunks into document store
    chunks = [
        {
            "_id": "aaaa1111bbbb2222",
            "message_doc_id": "abc123def4567890",
            "message_id": "<msg1@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "text": "This is the first chunk of text for testing embeddings.",
            "token_count": 10,
            "metadata": {
                "sender": "alice@example.com",
                "sender_name": "Alice",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test Message",
                "draft_mentions": ["draft-ietf-quic-transport-34"],
            },
            "created_at": "2023-10-15T12:00:00Z",
            "embedding_generated": False,
        },
        {
            "_id": "cccc3333dddd4444",
            "message_doc_id": "abc123def4567890",
            "message_id": "<msg1@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "chunk_index": 1,
            "text": "This is the second chunk with more content for embedding.",
            "token_count": 10,
            "metadata": {
                "sender": "alice@example.com",
                "sender_name": "Alice",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test Message",
                "draft_mentions": ["draft-ietf-quic-transport-34"],
            },
            "created_at": "2023-10-15T12:00:00Z",
            "embedding_generated": False,
        },
        {
            "_id": "eeee5555ffff6666",
            "message_doc_id": "fedcba9876543210",
            "message_id": "<msg2@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "text": "Third chunk from a different message in the same thread.",
            "token_count": 10,
            "metadata": {
                "sender": "bob@example.com",
                "sender_name": "Bob",
                "date": "2023-10-15T13:00:00Z",
                "subject": "Re: Test Message",
                "draft_mentions": [],
            },
            "created_at": "2023-10-15T13:00:00Z",
            "embedding_generated": False,
        },
    ]

    for chunk in chunks:
        in_memory_document_store.insert_document("chunks", chunk)

    # Process chunks
    event_data = {
        "chunk_ids": ["aaaa1111bbbb2222", "cccc3333dddd4444", "eeee5555ffff6666"],
        "chunk_count": 3,
    }

    embedding_service.process_chunks(event_data)

    # Verify embeddings were stored in vector store
    assert in_memory_vector_store.count() == 3

    # Verify chunk status was updated
    updated_chunks = in_memory_document_store.query_documents(
        collection="chunks",
        filter_dict={"embedding_generated": True}
    )

    assert len(updated_chunks) == 3
    for chunk in updated_chunks:
        assert chunk["embedding_generated"] is True

    # Verify success event was published
    mock_publisher.publish.assert_called()
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "embeddings.generated"

    event = publish_call[1]["event"]
    assert event["event_type"] == "EmbeddingsGenerated"
    assert len(event["data"]["chunk_ids"]) == 3
    assert event["data"]["embedding_count"] == 3

    # Verify embeddings can be queried
    query_vector = [0.1] * 384
    results = in_memory_vector_store.query(query_vector, top_k=2)

    assert len(results) == 2
    assert results[0].metadata["chunk_id"] in [
        "aaaa1111bbbb2222",
        "cccc3333dddd4444",
        "eeee5555ffff6666",
    ]
    assert "text" in results[0].metadata
    assert "sender" in results[0].metadata
    assert "embedding_model" in results[0].metadata


@pytest.mark.integration
def test_batch_processing_integration(
    embedding_service,
    in_memory_document_store,
    in_memory_vector_store,
):
    """Test that batching works correctly with real adapters."""
    # Create 5 chunks (will be processed in batches of 2)
    chunk_ids = [f"{i:01x}{'a' * 15}" for i in range(5)]  # Generate 16-hex IDs
    msg_ids = [f"{i:01x}{'b' * 15}" for i in range(5)]  # Generate 16-hex message IDs
    chunks = [
        {
            "_id": chunk_ids[i],
            "message_doc_id": msg_ids[i],
            "message_id": f"<msg{i}@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "chunk_index": i,
            "text": f"Text for chunk {i}",
            "token_count": 5,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            },
            "created_at": "2023-10-15T12:00:00Z",
            "embedding_generated": False,
        }
        for i in range(5)
    ]

    for chunk in chunks:
        in_memory_document_store.insert_document("chunks", chunk)

    event_data = {
        "chunk_ids": chunk_ids,
    }

    embedding_service.process_chunks(event_data)

    # Verify all chunks were embedded
    assert in_memory_vector_store.count() == 5

    # Verify all chunks have embedding_generated=True
    updated_chunks = in_memory_document_store.query_documents(
        collection="chunks",
        filter_dict={"embedding_generated": True}
    )

    assert len(updated_chunks) == 5
    for chunk in updated_chunks:
        assert chunk["embedding_generated"] is True


@pytest.mark.integration
def test_metadata_preservation(
    embedding_service,
    in_memory_document_store,
    in_memory_vector_store,
):
    """Test that metadata is correctly preserved in vector store."""
    chunk = {
        "_id": "aaaa1111bbbbcccc",
        "message_doc_id": "abc123def4567890",
        "message_id": "<msg@example.com>",
        "thread_id": "1111222233334444",
        "archive_id": "archive-123",
        "chunk_index": 0,
        "text": "Test chunk with metadata",
        "token_count": 5,
        "metadata": {
            "sender": "alice@ietf.org",
            "sender_name": "Alice Developer",
            "date": "2023-10-15T14:30:00Z",
            "subject": "QUIC connection migration",
            "draft_mentions": ["draft-ietf-quic-transport-34", "draft-ietf-quic-recovery-34"],
        },
        "created_at": "2023-10-15T14:30:00Z",
        "embedding_generated": False,
    }

    in_memory_document_store.insert_document("chunks", chunk)

    event_data = {
        "chunk_ids": ["aaaa1111bbbbcccc"],
    }

    embedding_service.process_chunks(event_data)

    # Query the embedding from vector store
    query_vector = [0.1] * 384
    results = in_memory_vector_store.query(query_vector, top_k=1)

    assert len(results) == 1
    metadata = results[0].metadata

    # Verify all metadata fields are present
    assert metadata["chunk_id"] == "aaaa1111bbbbcccc"
    assert metadata["message_id"] == "<msg@example.com>"
    assert metadata["thread_id"] == "1111222233334444"
    assert metadata["archive_id"] == "archive-123"
    assert metadata["chunk_index"] == 0
    assert metadata["text"] == "Test chunk with metadata"
    assert metadata["sender"] == "alice@ietf.org"
    assert metadata["sender_name"] == "Alice Developer"
    assert metadata["date"] == "2023-10-15T14:30:00Z"
    assert metadata["subject"] == "QUIC connection migration"
    assert metadata["draft_mentions"] == ["draft-ietf-quic-transport-34", "draft-ietf-quic-recovery-34"]
    assert metadata["token_count"] == 5
    assert metadata["embedding_model"] == "all-MiniLM-L6-v2"
    assert metadata["embedding_backend"] == "sentencetransformers"
    assert "embedding_date" in metadata
