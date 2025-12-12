# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the orchestration service."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from app.service import OrchestrationService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    store.query = Mock(return_value=[])
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
def orchestration_service(mock_document_store, mock_vector_store, mock_publisher, mock_subscriber):
    """Create an orchestration service instance."""
    return OrchestrationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
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
    assert orchestration_service.vector_store is not None
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
    assert "chunk_id" in call_args[0][1]


def test_retrieve_context(orchestration_service, mock_document_store):
    """Test retrieving context for a thread."""
    thread_id = "<thread-1@example.com>"
    
    # Setup mock data
    chunks = [
        {
            "chunk_id": "chunk-1",
            "message_id": "<msg-1@example.com>",
            "thread_id": thread_id,
            "text": "Test chunk 1",
            "embedding_generated": True,
        },
        {
            "chunk_id": "chunk-2",
            "message_id": "<msg-2@example.com>",
            "thread_id": thread_id,
            "text": "Test chunk 2",
            "embedding_generated": True,
        },
    ]
    
    messages = [
        {
            "message_id": "<msg-1@example.com>",
            "subject": "Test Subject",
            "from": {"name": "User 1", "email": "user1@example.com"},
            "date": "2023-10-15T12:00:00Z",
            "draft_mentions": [],
        },
        {
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
        {"chunk_id": "chunk-1", "thread_id": "<thread-1@example.com>", "message_id": "<msg-1@example.com>", "embedding_generated": True},
        {"chunk_id": "chunk-2", "thread_id": "<thread-1@example.com>", "message_id": "<msg-1@example.com>", "embedding_generated": True},
    ]
    
    messages = [
        {"message_id": "<msg-1@example.com>", "subject": "Test", "from": {"email": "user@example.com"}, "date": "2023-10-15T12:00:00Z", "draft_mentions": []},
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
