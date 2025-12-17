# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the orchestration service."""

import pytest
from unittest.mock import Mock

from app.service import OrchestrationService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    return store


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
def orchestration_service(mock_document_store, mock_publisher, mock_subscriber):
    """Create an orchestration service instance."""
    return OrchestrationService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        top_k=12,
        context_window_tokens=3000,
        llm_backend="ollama",
        llm_model="mistral",
    )


def test_service_initialization(orchestration_service):
    """Test that the service initializes correctly."""
    assert orchestration_service.document_store is not None
    assert orchestration_service.publisher is not None
    assert orchestration_service.subscriber is not None
    assert orchestration_service.events_processed == 0
    assert orchestration_service.threads_orchestrated == 0
    assert orchestration_service.top_k == 12
    assert orchestration_service.llm_backend == "ollama"


def test_service_start(orchestration_service, mock_subscriber):
    """Test that the service subscribes to events on start."""
    orchestration_service.start()
    
    # Verify subscription was called
    mock_subscriber.subscribe.assert_called_once()
    call_args = mock_subscriber.subscribe.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "embeddings.generated"


def test_resolve_threads(orchestration_service, mock_document_store):
    """Test resolving thread IDs from chunk IDs."""
    # Setup mock data
    chunk_ids = ["chunk-1", "chunk-2", "chunk-3"]
    chunks = [
        {"chunk_id": "chunk-1", "thread_id": "<thread-1@example.com>"},
        {"chunk_id": "chunk-2", "thread_id": "<thread-1@example.com>"},
        {"chunk_id": "chunk-3", "thread_id": "<thread-2@example.com>"},
    ]
    mock_document_store.query_documents = Mock(return_value=chunks)
    
    # Resolve threads
    thread_ids = orchestration_service._resolve_threads(chunk_ids)
    
    # Verify results
    assert len(thread_ids) == 2
    assert "<thread-1@example.com>" in thread_ids
    assert "<thread-2@example.com>" in thread_ids
    
    # Verify document store was called correctly
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[0][0] == "chunks"
    assert "_id" in call_args[0][1]


