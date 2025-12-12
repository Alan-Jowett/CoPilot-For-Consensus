# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the chunking service."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from app.service import ChunkingService
from copilot_chunking import TokenWindowChunker


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.insert_document = Mock(return_value="chunk_123")
    store.query_documents = Mock(return_value=[])
    return store


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
def mock_chunker():
    """Create a mock chunker."""
    return TokenWindowChunker(chunk_size=384, overlap=50)


@pytest.fixture
def chunking_service(mock_document_store, mock_publisher, mock_subscriber, mock_chunker):
    """Create a chunking service instance."""
    return ChunkingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )


def test_service_initialization(chunking_service):
    """Test that the service initializes correctly."""
    assert chunking_service.document_store is not None
    assert chunking_service.publisher is not None
    assert chunking_service.subscriber is not None
    assert chunking_service.chunker is not None
    assert chunking_service.messages_processed == 0
    assert chunking_service.chunks_created_total == 0


def test_service_start(chunking_service, mock_subscriber):
    """Test that the service subscribes to events on start."""
    chunking_service.start()
    
    # Verify subscription was called
    mock_subscriber.subscribe.assert_called_once()
    call_args = mock_subscriber.subscribe.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "json.parsed"


def test_chunk_message_success(chunking_service, mock_document_store):
    """Test chunking a message successfully."""
    message = {
        "message_id": "<test@example.com>",
        "thread_id": "<thread@example.com>",
        "archive_id": "archive-123",
        "body_normalized": "This is a test message with some content. " * 100,
        "from": {"email": "user@example.com", "name": "Test User"},
        "date": "2023-10-15T12:00:00Z",
        "subject": "Test Subject",
        "draft_mentions": [],
    }
    
    chunks = chunking_service._chunk_message(message)
    
    # Verify chunks were created
    assert len(chunks) > 0
    
    # Verify chunk structure
    chunk = chunks[0]
    assert "chunk_id" in chunk
    assert chunk["message_id"] == "<test@example.com>"
    assert chunk["thread_id"] == "<thread@example.com>"
    assert chunk["archive_id"] == "archive-123"
    assert chunk["chunk_index"] == 0
    assert "text" in chunk
    assert "token_count" in chunk
    assert chunk["embedding_generated"] is False
    assert "metadata" in chunk
    assert chunk["metadata"]["sender"] == "user@example.com"


def test_chunk_message_empty_body(chunking_service):
    """Test chunking a message with empty body."""
    message = {
        "message_id": "<test@example.com>",
        "body_normalized": "",
        "from": {"email": "user@example.com", "name": "Test User"},
        "date": "2023-10-15T12:00:00Z",
        "subject": "Test Subject",
    }
    
    chunks = chunking_service._chunk_message(message)
    
    # Empty messages should return no chunks
    assert len(chunks) == 0


def test_chunk_message_whitespace_only(chunking_service):
    """Test chunking a message with only whitespace."""
    message = {
        "message_id": "<test@example.com>",
        "body_normalized": "   \n\t  ",
        "from": {"email": "user@example.com", "name": "Test User"},
        "date": "2023-10-15T12:00:00Z",
        "subject": "Test Subject",
    }
    
    chunks = chunking_service._chunk_message(message)
    
    # Whitespace-only messages should return no chunks
    assert len(chunks) == 0


def test_process_messages_success(chunking_service, mock_document_store, mock_publisher):
    """Test processing messages successfully."""
    # Setup mock responses
    messages = [
        {
            "message_id": "<test1@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "body_normalized": "This is test message one. " * 50,
            "from": {"email": "user1@example.com", "name": "User One"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject 1",
            "draft_mentions": [],
        },
        {
            "message_id": "<test2@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "archive-123",
            "body_normalized": "This is test message two. " * 50,
            "from": {"email": "user2@example.com", "name": "User Two"},
            "date": "2023-10-15T13:00:00Z",
            "subject": "Test Subject 2",
            "draft_mentions": [],
        },
    ]
    
    mock_document_store.query_documents.return_value = messages
    
    event_data = {
        "archive_id": "archive-123",
        "parsed_message_ids": ["<test1@example.com>", "<test2@example.com>"],
    }
    
    chunking_service.process_messages(event_data)
    
    # Verify messages were queried
    mock_document_store.query_documents.assert_called_once()
    
    # Verify chunks were stored
    assert mock_document_store.insert_document.call_count > 0
    
    # Verify ChunksPrepared event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["routing_key"] == "chunks.prepared"
    
    # Verify stats were updated
    assert chunking_service.messages_processed == 2
    assert chunking_service.chunks_created_total > 0


def test_process_messages_no_messages_found(chunking_service, mock_document_store, mock_publisher):
    """Test processing when no messages are found in database."""
    mock_document_store.query_documents.return_value = []
    
    event_data = {
        "archive_id": "archive-123",
        "parsed_message_ids": ["<test@example.com>"],
    }
    
    chunking_service.process_messages(event_data)
    
    # Verify ChunkingFailed event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["routing_key"] == "chunking.failed"


def test_process_messages_empty_list(chunking_service, mock_document_store, mock_publisher):
    """Test processing with empty message list."""
    event_data = {
        "archive_id": "archive-123",
        "parsed_message_ids": [],
    }
    
    chunking_service.process_messages(event_data)
    
    # No queries or publishes should happen
    mock_document_store.query_documents.assert_not_called()
    mock_publisher.publish.assert_not_called()


def test_get_stats(chunking_service):
    """Test getting service statistics."""
    chunking_service.messages_processed = 10
    chunking_service.chunks_created_total = 25
    chunking_service.last_processing_time = 2.5
    
    stats = chunking_service.get_stats()
    
    assert stats["messages_processed"] == 10
    assert stats["chunks_created_total"] == 25
    assert stats["last_processing_time_seconds"] == 2.5


def test_publish_chunks_prepared(chunking_service, mock_publisher):
    """Test publishing ChunksPrepared event."""
    chunking_service._publish_chunks_prepared(
        message_ids=["<msg1@example.com>", "<msg2@example.com>"],
        chunk_ids=["chunk1", "chunk2", "chunk3"],
        chunk_count=3,
        avg_chunk_size=350.5,
    )
    
    # Verify event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "chunks.prepared"
    
    message = call_args[1]["message"]
    assert message["event_type"] == "ChunksPrepared"
    assert message["data"]["chunk_count"] == 3
    assert len(message["data"]["chunk_ids"]) == 3
    assert message["data"]["chunks_ready"] is True


def test_publish_chunking_failed(chunking_service, mock_publisher):
    """Test publishing ChunkingFailed event."""
    chunking_service._publish_chunking_failed(
        message_ids=["<msg1@example.com>"],
        error_message="Test error",
        error_type="TestError",
        retry_count=0,
    )
    
    # Verify event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "chunking.failed"
    
    message = call_args[1]["message"]
    assert message["event_type"] == "ChunkingFailed"
    assert message["data"]["error_message"] == "Test error"
    assert message["data"]["error_type"] == "TestError"
