# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the embedding service."""

import pytest
from unittest.mock import Mock

from app.service import EmbeddingService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    store.update_document = Mock()  # No return value - raises exception on error
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    store.add_embeddings = Mock()
    return store


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    provider = Mock()
    # Return a fixed-dimension embedding
    provider.embed = Mock(return_value=[0.1] * 384)
    return provider


@pytest.fixture
def mock_publisher():
    """Create a mock event publisher."""
    publisher = Mock()
    publisher.publish = Mock(return_value=True)
    return publisher


@pytest.fixture
def mock_subscriber():
    """Create a mock event subscriber."""
    subscriber = Mock()
    subscriber.subscribe = Mock()
    return subscriber


@pytest.fixture
def embedding_service(
    mock_document_store,
    mock_vector_store,
    mock_embedding_provider,
    mock_publisher,
    mock_subscriber,
):
    """Create an embedding service instance."""
    return EmbeddingService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        embedding_provider=mock_embedding_provider,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        embedding_model="all-MiniLM-L6-v2",
        embedding_backend="sentencetransformers",
        embedding_dimension=384,
        batch_size=32,
    )


def test_service_initialization(embedding_service):
    """Test that the service initializes correctly."""
    assert embedding_service.document_store is not None
    assert embedding_service.vector_store is not None
    assert embedding_service.embedding_provider is not None
    assert embedding_service.publisher is not None
    assert embedding_service.subscriber is not None
    assert embedding_service.chunks_processed == 0
    assert embedding_service.embeddings_generated_total == 0
    assert embedding_service.embedding_model == "all-MiniLM-L6-v2"
    assert embedding_service.embedding_backend == "sentencetransformers"
    assert embedding_service.embedding_dimension == 384


def test_service_start(embedding_service, mock_subscriber):
    """Test that the service subscribes to events on start."""
    embedding_service.start()
    
    # Verify subscription was called
    mock_subscriber.subscribe.assert_called_once()
    call_args = mock_subscriber.subscribe.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "chunks.prepared"