def test_retrieve_context(orchestration_service, mock_document_store):
    """Test retrieving context for a thread."""
    thread_id = "<thread-1@example.com>"
    
    # Setup mock data
    chunks = [
        {
            "_id": "aaaa1111bbbb2222",
            "message_doc_id": "abc123def4567890",
            "message_id": "<msg-1@example.com>",
            "thread_id": thread_id,
            "text": "Test chunk 1",
            "embedding_generated": True,
        },
        {
            "_id": "cccc3333dddd4444",
            "message_doc_id": "fedcba9876543210",
            "message_id": "<msg-2@example.com>",
            "thread_id": thread_id,
            "text": "Test chunk 2",
            "embedding_generated": True,
        },
    ]
    
    messages = [
        {
            "_id": "abc123def4567890",
            "message_id": "<msg-1@example.com>",
            "subject": "Test Subject",
            "from": {"name": "User 1", "email": "user1@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        },
        {
            "_id": "fedcba9876543210",
            "message_id": "<msg-2@example.com>",
            "subject": "Re: Test Subject",
            "from": {"name": "User 2", "email": "user2@example.com"},
            "date": "2023-10-15T13:00:00Z",
            "draft_mentions": ["draft-ietf-quic-transport-34"],
        },
    ]
    
    # Mock query_documents to return different results based on collection
    def mock_query(collection, query, **kwargs):
        if collection == "chunks":
            return chunks
        elif collection == "messages":
            # Expect filter on _id $in
            return messages
        return []
    
    mock_document_store.query_documents = Mock(side_effect=mock_query)
    
    # Retrieve context
    context = orchestration_service._retrieve_context(thread_id)
    
    # Verify results
    assert context["thread_id"] == thread_id
    assert context["chunk_count"] == 2
    assert len(context["chunks"]) == 2
    assert len(context["messages"]) == 2
    assert "retrieved_at" in context


def test_publish_summarization_requested(orchestration_service, mock_publisher):
    """Test publishing SummarizationRequested event."""
    thread_ids = ["<thread-1@example.com>"]
    context = {
        "thread_id": "<thread-1@example.com>",
        "chunk_count": 5,
        "messages": [{"message_id": "<msg-1@example.com>"}],
    }
    
    orchestration_service._publish_summarization_requested(thread_ids, context)
    
    # Verify publisher was called
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "summarization.requested"
    
    # Verify event data
    event = call_args[1]["event"]
    assert event["event_type"] == "SummarizationRequested"
    assert event["data"]["thread_ids"] == thread_ids
    assert event["data"]["top_k"] == 12
    assert event["data"]["llm_backend"] == "ollama"


def test_publish_orchestration_failed(orchestration_service, mock_publisher):
    """Test publishing OrchestrationFailed event."""
    thread_ids = ["<thread-1@example.com>"]
    error_message = "Test error"
    error_type = "TestError"
    
    orchestration_service._publish_orchestration_failed(thread_ids, error_message, error_type)
    
    # Verify publisher was called
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "orchestration.failed"
    
    # Verify event data
    event = call_args[1]["event"]
    assert event["event_type"] == "OrchestrationFailed"
    assert event["data"]["thread_ids"] == thread_ids
    assert event["data"]["error_message"] == error_message
    assert event["data"]["error_type"] == error_type


def test_publish_summarization_requested_publish_failure(orchestration_service, mock_publisher):
    """Publishing SummarizationRequested should raise when publisher raises exception."""
    mock_publisher.publish.side_effect = Exception("Publish failed")

    with pytest.raises(Exception):
        orchestration_service._publish_summarization_requested([
            "<thread-1@example.com>"
        ], {
            "thread_id": "<thread-1@example.com>",
            "chunk_count": 1,
            "messages": []
        })

    mock_publisher.publish.assert_called_once()


def test_publish_orchestration_failed_publish_failure(orchestration_service, mock_publisher):
    """Publishing OrchestrationFailed should raise when publisher raises exception."""
    mock_publisher.publish.side_effect = Exception("Publish failed")

    with pytest.raises(Exception):
        orchestration_service._publish_orchestration_failed([
            "<thread-1@example.com>"
        ], "boom", "TestError")

    mock_publisher.publish.assert_called_once()


def test_get_stats(orchestration_service):
    """Test getting service statistics."""
    orchestration_service.events_processed = 10
    orchestration_service.threads_orchestrated = 5
    orchestration_service.failures_count = 1
    orchestration_service.last_processing_time = 1.5
    
    stats = orchestration_service.get_stats()
    
    assert stats["events_processed"] == 10
    assert stats["threads_orchestrated"] == 5
    assert stats["failures_count"] == 1
    assert stats["last_processing_time_seconds"] == 1.5
    assert stats["config"]["top_k"] == 12
    assert stats["config"]["llm_backend"] == "ollama"


def test_handle_embeddings_generated_event(orchestration_service, mock_document_store, mock_publisher):
    """Test handling EmbeddingsGenerated event."""
    # Setup mock data
    event = {
        "event_type": "EmbeddingsGenerated",
        "event_id": "test-event-id",
        "timestamp": "2023-10-15T14:45:00Z",
        "version": "1.0",
        "data": {
            "chunk_ids": ["chunk-1", "chunk-2"],
            "embedding_count": 2,
            "embedding_model": "all-MiniLM-L6-v2",
        }
    }
    
    chunks = [
        {
            "chunk_id": "chunk-1",
            "thread_id": "<thread-1@example.com>",
            "message_id": "<msg-1@example.com>",
            "embedding_generated": True
        },
        {
            "chunk_id": "chunk-2",
            "thread_id": "<thread-1@example.com>",
            "message_id": "<msg-1@example.com>",
            "embedding_generated": True
        },
    ]

    messages = [
        {
            "message_id": "<msg-1@example.com>",
            "subject": "Test",
            "from": {"email": "user@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": []
        },
    ]
    
    # Mock query_documents to return different results
    def mock_query(collection, query, **kwargs):
        if collection == "chunks" and "chunk_id" in query:
            return chunks
        elif collection == "chunks":
            return chunks
        elif collection == "messages":
            return messages
        return []
    
    mock_document_store.query_documents = Mock(side_effect=mock_query)
    
    # Handle event
    orchestration_service._handle_embeddings_generated(event)
    
    # Verify event was processed
    assert orchestration_service.events_processed == 1
    
    # Verify SummarizationRequested was published
    assert mock_publisher.publish.called


def test_resolve_threads_raises_on_database_error(orchestration_service, mock_document_store):
    """Test that _resolve_threads raises exception on database errors."""
    # Setup mock to raise an exception
    mock_document_store.query_documents = Mock(side_effect=Exception("Database connection failed"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="Database connection failed"):
        orchestration_service._resolve_threads(["chunk-1", "chunk-2"])


def test_publish_orchestration_failed_raises_on_publish_error(orchestration_service, mock_publisher):
    """Test that _publish_orchestration_failed raises exception on publish errors."""
    # Setup mock to raise an exception
    mock_publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))
    
    # Verify exception is raised, not swallowed
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        orchestration_service._publish_orchestration_failed(
            thread_ids=["<thread-1@example.com>"],
            error_message="Test error",
            error_type="TestError"
        )


def test_event_handler_raises_on_errors(orchestration_service, mock_document_store):
    """Test that event handler re-raises exceptions to trigger message requeue."""
    # Setup mock to raise an exception during processing
    mock_document_store.query_documents = Mock(side_effect=Exception("Test error"))
    
    event = {
        "data": {
            "chunk_ids": ["chunk-1", "chunk-2"],
            "embedding_count": 2,
        }
    }
    
    # Event handler should re-raise to trigger message requeue for transient failures
    with pytest.raises(Exception, match="Test error"):
        orchestration_service._handle_embeddings_generated(event)
    
    # Verify failure was tracked
    assert orchestration_service.failures_count == 1
    assert orchestration_service.events_processed == 0  # Event not counted as processed


def test_handle_embeddings_generated_raises_on_missing_chunk_ids(orchestration_service):
    """Test that event handler raises exception when chunk_ids field is missing."""
    event = {
        "event_type": "EmbeddingsGenerated",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "embedding_count": 3,
            # Missing chunk_ids field - should trigger re-raise
        }
    }
    
    # Service should raise an exception for missing chunk_ids field
    with pytest.raises(ValueError):
        orchestration_service._handle_embeddings_generated(event)


def test_handle_embeddings_generated_raises_on_invalid_chunk_ids_type(orchestration_service):
    """Test that event handler raises exception when chunk_ids is not a list."""
    event = {
        "event_type": "EmbeddingsGenerated",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "chunk_ids": "not-an-array",  # Should be list, not string
            "embedding_count": 1,
        }
    }
    
    # Service should raise an exception for invalid type
    with pytest.raises(TypeError):
        orchestration_service._handle_embeddings_generated(event)


