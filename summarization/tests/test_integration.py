# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the summarization service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from app.service import SummarizationService
from copilot_summarization import MockSummarizer, LocalLLMSummarizer
from copilot_storage import InMemoryDocumentStore, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider


@pytest.fixture
def in_memory_document_store():
    """Create an in-memory document store with schema validation for testing."""
    from datetime import datetime, timezone
    import uuid
    
    # Create base in-memory store
    base_store = InMemoryDocumentStore()
    
    # Wrap with validation using document schemas
    schema_dir = Path(__file__).parent.parent.parent / "documents" / "schemas" / "documents"
    schema_provider = FileSchemaProvider(schema_dir=schema_dir)
    validating_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider
    )
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Seed with test data
    validating_store.insert_document(
        collection="messages",
        doc={
            "message_id": "<msg1@example.com>",
            "message_key": "msgkey-0000000001",
            "archive_id": "archive-00000001",
            "thread_id": "<thread@example.com>",
            "body_normalized": "This is a test message discussing important topics.",
            "from": {"email": "alice@example.com", "name": "Alice"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Important Discussion",
            "created_at": now,
        },
    )
    validating_store.insert_document(
        collection="messages",
        doc={
            "message_id": "<msg2@example.com>",
            "message_key": "msgkey-0000000002",
            "archive_id": "archive-00000001",
            "thread_id": "<thread@example.com>",
            "body_normalized": "I agree with the points raised in the previous message.",
            "from": {"email": "bob@example.com", "name": "Bob"},
            "date": "2023-10-15T13:00:00Z",
            "subject": "Re: Important Discussion",
            "created_at": now,
        },
    )
    
    return validating_store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store for testing."""
    return Mock()


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
def summarizer():
    """Create a mock summarizer with realistic latency."""
    return MockSummarizer(latency_ms=100)


@pytest.fixture
def integration_service(
    in_memory_document_store,
    mock_vector_store,
    mock_publisher,
    mock_subscriber,
    summarizer,
):
    """Create a summarization service with real storage adapters."""
    return SummarizationService(
        document_store=in_memory_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        retry_max_attempts=3,
        retry_backoff_seconds=1,
    )


@pytest.mark.integration
def test_end_to_end_summarization(integration_service, mock_publisher):
    """Test end-to-end summarization with real document store."""
    # Process a thread
    integration_service._process_thread(
        thread_id="<thread@example.com>",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize the following discussion:",
    )
    
    # Verify success event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summary.complete"
    
    # Verify event data
    message = publish_call[1]["event"]
    assert message["data"]["thread_id"] == "<thread@example.com>"
    assert "summary_markdown" in message["data"]
    assert message["data"]["llm_backend"] == "mock"
    
    # Verify stats
    assert integration_service.summaries_generated == 1
    assert integration_service.summarization_failures == 0


@pytest.mark.integration
def test_summarization_with_missing_thread(integration_service, mock_publisher):
    """Test summarization when thread doesn't exist."""
    # Process a non-existent thread
    integration_service._process_thread(
        thread_id="<nonexistent@example.com>",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )
    
    # Verify failure event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summarization.failed"
    
    # Verify error details
    message = publish_call[1]["event"]
    assert message["data"]["thread_id"] == "<nonexistent@example.com>"
    assert message["data"]["error_type"] == "NoContextError"
    
    # Verify stats
    assert integration_service.summaries_generated == 0


@pytest.mark.integration
def test_multiple_thread_summarization(integration_service, mock_publisher):
    """Test summarizing multiple threads."""
    event_data = {
        "thread_ids": ["<thread@example.com>"],
        "top_k": 10,
        "context_window_tokens": 3000,
        "prompt_template": "Summarize:",
    }
    
    integration_service.process_summarization(event_data)
    
    # Verify success event was published
    success_calls = [
        call for call in mock_publisher.publish.call_args_list
        if call[1]["routing_key"] == "summary.complete"
    ]
    assert len(success_calls) == 1
    
    # Verify stats
    assert integration_service.summaries_generated == 1


@pytest.mark.integration
def test_context_retrieval_integration(integration_service):
    """Test context retrieval with real document store."""
    context = integration_service._retrieve_context("<thread@example.com>", top_k=10)
    
    # Verify context was retrieved
    assert len(context["messages"]) == 2
    assert "This is a test message" in context["messages"][0]
    assert "I agree with the points" in context["messages"][1]
    
    # Verify chunks
    assert len(context["chunks"]) == 2
    assert context["chunks"][0]["message_id"] == "<msg1@example.com>"


@pytest.mark.integration
def test_service_stats_integration(integration_service):
    """Test service statistics tracking."""
    # Initial stats
    stats = integration_service.get_stats()
    assert stats["summaries_generated"] == 0
    assert stats["summarization_failures"] == 0
    
    # Process a thread
    integration_service._process_thread(
        thread_id="<thread@example.com>",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )
    
    # Updated stats
    stats = integration_service.get_stats()
    assert stats["summaries_generated"] == 1
    assert stats["summarization_failures"] == 0
    assert stats["last_processing_time_seconds"] > 0


@pytest.mark.integration
@pytest.mark.skip(reason="LocalLLMSummarizer tested in adapter tests; mocking requests module in integration context is complex")
def test_local_llm_real_content_flows_through(
    in_memory_document_store,
    mock_vector_store,
    mock_publisher,
    mock_subscriber,
):
    """Test that real Ollama content (not placeholder) flows through the pipeline.
    
    Note: This test is skipped because the LocalLLMSummarizer implementation is
    thoroughly tested in adapters/copilot_summarization/tests/test_local_llm_summarizer.py.
    Mocking the requests module in the integration test context with module reloading
    creates unnecessary complexity.
    """
    pass