def test_process_chunks_success(embedding_service, mock_document_store, mock_vector_store, mock_embedding_provider, mock_publisher):
    """Test processing chunks successfully."""
    # Setup mock data
    chunk_ids = ["chunk-1", "chunk-2", "chunk-3"]
    chunks = [
        {
            "_id": "chunk-1",
            "chunk_id": "chunk-1",
            "message_id": "<msg1@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "text": "This is chunk 1 text.",
            "token_count": 10,
            "metadata": {
                "sender": "user1@example.com",
                "sender_name": "User One",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test Subject",
                "draft_mentions": [],
            }
        },
        {
            "_id": "chunk-2",
            "chunk_id": "chunk-2",
            "message_id": "<msg1@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 1,
            "text": "This is chunk 2 text.",
            "token_count": 10,
            "metadata": {
                "sender": "user1@example.com",
                "sender_name": "User One",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test Subject",
                "draft_mentions": [],
            }
        },
        {
            "_id": "chunk-3",
            "chunk_id": "chunk-3",
            "message_id": "<msg2@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "text": "This is chunk 3 text.",
            "token_count": 10,
            "metadata": {
                "sender": "user2@example.com",
                "sender_name": "User Two",
                "date": "2023-10-15T13:00:00Z",
                "subject": "Re: Test Subject",
                "draft_mentions": ["draft-ietf-quic-transport-34"],
            }
        },
    ]
    
    mock_document_store.query_documents.return_value = chunks
    
    event_data = {
        "chunk_ids": chunk_ids,
        "chunk_count": 3,
    }
    
    # Process chunks
    embedding_service.process_chunks(event_data)
    
    # Verify document store was queried
    mock_document_store.query_documents.assert_called_once_with(
        collection="chunks",
        filter_dict={
            "chunk_id": {"$in": chunk_ids},
            "embedding_generated": False,
        }
    )
    
    # Verify embeddings were generated for each chunk
    assert mock_embedding_provider.embed.call_count == 3
    
    # Verify embeddings were stored
    mock_vector_store.add_embeddings.assert_called_once()
    call_args = mock_vector_store.add_embeddings.call_args
    stored_ids = call_args[0][0]
    stored_vectors = call_args[0][1]
    stored_metadata = call_args[0][2]
    
    assert len(stored_ids) == 3
    assert stored_ids == chunk_ids
    assert len(stored_vectors) == 3
    assert len(stored_metadata) == 3
    
    # Verify metadata structure
    assert stored_metadata[0]["chunk_id"] == "chunk-1"
    assert stored_metadata[0]["message_id"] == "<msg1@example.com>"
    assert stored_metadata[0]["text"] == "This is chunk 1 text."
    assert stored_metadata[0]["embedding_model"] == "all-MiniLM-L6-v2"
    assert stored_metadata[0]["embedding_backend"] == "sentencetransformers"
    
    # Verify chunk status was updated
    assert mock_document_store.update_document.call_count == 3
    # Verify the update calls were made for each chunk
    update_calls = mock_document_store.update_document.call_args_list
    updated_chunk_ids = [call[1]["doc_id"] for call in update_calls]
    assert set(updated_chunk_ids) == set(chunk_ids)
    
    # Verify success event was published
    mock_publisher.publish.assert_called_once()
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["exchange"] == "copilot.events"
    assert publish_call[1]["routing_key"] == "embeddings.generated"
    
    event = publish_call[1]["event"]
    assert event["event_type"] == "EmbeddingsGenerated"
    assert event["data"]["chunk_ids"] == chunk_ids
    assert event["data"]["embedding_count"] == 3
    assert event["data"]["embedding_model"] == "all-MiniLM-L6-v2"
    assert event["data"]["embedding_backend"] == "sentencetransformers"
    assert event["data"]["embedding_dimension"] == 384
    assert event["data"]["vector_store_updated"] is True
    
    # Verify stats were updated
    assert embedding_service.chunks_processed == 3
    assert embedding_service.embeddings_generated_total == 3


def test_process_chunks_no_chunks_found(embedding_service, mock_document_store, mock_publisher):
    """When no chunks are found, service should skip without publishing failure."""
    chunk_ids = ["chunk-1", "chunk-2"]
    mock_document_store.query_documents.return_value = []

    event_data = {
        "chunk_ids": chunk_ids,
    }

    embedding_service.process_chunks(event_data)

    # No failure event should be published for already-embedded or missing chunks
    mock_publisher.publish.assert_not_called()


def test_process_chunks_empty_chunk_ids(embedding_service, mock_document_store):
    """Test handling when event has no chunk IDs."""
    event_data = {
        "chunk_ids": [],
    }
    
    embedding_service.process_chunks(event_data)
    
    # Should return early without querying database
    mock_document_store.query_documents.assert_not_called()


def test_process_chunks_missing_mongo_id_raises_error(embedding_service, mock_document_store, mock_publisher):
    """Test that chunks without MongoDB _id raise ValueError to prevent inconsistent state."""
    chunk_ids = ["chunk-1", "chunk-2"]
    chunks = [
        {
            "chunk_id": "chunk-1",
            "_id": "mongo-id-1",
            "text": "Has ID",
            "message_id": "<msg@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "token_count": 5,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            }
        },
        {
            "chunk_id": "chunk-2",
            # Missing _id field
            "text": "No ID",
            "message_id": "<msg@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 1,
            "token_count": 5,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            }
        }
    ]
    
    mock_document_store.query_documents.return_value = chunks
    
    event_data = {
        "chunk_ids": chunk_ids,
    }
    
    # Should raise ValueError immediately to prevent embeddings without status update
    with pytest.raises(ValueError, match="missing MongoDB _id field"):
        embedding_service.process_chunks(event_data)