def test_handle_embeddings_generated_raises_on_missing_data_field(orchestration_service):
    """Test that event handler raises when data field is missing."""
    event = {
        "event_type": "EmbeddingsGenerated",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        # Missing data field
    }
    
    # Event handler should re-raise to trigger message requeue
    with pytest.raises(Exception):
        orchestration_service._handle_embeddings_generated(event)


def test_idempotent_orchestration(
    orchestration_service,
    mock_document_store,
    mock_publisher,
):
    """Test that orchestration allows summary regeneration.
    
    The orchestrator no longer performs idempotency checks, allowing summaries
    to be regenerated when new content arrives or when explicitly requested.
    This test verifies that the orchestrator processes requests even when a
    summary already exists.
    """
    thread_id = "<thread@example.com>"
    chunk_ids = ["chunk-1", "chunk-2"]
    
    # Setup: chunks exist and map to thread
    chunks = [
        {"chunk_id": "chunk-1", "thread_id": thread_id, "embedding_generated": True},
        {"chunk_id": "chunk-2", "thread_id": thread_id, "embedding_generated": True},
    ]
    
    # First call: no existing summary
    call_count = [0]
    def query_side_effect(collection, filter_dict, **kwargs):
        call_count[0] += 1
        if collection == "chunks":
            return chunks
        return []
    
    mock_document_store.query_documents.side_effect = query_side_effect
    
    event_data = {
        "chunk_ids": chunk_ids,
        "embedding_count": 2,
    }
    
    # First processing - should orchestrate
    orchestration_service.process_embeddings(event_data)
    
    # Verify SummarizationRequested was published
    assert mock_publisher.publish.call_count == 1
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["routing_key"] == "summarization.requested"
    
    # Reset mocks
    mock_publisher.publish.reset_mock()
    call_count[0] = 0
    
    # Second call: even if summary exists, should still process (allowing regeneration)
    existing_summary = {
        "summary_id": "summary-123",
        "thread_id": thread_id,
        "summary_type": "thread",
    }
    
    def query_side_effect_with_summary(collection, filter_dict, **kwargs):
        call_count[0] += 1
        if collection == "chunks":
            return chunks
        return []
    
    mock_document_store.query_documents.side_effect = query_side_effect_with_summary
    
    # Second processing - should still orchestrate (regeneration allowed)
    orchestration_service.process_embeddings(event_data)
    
    # Verify SummarizationRequested WAS published again (regeneration allowed)
    assert mock_publisher.publish.call_count == 1
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["routing_key"] == "summarization.requested"

