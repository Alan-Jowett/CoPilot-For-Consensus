# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the chunking service."""

import pytest
from unittest.mock import Mock

from app.service import ChunkingService
from copilot_chunking import TokenWindowChunker
from .test_helpers import assert_valid_event_schema


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
        "_id": "abc123def4567890",
        "message_id": "<test@example.com>",
        "thread_id": "fedcba9876543210",
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
    assert "_id" in chunk
    assert chunk["message_id"] == "<test@example.com>"
    assert chunk["thread_id"] == "fedcba9876543210"
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
            "_id": "abc123def4567890",
            "message_id": "<test1@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "body_normalized": "This is test message one. " * 50,
            "from": {"email": "user1@example.com", "name": "User One"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject 1",
            "draft_mentions": [],
        },
        {
            "_id": "fedcba9876543210",
            "message_id": "<test2@example.com>",
            "thread_id": "5555666677778888",
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
        "message_doc_ids": ["abc123def4567890", "fedcba9876543210"],
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
        "message_doc_ids": ["abc123def4567890"],
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
        "message_doc_ids": [],
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
        message_doc_ids=["abc123def4567890", "fedcba9876543210"],
        chunk_ids=["aaaa1111bbbb2222", "cccc3333dddd4444", "eeee5555ffff6666"],
        chunk_count=3,
        avg_chunk_size=350.5,
    )
    
    # Verify event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "chunks.prepared"
    
    event = call_args[1]["event"]
    assert event["event_type"] == "ChunksPrepared"
    assert event["data"]["chunk_count"] == 3
    assert len(event["data"]["chunk_ids"]) == 3
    assert event["data"]["chunks_ready"] is True
    
    # Validate event against JSON schema
    assert_valid_event_schema(event)


def test_publish_chunking_failed(chunking_service, mock_publisher):
    """Test publishing ChunkingFailed event."""
    chunking_service._publish_chunking_failed(
        message_doc_ids=["abc123def4567890"],
        error_message="Test error",
        error_type="TestError",
        retry_count=0,
    )
    
    # Verify event was published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "chunking.failed"
    
    event = call_args[1]["event"]
    assert event["event_type"] == "ChunkingFailed"
    assert event["data"]["error_message"] == "Test error"
    assert event["data"]["error_type"] == "TestError"
    
    # Validate event against JSON schema
    assert_valid_event_schema(event)


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_schema_validation_chunks_prepared():
    """Test that ChunksPrepared events validate against schema."""
    mock_store = Mock()
    mock_store.insert_document = Mock(return_value="chunk_123")
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    service._publish_chunks_prepared(
        message_doc_ids=["abc123def4567890"],
        chunk_ids=["aaaa1111bbbb2222", "cccc3333dddd4444"],
        chunk_count=2,
        avg_chunk_size=100.0,
    )
    
    call_args = mock_publisher.publish.call_args
    event = call_args[1]["event"]
    
    # Should pass schema validation
    assert_valid_event_schema(event)


def test_schema_validation_chunking_failed():
    """Test that ChunkingFailed events validate against schema."""
    mock_store = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    service._publish_chunking_failed(
        message_doc_ids=["abc123def4567890"],
        error_message="Test error",
        error_type="ValidationError",
        retry_count=1,
    )
    
    call_args = mock_publisher.publish.call_args
    event = call_args[1]["event"]
    
    # Should pass schema validation
    assert_valid_event_schema(event)


# ============================================================================
# Message Consumption Tests
# ============================================================================


def test_consume_json_parsed_event():
    """Test consuming a JSONParsed event."""
    mock_store = Mock()
    mock_store.insert_document = Mock(return_value="chunk_123")
    mock_store.query_documents = Mock(return_value=[])
    
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    # Simulate receiving a JSONParsed event
    event = {
        "event_type": "JSONParsed",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "a1b2c3d4e5f67890",
            "message_doc_ids": ["abc123def4567890"],
            "thread_ids": ["1111222233334444"],
            "message_count": 1,
            "thread_count": 1,
            "parsing_duration_seconds": 1.5,
        }
    }
    
    # Validate incoming event
    assert_valid_event_schema(event)
    
    # Process the event - would normally be called by subscriber
    # For now, just verify the event structure is correct
    assert event["data"]["archive_id"] == "a1b2c3d4e5f67890"
    assert len(event["data"]["message_doc_ids"]) == 1