def test_process_chunks_retry_on_failure(embedding_service, mock_document_store, mock_vector_store, mock_publisher):
    """Test retry logic on failure."""
    chunk_ids = ["chunk-1"]
    chunks = [
        {
            "_id": "chunk-1",
            "chunk_id": "chunk-1",
            "text": "Test text",
            "message_id": "<msg@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "token_count": 5,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            }
        }
    ]
    
    mock_document_store.query_documents.return_value = chunks
    
    # Make vector store fail on first call, succeed on second
    mock_vector_store.add_embeddings.side_effect = [
        Exception("Vector store error"),
        None,  # Success on retry
    ]
    
    event_data = {
        "chunk_ids": chunk_ids,
    }
    
    # Set lower retry settings for faster test
    embedding_service.max_retries = 3
    embedding_service.retry_backoff_seconds = 0.1
    
    embedding_service.process_chunks(event_data)
    
    # Verify vector store was called twice (initial + 1 retry)
    assert mock_vector_store.add_embeddings.call_count == 2
    
    # Verify success event was published (after retry)
    success_calls = [call for call in mock_publisher.publish.call_args_list if call[1]["routing_key"] == "embeddings.generated"]
    assert len(success_calls) == 1, "Should publish exactly one success event after retry"


def test_process_chunks_max_retries_exceeded(embedding_service, mock_document_store, mock_vector_store, mock_publisher):
    """Test that failure event is published and exception raised after max retries."""
    chunk_ids = ["chunk-1"]
    chunks = [
        {
            "_id": "chunk-1",
            "chunk_id": "chunk-1",
            "text": "Test text",
            "message_id": "<msg@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": 0,
            "token_count": 5,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            }
        }
    ]
    
    mock_document_store.query_documents.return_value = chunks
    mock_vector_store.add_embeddings.side_effect = Exception("Persistent error")
    
    event_data = {
        "chunk_ids": chunk_ids,
    }
    
    # Set lower retry settings for faster test
    embedding_service.max_retries = 2
    embedding_service.retry_backoff_seconds = 0.1
    
    # Should raise exception after max retries to trigger message requeue
    with pytest.raises(Exception, match="Persistent error"):
        embedding_service.process_chunks(event_data)
    
    # Verify vector store was called max_retries times
    assert mock_vector_store.add_embeddings.call_count == 2
    
    # Verify failure event was published before re-raising
    mock_publisher.publish.assert_called()
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "embedding.generation.failed"
    
    event = publish_call[1]["event"]
    assert event["event_type"] == "EmbeddingGenerationFailed"
    assert event["data"]["chunk_ids"] == chunk_ids
    assert event["data"]["retry_count"] == 2


def test_get_stats(embedding_service):
    """Test getting service statistics."""
    embedding_service.chunks_processed = 10
    embedding_service.embeddings_generated_total = 10
    embedding_service.last_processing_time = 5.5
    
    stats = embedding_service.get_stats()
    
    assert stats["chunks_processed"] == 10
    assert stats["embeddings_generated_total"] == 10
    assert stats["last_processing_time_seconds"] == 5.5
    assert stats["embedding_model"] == "all-MiniLM-L6-v2"
    assert stats["embedding_backend"] == "sentencetransformers"
    assert stats["embedding_dimension"] == 384
    assert stats["batch_size"] == 32
    assert "uptime_seconds" in stats


def test_batch_processing(embedding_service, mock_document_store, mock_vector_store, mock_embedding_provider):
    """Test that chunks are processed in batches."""
    # Create more chunks than batch size
    chunk_ids = [f"chunk-{i}" for i in range(100)]
    chunks = [
        {
            "_id": f"chunk-{i}",
            "chunk_id": f"chunk-{i}",
            "text": f"Text for chunk {i}",
            "message_id": f"<msg{i}@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "chunk_index": i,
            "token_count": 10,
            "metadata": {
                "sender": "user@example.com",
                "sender_name": "User",
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test",
                "draft_mentions": [],
            }
        }
        for i in range(100)
    ]
    
    mock_document_store.query_documents.return_value = chunks
    embedding_service.batch_size = 32
    
    event_data = {
        "chunk_ids": chunk_ids,
    }
    
    embedding_service.process_chunks(event_data)
    
    # Verify all chunks were processed
    assert mock_embedding_provider.embed.call_count == 100
    
    # Verify vector store was called multiple times (once per batch)
    # 100 chunks / 32 batch_size = 4 batches (32, 32, 32, 4)
    assert mock_vector_store.add_embeddings.call_count == 4