def test_metrics_collector_uses_tags_parameter(mock_document_store, mock_publisher, mock_subscriber):
    """Test that metrics collector calls use tags= parameter, not labels=."""
    mock_metrics = Mock()
    
    service = OrchestrationService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        top_k=12,
        context_window_tokens=3000,
        llm_backend="ollama",
        llm_model="mistral",
        metrics_collector=mock_metrics,
    )
    
    # Test _publish_summarization_requested metrics call
    thread_ids = ["<thread-1@example.com>"]
    context = {
        "thread_id": "<thread-1@example.com>",
        "chunk_count": 5,
        "messages": [{"message_id": "<msg-1@example.com>"}],
    }
    
    service._publish_summarization_requested(thread_ids, context)
    
    # Verify increment was called with tags parameter
    assert mock_metrics.increment.called
    increment_calls = mock_metrics.increment.call_args_list
    
    # Check that first call uses tags= (not labels=)
    first_call_kwargs = increment_calls[0][1] if increment_calls[0][1] else {}
    assert 'tags' in first_call_kwargs, "metrics_collector.increment should use 'tags=' parameter"
    assert 'labels' not in first_call_kwargs, "metrics_collector.increment should NOT use 'labels=' parameter"
    assert first_call_kwargs['tags'] == {"event_type": "summarization_requested", "outcome": "success"}
    
    # Reset mock for next test
    mock_metrics.reset_mock()
    
    # Test _publish_orchestration_failed metrics calls
    service._publish_orchestration_failed(thread_ids, "Test error", "TestError")
    
    # Verify both increment calls use tags parameter
    assert mock_metrics.increment.call_count == 2
    increment_calls = mock_metrics.increment.call_args_list
    
    # First call: orchestration_events_total
    first_call_kwargs = increment_calls[0][1] if increment_calls[0][1] else {}
    assert 'tags' in first_call_kwargs, "First increment call should use 'tags=' parameter"
    assert 'labels' not in first_call_kwargs, "First increment call should NOT use 'labels=' parameter"
    assert first_call_kwargs['tags'] == {"event_type": "orchestration_failed", "outcome": "failure"}
    
    # Second call: orchestration_failures_total
    second_call_kwargs = increment_calls[1][1] if increment_calls[1][1] else {}
    assert 'tags' in second_call_kwargs, "Second increment call should use 'tags=' parameter"
    assert 'labels' not in second_call_kwargs, "Second increment call should NOT use 'labels=' parameter"
    assert second_call_kwargs['tags'] == {"error_type": "TestError"}