def test_consume_json_parsed_multiple_messages():
    """Test consuming JSONParsed event with multiple messages."""
    event = {
        "event_type": "JSONParsed",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "a1b2c3d4e5f67890",
            "message_doc_ids": [
                "abc123def4567890",
                "fedcba9876543210",
                "111122223333444f",
            ],
            "thread_ids": ["1111222233334444"],
            "message_count": 3,
            "thread_count": 1,
            "parsing_duration_seconds": 2.5,
        }
    }
    
    # Validate incoming event
    assert_valid_event_schema(event)
    assert event["data"]["message_count"] == 3


# ============================================================================
# Invalid Message Handling Tests
# ============================================================================


def test_handle_malformed_event_missing_data():
    """Test handling event with missing data field."""
    mock_store = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    # Event missing 'data' field
    event = {
        "event_type": "JSONParsed",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
    }
    
    # Service should raise an exception for missing data field
    with pytest.raises((KeyError, AttributeError, ValueError)):
        service._handle_json_parsed(event)


def test_handle_event_with_invalid_message_doc_ids_type():
    """Test handling event with invalid message_doc_ids type."""
    mock_store = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    # message_doc_ids should be array but is string
    event = {
        "event_type": "JSONParsed",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "archive-123",
            "message_doc_ids": "not-an-array",
            "thread_ids": ["1111222233334444"],
            "message_count": 1,
            "thread_count": 1,
            "parsing_duration_seconds": 1.0,
        }
    }
    
    # Service should raise an exception for invalid type
    with pytest.raises((TypeError, AttributeError)):
        service._handle_json_parsed(event)


def test_publish_chunks_prepared_raises_on_publish_error(chunking_service, mock_publisher):
    """Test that _publish_chunks_prepared raises exception on publish errors."""
    # Setup mock to raise an exception
    mock_publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        chunking_service._publish_chunks_prepared(
            message_doc_ids=["abc123def4567890"],
            chunk_ids=["aaaa1111bbbb2222"],
            chunk_count=1,
            avg_chunk_size=100.0
        )


def test_publish_chunking_failed_raises_on_publish_error(chunking_service, mock_publisher):
    """Test that _publish_chunking_failed raises exception on publish errors."""
    # Setup mock to raise an exception
    mock_publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        chunking_service._publish_chunking_failed(
            message_doc_ids=["abc123def4567890"],
            error_message="Test error",
            error_type="TestError",
            retry_count=0
        )


def test_event_handler_raises_on_errors(chunking_service):
    """Test that event handler re-raises exceptions to trigger message requeue."""
    # Create a mock that raises during event parsing (before process_messages)
    from copilot_events import JSONParsedEvent
    
    # This will cause the event handler to fail during event parsing
    event = {
        "data": None  # This will cause an error when accessing event data
    }
    
    # Event handler should re-raise to trigger message requeue for failures
    with pytest.raises(Exception):
        chunking_service._handle_json_parsed(event)


def test_query_documents_uses_filter_dict_parameter(chunking_service, mock_document_store):
    """Test that query_documents is called with filter_dict parameter, not query."""
    # Setup mock
    mock_document_store.query_documents.return_value = []
    
    event_data = {
        "archive_id": "archive-123",
        "message_doc_ids": ["abc123def4567890"],
    }
    
    # Process messages
    chunking_service.process_messages(event_data)
    
    # Verify query_documents was called with filter_dict parameter
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    
    # Check that filter_dict is in kwargs (positional args would be in [0])
    assert "filter_dict" in call_args[1], "query_documents must use 'filter_dict' parameter"
    assert "query" not in call_args[1], "query_documents should not use deprecated 'query' parameter"


def test_publisher_uses_event_parameter(chunking_service, mock_publisher):
    """Test that publisher.publish is called with event parameter, not message."""
    # Trigger a chunks prepared event
    chunking_service._publish_chunks_prepared(
        message_doc_ids=["abc123def4567890"],
        chunk_ids=["aaaa1111bbbb2222"],
        chunk_count=1,
        avg_chunk_size=100.0
    )
    
    # Verify publish was called with event parameter
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    # Check that event is in kwargs
    assert "event" in call_args[1], "publisher.publish must use 'event' parameter"
    assert "message" not in call_args[1], "publisher.publish should not use deprecated 'message' parameter"