def test_handle_chunks_prepared_raises_on_missing_chunk_ids(embedding_service):
    """Test that event handler raises exception when chunk_ids field is missing."""
    event = {
        "event_type": "ChunksPrepared",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "chunk_count": 3,
            # Missing chunk_ids field - should trigger re-raise
        }
    }
    
    # Service should raise an exception for missing chunk_ids field
    with pytest.raises(ValueError):
        embedding_service._handle_chunks_prepared(event)


def test_handle_chunks_prepared_raises_on_invalid_chunk_ids_type(embedding_service):
    """Test that event handler raises exception when chunk_ids is not a list."""
    event = {
        "event_type": "ChunksPrepared",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "chunk_ids": "not-an-array",  # Should be list, not string
            "chunk_count": 1,
        }
    }
    
    # Service should raise an exception for invalid type
    with pytest.raises(TypeError):
        embedding_service._handle_chunks_prepared(event)


def test_event_handler_raises_on_missing_data_field(embedding_service):
    """Test that event handler raises when data field is missing."""
    event = {
        "event_type": "ChunksPrepared",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        # Missing data field
    }
    
    # Event handler should re-raise to trigger message requeue
    with pytest.raises(Exception):
        embedding_service._handle_chunks_prepared(event)


def test_event_handler_raises_on_process_chunks_error(embedding_service, mock_document_store, mock_publisher):
    """Test that event handler re-raises exceptions from process_chunks."""
    # Mock document store to raise an error
    mock_document_store.query_documents.side_effect = Exception("Database connection lost")
    
    event = {
        "event_type": "ChunksPrepared",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "chunk_ids": ["chunk-1"],
            "chunk_count": 1,
        }
    }
    
    # Set lower retry count for faster test
    embedding_service.max_retries = 1
    embedding_service.retry_backoff_seconds = 0.01
    
    # Event handler should re-raise the exception after max retries
    with pytest.raises(Exception, match="Database connection lost"):
        embedding_service._handle_chunks_prepared(event)


def test_publish_embeddings_generated_raises_on_publish_error(embedding_service, mock_publisher):
    """Test that _publish_embeddings_generated raises exception on publish errors."""
    # Setup mock to raise an exception
    mock_publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        embedding_service._publish_embeddings_generated(
            chunk_ids=["chunk-1"],
            embedding_count=1,
            avg_generation_time_ms=100.0
        )


def test_publish_embedding_failed_raises_on_publish_error(embedding_service, mock_publisher):
    """Test that _publish_embedding_failed raises exception on publish errors."""
    # Setup mock to raise an exception
    mock_publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        embedding_service._publish_embedding_failed(
            chunk_ids=["chunk-1"],
            error_message="Test error",
            error_type="TestError",
            retry_count=0
        )


def test_publish_embeddings_generated_false_return(embedding_service, mock_publisher):
    """Publisher raising exception should propagate for EmbeddingsGenerated."""
    mock_publisher.publish.side_effect = Exception("Publish failed")

    with pytest.raises(Exception):
        embedding_service._publish_embeddings_generated([
            "chunk-1"
        ], 1, 10.0)

    mock_publisher.publish.assert_called_once()


def test_publish_embedding_failed_false_return(embedding_service, mock_publisher):
    """Publisher raising exception should propagate for EmbeddingGenerationFailed."""
    mock_publisher.publish.side_effect = Exception("Publish failed")

    with pytest.raises(Exception):
        embedding_service._publish_embedding_failed([
            "chunk-1"
        ], "boom", "TestError", 0)

    mock_publisher.publish.assert_called_once()