def test_idempotent_chunk_insertion(chunking_service, mock_document_store, mock_publisher):
    """Test that duplicate chunk insertions are handled gracefully (idempotency)."""
    from pymongo.errors import DuplicateKeyError
    
    # Setup mock to simulate duplicate on second insert
    messages = [
        {
            "_id": "abc123def4567890",
            "message_id": "<test@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "body_normalized": "This is a test message. " * 50,
            "from": {"email": "user@example.com", "name": "Test User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject",
            "draft_mentions": [],
        }
    ]
    
    mock_document_store.query_documents.return_value = messages
    
    # First insert succeeds, second raises DuplicateKeyError
    insert_count = [0]
    
    def insert_side_effect(collection, document):
        insert_count[0] += 1
        if insert_count[0] == 2:
            raise DuplicateKeyError("E11000 duplicate key error")
        return f"chunk_{insert_count[0]}"
    
    mock_document_store.insert_document.side_effect = insert_side_effect
    
    event_data = {
        "archive_id": "archive-123",
        "message_doc_ids": ["abc123def4567890"],
    }
    
    # Process should succeed despite duplicate
    chunking_service.process_messages(event_data)
    
    # Verify ChunksPrepared event was still published
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["routing_key"] == "chunks.prepared"
    
    # Stats should be updated
    assert chunking_service.messages_processed == 1
    assert chunking_service.chunks_created_total > 0


def test_metrics_collector_uses_observe_for_histograms():
    """Test that metrics collector uses observe() method for duration and size metrics."""
    mock_store = Mock()
    mock_store.insert_document = Mock(return_value="chunk_123")
    mock_store.query_documents = Mock(return_value=[
        {
            "_id": "abc123def4567890",
            "message_id": "<test@example.com>",
            "thread_id": "1111222233334444",
            "archive_id": "archive-123",
            "body_normalized": "This is a test message. " * 50,
            "from": {"email": "user@example.com", "name": "Test User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject",
            "draft_mentions": [],
        }
    ])
    
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    mock_metrics = Mock()
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
        metrics_collector=mock_metrics,
    )
    
    event_data = {
        "archive_id": "archive-123",
        "message_doc_ids": ["abc123def4567890"],
    }
    
    service.process_messages(event_data)
    
    # Verify observe was called for duration (not histogram)
    observe_calls = [call for call in mock_metrics.observe.call_args_list]
    assert len(observe_calls) >= 1, "observe() should be called for metrics"
    
    # Check that duration metric was recorded
    duration_calls = [call for call in observe_calls 
                     if call[0][0] == "chunking_duration_seconds"]
    assert len(duration_calls) == 1, "chunking_duration_seconds should be recorded once"
    
    # Verify histogram method was NOT called (it doesn't exist in the API)
    method_names = [call[0] for call in mock_metrics.method_calls]
    assert 'histogram' not in method_names, \
        "histogram() method should not be used (use observe() instead)"


def test_requeue_incomplete_messages_with_aggregation_support():
    """Test that startup requeue works when document store supports aggregation."""
    from copilot_storage import InMemoryDocumentStore
    
    # Use real InMemoryDocumentStore which now supports aggregation
    store = InMemoryDocumentStore()
    store.connect()
    
    # Insert test data: 2 messages, only 1 has chunks
    store.insert_document('messages', {
        'message_key': 'msg1',
        'archive_id': 1,
        'body_normalized': 'test message 1'
    })
    store.insert_document('messages', {
        'message_key': 'msg2',
        'archive_id': 1,
        'body_normalized': 'test message 2'
    })
    store.insert_document('chunks', {
        'message_key': 'msg1',
        'chunk_id': 'chunk1'
    })
    
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    # Call requeue - should use aggregation to find msg2
    service._requeue_incomplete_messages()
    
    # Verify that a requeue event was published for msg2
    assert mock_publisher.publish.call_count == 1
    call_args = mock_publisher.publish.call_args
    
    # Verify the published event contains msg2
    event_data = call_args[1]['data']
    assert event_data['archive_id'] == 1
    assert 'msg2' in event_data['message_keys']
    assert 'msg1' not in event_data['message_keys']


def test_requeue_skips_when_aggregation_not_supported():
    """Test that startup requeue is skipped gracefully when aggregation not supported."""
    # Create a mock store without aggregate_documents method
    mock_store = Mock(spec=['connect', 'insert_document', 'query_documents'])
    
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_chunker = TokenWindowChunker(chunk_size=384, overlap=50)
    
    service = ChunkingService(
        document_store=mock_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
    )
    
    # Call requeue - should detect missing method and skip gracefully
    service._requeue_incomplete_messages()
    
    # Verify no events were published (requeue was skipped)
    assert mock_publisher.publish.call_count == 0

