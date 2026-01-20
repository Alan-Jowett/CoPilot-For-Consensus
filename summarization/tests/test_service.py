# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the summarization service."""

from unittest.mock import Mock

import pytest
from app.service import SummarizationService
from copilot_summarization import Citation, Summary

from .test_helpers import assert_valid_event_schema


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()

    # Default messages data
    messages_data = [
        {
            "_id": "aaa1111bbb222222",
            "message_id": "<msg1@example.com>",
            "thread_id": "1111222233334444",
            "body_normalized": "This is the first message in the thread.",
            "from": {"email": "user1@example.com", "name": "User One"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject",
        },
        {
            "_id": "ccc3333ddd444444",
            "message_id": "<msg2@example.com>",
            "thread_id": "1111222233334444",
            "body_normalized": "This is the second message in the thread.",
            "from": {"email": "user2@example.com", "name": "User Two"},
            "date": "2023-10-15T13:00:00Z",
            "subject": "Re: Test Subject",
        },
    ]

    # Default chunks data with canonical _id
    chunks_data = [
        {
            "_id": "aaaa1111bbbb2222",
            "message_id": "<msg1@example.com>",
            "thread_id": "1111222233334444",
            "text": "This is the first chunk.",
            "token_count": 10,
            "chunk_index": 0,
        },
        {
            "_id": "cccc3333dddd4444",
            "message_id": "<msg2@example.com>",
            "thread_id": "1111222233334444",
            "text": "This is the second chunk.",
            "token_count": 10,
            "chunk_index": 0,
        },
    ]

    # Collection-aware query that returns messages and chunks by thread_id
    def query_side_effect(collection, *args, **kwargs):
        if collection == "messages":
            return messages_data
        elif collection == "chunks":
            return chunks_data
        elif collection == "summaries":
            return []  # No existing summaries by default
        return []

    store.query_documents = Mock(side_effect=query_side_effect)
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    # Vector store methods can be mocked here if needed
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
def mock_summarizer():
    """Create a mock summarizer."""
    summarizer = Mock()
    summarizer.summarize = Mock(
        return_value=Summary(
            thread_id="1111222233334444",
            summary_markdown="# Summary\n\nThis is a test summary with citations [1].",
            citations=[
                Citation(
                    message_id="<msg1@example.com>",
                    chunk_id="aaaa1111bbbb2222",
                    offset=0,
                ),
            ],
            llm_backend="mock",
            llm_model="mock-model",
            tokens_prompt=100,
            tokens_completion=50,
            latency_ms=150,
        )
    )
    return summarizer


@pytest.fixture
def summarization_service(
    mock_document_store,
    mock_vector_store,
    mock_publisher,
    mock_subscriber,
    mock_summarizer,
):
    """Create a summarization service instance."""
    return SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        top_k=10,
        citation_count=10,
        retry_max_attempts=3,
        retry_backoff_seconds=1,
    )


def test_service_initialization(summarization_service):
    """Test that the service initializes correctly."""
    assert summarization_service.document_store is not None
    assert summarization_service.vector_store is not None
    assert summarization_service.publisher is not None
    assert summarization_service.subscriber is not None
    assert summarization_service.summarizer is not None
    assert summarization_service.summaries_generated == 0
    assert summarization_service.summarization_failures == 0


def test_service_start(summarization_service, mock_subscriber):
    """Test that the service subscribes to events on start."""
    summarization_service.start()

    # Verify subscription was called
    mock_subscriber.subscribe.assert_called_once()
    call_args = mock_subscriber.subscribe.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "summarization.requested"


def test_retrieve_context_success(summarization_service, mock_document_store):
    """Test retrieving context for a thread successfully."""
    context = summarization_service._retrieve_context("1111222233334444", top_k=10)

    # Verify context was retrieved
    assert len(context["messages"]) > 0
    assert len(context["chunks"]) > 0
    assert context["messages"][0] == "This is the first message in the thread."

    # Verify document store was queried
    mock_document_store.query_documents.assert_called_once_with(
        collection="messages",
        filter_dict={"thread_id": "1111222233334444"},
    )


def test_retrieve_context_no_messages(summarization_service, mock_document_store):
    """Test retrieving context when no messages are found."""
    # Override with side_effect that returns empty for all collections
    mock_document_store.query_documents.side_effect = lambda *args, **kwargs: []

    context = summarization_service._retrieve_context("1111222233334444", top_k=10)

    # Verify empty context
    assert context["messages"] == []
    assert context["chunks"] == []


def test_substitute_prompt_template(summarization_service):
    """Test substituting template variables in prompt template."""
    template = (
        "Thread ID: {thread_id}\n"
        "Messages: {message_count}\n"
        "Date range: {date_range}\n"
        "Participants: {participants}\n"
        "Drafts: {draft_mentions}\n"
        "Excerpts:\n{email_chunks}"
    )

    context = {
        "messages": [
            "First message",
            "Second message",
        ],
        "chunks": [
            {
                "from": {"email": "user1@example.com", "name": "User One"},
                "date": "2023-10-15T12:00:00Z",
                "draft_mentions": ["draft-ietf-quic-transport-34"],
            },
            {
                "from": {"email": "user2@example.com", "name": "User Two"},
                "date": "2023-10-15T13:00:00Z",
                "draft_mentions": ["draft-ietf-http-core-99"],
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Verify substitutions
    assert "thread-123" in result
    assert "Messages: 2" in result
    assert "2023-10-15T12:00:00Z to 2023-10-15T13:00:00Z" in result
    assert "user1@example.com" in result
    assert "draft-ietf-quic-transport-34" in result
    assert "First message" in result


def test_substitute_prompt_template_unexpected_placeholder(summarization_service):
    """Test that KeyError is caught for unexpected placeholders in template.

    If the template contains a placeholder that is not in the expected set
    ({thread_id}, {message_count}, {date_range}, {participants}, {draft_mentions},
    {email_chunks}), the string.format() call will raise KeyError. This should be
    caught and converted to ValueError with a descriptive message.
    """
    template = "Thread ID: {thread_id}\n" "Summary: {unexpected_placeholder}"

    context = {
        "messages": ["Message 1"],
        "chunks": [{"from": {"email": "test@example.com"}, "date": "2023-10-15T12:00:00Z", "draft_mentions": []}],
    }

    # Should raise ValueError (not KeyError) with descriptive message
    with pytest.raises(ValueError) as exc_info:
        summarization_service._substitute_prompt_template(
            prompt_template=template,
            thread_id="thread-123",
            context=context,
        )

    error_msg = str(exc_info.value)
    assert "unexpected_placeholder" in error_msg
    assert "Expected placeholders" in error_msg
    # Verify the expected placeholders are listed in error message
    assert "thread_id" in error_msg
    assert "message_count" in error_msg
    assert "email_chunks" in error_msg


def test_substitute_prompt_template_empty_messages(summarization_service):
    """Test substitution with empty messages list."""
    template = "Thread ID: {thread_id}\n" "Message count: {message_count}\n" "Excerpts:\n{email_chunks}"

    context = {
        "messages": [],  # Empty messages
        "chunks": [
            {
                "from": {"email": "user1@example.com", "name": "User One"},
                "date": "2023-10-15T12:00:00Z",
                "draft_mentions": [],
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Should handle empty messages gracefully
    assert "thread-123" in result
    assert "Message count: 0" in result
    assert result is not None


def test_substitute_prompt_template_empty_chunks(summarization_service):
    """Test substitution with empty chunks list."""
    template = "Thread ID: {thread_id}\n" "Participants: {participants}\n" "Excerpts:\n{email_chunks}"

    context = {
        "messages": ["Message 1", "Message 2"],
        "chunks": [],  # Empty chunks
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Should handle empty chunks gracefully
    assert "thread-123" in result
    assert "Participants:" in result
    # With empty chunks, there should be no participants
    assert result is not None


def test_substitute_prompt_template_both_empty(summarization_service):
    """Test substitution with both messages and chunks empty."""
    template = (
        "Thread ID: {thread_id}\n"
        "Messages: {message_count}\n"
        "Date range: {date_range}\n"
        "Participants: {participants}\n"
        "Drafts: {draft_mentions}\n"
        "Excerpts:\n{email_chunks}"
    )

    context = {
        "messages": [],
        "chunks": [],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Should handle both empty gracefully
    assert "thread-123" in result
    assert "Messages: 0" in result
    # Date range might be empty or a placeholder
    assert result is not None


def test_substitute_prompt_template_malformed_chunk_sender_not_dict(summarization_service):
    """Test that chunks with malformed 'from' field are handled.

    If chunk['from'] is not a dict but some other type, accessing
    chunk['from']['email'] will raise TypeError or KeyError.
    """
    template = "Participants: {participants}"

    context = {
        "messages": [],
        "chunks": [
            {
                "from": "invalid-sender-string",  # Should be dict
                "date": "2023-10-15T12:00:00Z",
                "draft_mentions": [],
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # String sender is preserved as participant label
    assert result == "Participants: invalid-sender-string"


def test_substitute_prompt_template_malformed_chunk_missing_date(summarization_service):
    """Test that chunks with missing 'date' field are handled."""
    template = "Date range: {date_range}"

    context = {
        "messages": [],
        "chunks": [
            {
                "from": {"email": "user1@example.com", "name": "User One"},
                # Missing 'date' field
                "draft_mentions": [],
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Missing dates should yield Unknown range
    assert result == "Date range: Unknown"


def test_substitute_prompt_template_chunk_with_none_from(summarization_service):
    """Test that chunks with None 'from' field are handled."""
    template = "Participants: {participants}"

    context = {
        "messages": [],
        "chunks": [
            {
                "from": None,  # None instead of dict
                "date": "2023-10-15T12:00:00Z",
                "draft_mentions": [],
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # None sender should fall back to default participants text
    assert result == "Participants: Multiple participants"


def test_substitute_prompt_template_draft_mentions_not_list(summarization_service):
    """Test that chunks with non-list draft_mentions are handled."""
    template = "Drafts: {draft_mentions}"

    context = {
        "messages": [],
        "chunks": [
            {
                "from": {"email": "user1@example.com", "name": "User One"},
                "date": "2023-10-15T12:00:00Z",
                "draft_mentions": "not-a-list",  # Should be list
            },
        ],
    }

    result = summarization_service._substitute_prompt_template(
        prompt_template=template,
        thread_id="thread-123",
        context=context,
    )

    # Non-list draft mentions should be ignored, using default text
    assert result == "Drafts: No specific drafts mentioned"


def test_format_citations(summarization_service):
    """Test formatting citations."""
    citations = [
        Citation(
            message_id="<msg1@example.com>",
            chunk_id="aaaa1111bbbb2222",
            offset=0,
        ),
        Citation(
            message_id="<msg2@example.com>",
            chunk_id="cccc3333dddd4444",
            offset=10,
        ),
    ]

    chunks = [
        {"_id": "aaaa1111bbbb2222", "message_id": "<msg1@example.com>", "text": "Text 1"},
        {"_id": "cccc3333dddd4444", "message_id": "<msg2@example.com>", "text": "Text 2"},
    ]

    formatted = summarization_service._format_citations(citations, chunks)

    assert len(formatted) == 2
    assert formatted[0]["message_id"] == "<msg1@example.com>"
    assert formatted[0]["chunk_id"] == "aaaa1111bbbb2222"
    assert formatted[0]["offset"] == 0
    assert formatted[0]["text"] == "Text 1"
    assert formatted[1]["text"] == "Text 2"


def test_format_citations_limit(summarization_service):
    """Test that citations are limited to citation_count."""
    # Create more citations than the limit
    citations = [
        Citation(
            message_id=f"<msg{i}@example.com>",
            chunk_id=f"chunk_{i}",
            offset=i * 10,
        )
        for i in range(20)
    ]

    formatted = summarization_service._format_citations(citations, [])

    # Should be limited to citation_count (10)
    assert len(formatted) == 10


def test_format_citations_full_text(summarization_service):
    """Test that citation text includes the full chunk text.

    Since chunks are already sized by the chunking service (384 token target, max 512),
    we no longer truncate citation text in the summarization service.
    """
    long_text = "x" * 1000  # 1000 character text

    citations = [
        Citation(
            message_id="<msg1@example.com>",
            chunk_id="aaaa1111bbbb2222",
            offset=0,
        ),
    ]

    chunks = [
        {"_id": "aaaa1111bbbb2222", "message_id": "<msg1@example.com>", "text": long_text},
    ]

    formatted = summarization_service._format_citations(citations, chunks)

    assert len(formatted) == 1
    # Full text should be returned without truncation
    assert len(formatted[0]["text"]) == 1000
    assert formatted[0]["text"] == "x" * 1000


def test_format_citations_missing_chunk_id(summarization_service):
    """Test that citations with non-existent chunk_ids result in empty text."""
    citations = [
        Citation(
            message_id="<msg1@example.com>",
            chunk_id="chunk_nonexistent",
            offset=0,
        ),
    ]

    chunks = [
        {"_id": "aaaa1111bbbb2222", "message_id": "<msg1@example.com>", "text": "Text 1"},
    ]

    formatted = summarization_service._format_citations(citations, chunks)

    assert len(formatted) == 1
    assert formatted[0]["chunk_id"] == "chunk_nonexistent"
    assert formatted[0]["text"] == ""  # Empty text for non-existent chunk


def test_process_thread_success(summarization_service, mock_summarizer, mock_publisher):
    """Test processing a thread successfully."""
    summarization_service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify summarizer was called
    mock_summarizer.summarize.assert_called_once()

    # Verify success event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summary.complete"

    # Verify stats were updated
    assert summarization_service.summaries_generated == 1
    assert summarization_service.summarization_failures == 0


def test_process_thread_citations_generated_from_chunks(
    summarization_service,
    mock_summarizer,
    mock_publisher,
    mock_document_store,
):
    """Test that citations are generated from chunks, not from LLM output.

    This test verifies the fix for issue 365: all production summarizers return
    empty citations. The service should generate citations from the chunks used
    as context, ignoring any citations returned by the LLM (which may be empty
    or hallucinated).
    """
    # Configure mock_summarizer to return a summary with citations
    # (even though real LLMs return empty arrays)
    mock_summarizer.summarize.return_value = Summary(
        thread_id="1111222233334444",
        summary_markdown="# Summary\n\nTest summary with LLM-provided citations [1][2].",
        citations=[
            # These citations from the LLM should be IGNORED
            Citation(
                message_id="<hallucinated@example.com>",
                chunk_id="hallucinated_chunk",
                offset=999,
            ),
        ],
        llm_backend="mock",
        llm_model="mock-model",
        tokens_prompt=100,
        tokens_completion=50,
        latency_ms=150,
    )

    # Process the thread
    summarization_service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify success event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summary.complete"

    # Get the published event (passed as 'event' parameter)
    event_data = publish_call[1]["event"]

    # CRITICAL: Verify citations were generated from chunks, NOT from LLM
    citations = event_data["data"]["citations"]

    # Should have 2 citations (one per message/chunk from context)
    assert len(citations) == 2, "Should generate citations from chunks in context"

    # Verify citations match the messages in context (from mock_document_store)
    citation_message_ids = {c["message_id"] for c in citations}
    expected_message_ids = {"<msg1@example.com>", "<msg2@example.com>"}
    assert citation_message_ids == expected_message_ids, "Citations should reference actual messages from context"

    # Verify LLM-returned citations were IGNORED (no hallucinated citations)
    for citation in citations:
        assert (
            citation["message_id"] != "<hallucinated@example.com>"
        ), "Should not include hallucinated citation from LLM"
        assert citation["chunk_id"] != "hallucinated_chunk", "Should not include hallucinated chunk_id from LLM"

    # Verify each citation has required fields from chunks
    for citation in citations:
        assert "message_id" in citation
        assert "chunk_id" in citation
        assert "offset" in citation
        assert "text" in citation  # Text from chunk
        assert citation["text"] != "", "Citation should have text from chunk"

    # Verify stats were updated
    assert summarization_service.summaries_generated == 1


def test_process_thread_no_context(summarization_service, mock_document_store, mock_publisher):
    """Test processing a thread when no context is available."""
    # Override with side_effect that returns empty for all collections
    mock_document_store.query_documents.side_effect = lambda *args, **kwargs: []

    summarization_service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify failure event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summarization.failed"

    # Verify stats were not updated
    assert summarization_service.summaries_generated == 0


def test_process_thread_retry_on_failure(
    summarization_service,
    mock_summarizer,
    mock_publisher,
):
    """Test that the service retries on failure."""
    # Make summarizer fail twice, then succeed
    mock_summarizer.summarize.side_effect = [
        Exception("LLM error"),
        Exception("LLM error"),
        Summary(
            thread_id="1111222233334444",
            summary_markdown="Success on retry",
            citations=[],
            llm_backend="mock",
            llm_model="mock-model",
            tokens_prompt=100,
            tokens_completion=50,
            latency_ms=150,
        ),
    ]

    summarization_service.retry_backoff_seconds = 0  # No delay for testing

    summarization_service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify summarizer was called 3 times
    assert mock_summarizer.summarize.call_count == 3

    # Verify success event was published
    publish_calls = [call for call in mock_publisher.publish.call_args_list]
    success_calls = [call for call in publish_calls if call[1]["routing_key"] == "summary.complete"]
    assert len(success_calls) == 1

    # Verify stats
    assert summarization_service.summaries_generated == 1


def test_process_thread_max_retries_exceeded(
    summarization_service,
    mock_summarizer,
    mock_publisher,
):
    """Test that the service fails after max retries."""
    # Make summarizer always fail
    mock_summarizer.summarize.side_effect = Exception("Persistent LLM error")

    summarization_service.retry_backoff_seconds = 0  # No delay for testing

    summarization_service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify summarizer was called max_attempts times
    assert mock_summarizer.summarize.call_count == 3

    # Verify failure event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summarization.failed"

    # Verify stats
    assert summarization_service.summaries_generated == 0
    assert summarization_service.summarization_failures == 1


def test_process_summarization_multiple_threads(
    summarization_service,
    mock_summarizer,
    mock_publisher,
):
    """Test processing multiple threads."""
    event_data = {
        "thread_ids": ["<thread1@example.com>", "<thread2@example.com>"],
        "top_k": 10,
        "context_window_tokens": 3000,
        "prompt_template": "Summarize:",
    }

    summarization_service.process_summarization(event_data)

    # Verify summarizer was called for each thread
    assert mock_summarizer.summarize.call_count == 2

    # Verify success events were published for each thread
    success_calls = [
        call for call in mock_publisher.publish.call_args_list if call[1]["routing_key"] == "summary.complete"
    ]
    assert len(success_calls) == 2

    # Verify stats
    assert summarization_service.summaries_generated == 2


def test_get_stats(summarization_service):
    """Test getting service statistics."""
    stats = summarization_service.get_stats()

    assert "summaries_generated" in stats
    assert "summarization_failures" in stats
    assert "last_processing_time_seconds" in stats
    assert stats["summaries_generated"] == 0
    assert stats["summarization_failures"] == 0


def test_handle_summarization_requested_event(
    summarization_service,
    mock_summarizer,
    mock_publisher,
):
    """Test handling SummarizationRequested event."""
    event = {
        "data": {
            "thread_ids": ["1111222233334444"],
            "top_k": 10,
            "context_window_tokens": 3000,
            "prompt_template": "Summarize:",
        }
    }

    summarization_service._handle_summarization_requested(event)

    # Verify summarizer was called
    mock_summarizer.summarize.assert_called_once()

    # Verify success event was published
    success_calls = [
        call for call in mock_publisher.publish.call_args_list if call[1]["routing_key"] == "summary.complete"
    ]
    assert len(success_calls) == 1


def test_publish_summary_complete(summarization_service, mock_publisher):
    """Test publishing SummaryComplete event."""
    summarization_service._publish_summary_complete(
        summary_id="aaaaaabbbbbbcccc",
        thread_id="1111222233334444",
        summary_markdown="# Summary\n\nTest summary",
        citations=[{"message_id": "<msg1@example.com>", "chunk_id": "aaaa1111bbbb2222", "offset": 0}],
        llm_backend="mock",
        llm_model="mock-model",
        tokens_prompt=100,
        tokens_completion=50,
        latency_ms=150,
    )

    # Verify publish was called
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args

    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "summary.complete"

    message = call_args[1]["event"]
    assert message["data"]["summary_id"] == "aaaaaabbbbbbcccc"
    assert message["data"]["thread_id"] == "1111222233334444"
    assert message["data"]["summary_markdown"] == "# Summary\n\nTest summary"
    assert len(message["data"]["citations"]) == 1

    # Validate event against JSON schema
    assert_valid_event_schema(message)


def test_publish_summarization_failed(summarization_service, mock_publisher):
    """Test publishing SummarizationFailed event."""
    summarization_service._publish_summarization_failed(
        thread_id="1111222233334444",
        error_type="LLMTimeout",
        error_message="Request timed out",
        retry_count=2,
    )

    # Verify publish was called
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args

    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "summarization.failed"

    message = call_args[1]["event"]
    assert message["data"]["thread_id"] == "1111222233334444"
    assert message["data"]["error_type"] == "LLMTimeout"
    assert message["data"]["error_message"] == "Request timed out"
    assert message["data"]["retry_count"] == 2

    # Validate event against JSON schema
    assert_valid_event_schema(message)


def test_service_with_metrics_collector(
    mock_document_store,
    mock_vector_store,
    mock_publisher,
    mock_subscriber,
    mock_summarizer,
):
    """Test service with metrics collector."""
    mock_metrics = Mock()

    service = SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        metrics_collector=mock_metrics,
    )

    service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify metrics were collected
    assert mock_metrics.increment.call_count > 0
    assert mock_metrics.observe.call_count > 0


def test_service_with_error_reporter(
    mock_document_store,
    mock_vector_store,
    mock_publisher,
    mock_subscriber,
    mock_summarizer,
):
    """Test service with error reporter."""
    mock_error_reporter = Mock()
    mock_summarizer.summarize.side_effect = Exception("Test error")

    service = SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        error_reporter=mock_error_reporter,
        retry_max_attempts=1,
        retry_backoff_seconds=0,
    )

    service._process_thread(
        thread_id="1111222233334444",
        top_k=10,
        context_window_tokens=3000,
        prompt_template="Summarize:",
    )

    # Verify error was reported
    mock_error_reporter.report.assert_called()


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_schema_validation_summary_complete_valid(summarization_service, mock_publisher):
    """Test that SummaryComplete events validate against schema."""
    summarization_service._publish_summary_complete(
        summary_id="aaaaaabbbbbbcccc",
        thread_id="1111222233334444",
        summary_markdown="# Summary\n\nTest",
        citations=[],
        llm_backend="test",
        llm_model="test-model",
        tokens_prompt=10,
        tokens_completion=5,
        latency_ms=100,
    )

    call_args = mock_publisher.publish.call_args
    event = call_args[1]["event"]

    # Should pass schema validation
    assert_valid_event_schema(event)


def test_schema_validation_summarization_failed_valid(summarization_service, mock_publisher):
    """Test that SummarizationFailed events validate against schema."""
    summarization_service._publish_summarization_failed(
        thread_id="1111222233334444",
        error_type="TestError",
        error_message="Test error message",
        retry_count=0,
    )

    call_args = mock_publisher.publish.call_args
    event = call_args[1]["event"]

    # Should pass schema validation
    assert_valid_event_schema(event)


# ============================================================================
# Message Consumption Tests
# ============================================================================


def test_consume_summarization_requested_event():
    """Test consuming a SummarizationRequested event."""
    mock_store = Mock()

    # Collection-aware mock that returns messages for "messages" and empty for "summaries"
    messages_data = [
        {
            "message_id": "<msg@example.com>",
            "thread_id": "1111222233334444",
            "body_normalized": "Test message",
            "from": {"email": "user@example.com", "name": "User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test",
        }
    ]

    def query_side_effect(collection, *args, **kwargs):
        if collection == "messages":
            return messages_data
        elif collection == "summaries":
            return []
        return []

    mock_store.query_documents = Mock(side_effect=query_side_effect)

    mock_vector = Mock()
    mock_publisher = Mock()
    mock_publisher.publish = Mock()
    mock_subscriber = Mock()

    mock_summarizer = Mock()
    mock_summarizer.summarize = Mock(
        return_value=Summary(
            thread_id="1111222233334444",
            summary_markdown="Test summary",
            citations=[],
            llm_backend="test",
            llm_model="test-model",
            tokens_prompt=10,
            tokens_completion=5,
            latency_ms=100,
        )
    )

    service = SummarizationService(
        document_store=mock_store,
        vector_store=mock_vector,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        retry_max_attempts=1,
        retry_backoff_seconds=0,
    )

    # Simulate receiving a SummarizationRequested event
    event = {
        "event_type": "SummarizationRequested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "thread_ids": ["1111222233334444"],
            "top_k": 10,
            "prompt_template": "Summarize:",
        },
    }

    # Validate incoming event
    assert_valid_event_schema(event)

    # Process the event
    service._handle_summarization_requested(event)

    # Verify summarizer was called
    mock_summarizer.summarize.assert_called_once()

    # Verify success event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "summary.complete"


def test_consume_summarization_requested_multiple_threads():
    """Test consuming a SummarizationRequested event with multiple threads."""
    mock_store = Mock()

    # Collection-aware mock that returns messages for "messages" and empty for "summaries"
    messages_data = [
        {
            "message_id": "<msg@example.com>",
            "thread_id": "<thread1@example.com>",
            "body_normalized": "Test",
            "from": {"email": "user@example.com", "name": "User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test",
        }
    ]

    def query_side_effect(collection, *args, **kwargs):
        if collection == "messages":
            return messages_data
        elif collection == "summaries":
            return []
        return []

    mock_store.query_documents = Mock(side_effect=query_side_effect)

    mock_vector = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()

    mock_summarizer = Mock()
    mock_summarizer.summarize = Mock(
        return_value=Summary(
            thread_id="1111222233334444",
            summary_markdown="Test",
            citations=[],
            llm_backend="test",
            llm_model="test-model",
            tokens_prompt=10,
            tokens_completion=5,
            latency_ms=100,
        )
    )

    service = SummarizationService(
        document_store=mock_store,
        vector_store=mock_vector,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        retry_max_attempts=1,
        retry_backoff_seconds=0,
    )

    # Event with multiple thread IDs
    event = {
        "event_type": "SummarizationRequested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "thread_ids": ["<thread1@example.com>", "<thread2@example.com>"],
            "top_k": 10,
            "llm_backend": "test",
            "llm_model": "test-model",
            "context_window_tokens": 3000,
            "prompt_template": "Summarize:",
        },
    }

    service._handle_summarization_requested(event)

    # Should process both threads
    assert mock_summarizer.summarize.call_count == 2


# ============================================================================
# Invalid Message Handling Tests
# ============================================================================


def test_handle_malformed_event_missing_data():
    """Test handling event with missing data field."""
    mock_store = Mock()
    mock_vector = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_summarizer = Mock()

    service = SummarizationService(
        document_store=mock_store,
        vector_store=mock_vector,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
    )

    # Event missing 'data' field
    event = {
        "event_type": "SummarizationRequested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
    }

    # Service should raise an exception for missing data field
    with pytest.raises(KeyError):
        service._handle_summarization_requested(event)


def test_handle_malformed_event_missing_required_field():
    """Test handling event with missing required field in data."""
    mock_store = Mock()
    mock_vector = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_summarizer = Mock()

    service = SummarizationService(
        document_store=mock_store,
        vector_store=mock_vector,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
    )

    # Event missing required 'thread_ids' field
    event = {
        "event_type": "SummarizationRequested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "top_k": 10,
            "llm_backend": "test",
            "llm_model": "test-model",
            "context_window_tokens": 3000,
            "prompt_template": "Summarize:",
        },
    }

    # Service should raise an exception for missing required field
    with pytest.raises(KeyError):
        service._handle_summarization_requested(event)


def test_handle_event_with_invalid_thread_ids_type():
    """Test handling event with invalid thread_ids type."""
    mock_store = Mock()
    mock_vector = Mock()
    mock_publisher = Mock()
    mock_subscriber = Mock()
    mock_summarizer = Mock()

    service = SummarizationService(
        document_store=mock_store,
        vector_store=mock_vector,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
    )

    # thread_ids should be array but is string
    event = {
        "event_type": "SummarizationRequested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "thread_ids": "not-an-array",
            "top_k": 10,
            "llm_backend": "test",
            "llm_model": "test-model",
            "context_window_tokens": 3000,
            "prompt_template": "Summarize:",
        },
    }

    # Service should raise an exception for invalid type
    with pytest.raises((TypeError, AttributeError)):
        service._handle_summarization_requested(event)


def test_publish_summary_complete_with_publisher_failure(
    mock_document_store,
    mock_vector_store,
    mock_summarizer,
):
    """Test that _publish_summary_complete raises exception when publisher fails."""
    # Create a publisher that raises an exception
    mock_publisher = Mock()
    mock_publisher.publish = Mock(side_effect=Exception("Failed to publish SummaryComplete event for test-thread"))

    mock_subscriber = Mock()

    service = SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
    )

    # Should propagate exception when publisher raises
    with pytest.raises(Exception) as exc_info:
        service._publish_summary_complete(
            summary_id="aaaaaabbbbbbcccc",
            thread_id="test-thread",
            summary_markdown="# Test Summary",
            citations=[],
            llm_backend="test",
            llm_model="test-model",
            tokens_prompt=100,
            tokens_completion=50,
            latency_ms=1000,
        )

    assert "Failed to publish SummaryComplete event" in str(exc_info.value)


def test_publish_summarization_failed_with_publisher_failure(
    mock_document_store,
    mock_vector_store,
    mock_summarizer,
):
    """Test that _publish_summarization_failed raises exception when publisher fails."""
    # Create a publisher that raises an exception
    mock_publisher = Mock()
    mock_publisher.publish = Mock(side_effect=Exception("Failed to publish SummarizationFailed event for test-thread"))

    mock_subscriber = Mock()

    service = SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
    )

    # Should propagate exception when publisher raises
    with pytest.raises(Exception) as exc_info:
        service._publish_summarization_failed(
            thread_id="test-thread",
            error_type="TestError",
            error_message="Test error message",
            retry_count=3,
        )

    assert "Failed to publish SummarizationFailed event" in str(exc_info.value)


def test_idempotent_summarization(
    summarization_service,
    mock_document_store,
    mock_summarizer,
    mock_publisher,
):
    """Test that summarization service regenerates summaries when requested.

    The orchestrator is responsible for idempotency checks. The summarization service
    should always execute summarization requests, allowing the orchestrator to control
    regeneration policy (e.g., when new chunks arrive for a thread).
    """
    thread_id = "1111222233334444"

    # Setup messages for context retrieval
    messages_data = [
        {
            "message_id": "<msg1@example.com>",
            "thread_id": thread_id,
            "body_normalized": "Test message 1",
        },
        {
            "message_id": "<msg2@example.com>",
            "thread_id": thread_id,
            "body_normalized": "Test message 2",
        },
    ]

    # Setup summary that already exists in database
    existing_summary = {
        "summary_id": "summary-123",
        "thread_id": thread_id,
        "summary_type": "thread",
        "summary_markdown": "Existing summary",
    }

    # Configure mock to return messages for context retrieval
    def query_side_effect(collection, filter_dict, **kwargs):
        if collection == "summaries":
            # Existing summary in database (orchestrator should have checked this)
            return [existing_summary]
        elif collection == "messages":
            # Return messages for context
            return messages_data
        return []

    mock_document_store.query_documents.side_effect = query_side_effect

    event_data = {
        "thread_ids": [thread_id],
        "top_k": 12,
        "context_window_tokens": 3000,
        "prompt_template": "Summarize this:",
    }

    # Process summarization - should generate new summary even though one exists
    summarization_service.process_summarization(event_data)

    # Verify summarizer was called (regenerated despite existing summary)
    assert mock_summarizer.summarize.call_count == 1

    # Verify summary complete event was published
    assert mock_publisher.publish.call_count == 1
    assert summarization_service.summaries_generated == 1

    # Reset mocks
    mock_summarizer.summarize.reset_mock()
    mock_publisher.publish.reset_mock()

    # Second request - should also generate (orchestrator controls idempotency)
    summarization_service.process_summarization(event_data)

    # Verify summarizer was called again
    assert mock_summarizer.summarize.call_count == 1

    # New event should be published
    assert mock_publisher.publish.call_count == 1

    # Stats reflect both summaries were generated
    assert summarization_service.summaries_generated == 2


def test_generate_summary_id_deterministic(summarization_service):
    """Test that summary ID generation is deterministic."""
    citations1 = [
        {"_id": "aaaa1111bbbb2222", "chunk_id": "aaaa1111bbbb2222", "message_id": "msg_1", "offset": 0},
        {"_id": "cccc3333dddd4444", "chunk_id": "cccc3333dddd4444", "message_id": "msg_2", "offset": 10},
    ]

    citations2 = [
        {"_id": "cccc3333dddd4444", "chunk_id": "cccc3333dddd4444", "message_id": "msg_2", "offset": 10},
        {"_id": "aaaa1111bbbb2222", "chunk_id": "aaaa1111bbbb2222", "message_id": "msg_1", "offset": 0},
    ]

    # Same thread and chunks (different order) should produce same ID
    id1 = summarization_service._generate_summary_id("1111222233334444", citations1)
    id2 = summarization_service._generate_summary_id("1111222233334444", citations2)

    assert id1 == id2
    assert len(id1) == 64  # SHA256 hex digest length

    # Different thread should produce different ID
    id3 = summarization_service._generate_summary_id("<other_thread@example.com>", citations1)
    assert id3 != id1

    # Different chunks should produce different ID
    citations3 = [
        {"_id": "eeee5555ffff6666", "chunk_id": "eeee5555ffff6666", "message_id": "msg_3", "offset": 0},
    ]
    id4 = summarization_service._generate_summary_id("1111222233334444", citations3)
    assert id4 != id1


def test_generate_summary_id_empty_citations(summarization_service):
    """Test that summary ID generation works with empty citations."""
    id1 = summarization_service._generate_summary_id("1111222233334444", [])

    assert id1 is not None
    assert len(id1) == 64

    # Same thread with no citations should produce same ID
    id2 = summarization_service._generate_summary_id("1111222233334444", [])
    assert id1 == id2


def test_retrieve_context_from_selected_chunks_success(summarization_service):
    """Test _retrieve_context_from_selected_chunks with valid selected chunks."""
    selected_chunks = [
        {"chunk_id": "chunk1", "source": "thread_chunks", "score": 0.9, "rank": 0},
        {"chunk_id": "chunk2", "source": "thread_chunks", "score": 0.8, "rank": 1},
    ]

    # The mock_document_store fixture uses a side_effect; disable it for this test
    # so return_value controls the response.
    summarization_service.document_store.query_documents.side_effect = None
    summarization_service.document_store.query_documents.reset_mock()

    # Mock document store to return chunks
    summarization_service.document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
        {"_id": "chunk2", "text": "text2", "thread_id": "thread1"},
    ]

    context = summarization_service._retrieve_context_from_selected_chunks(
        thread_id="thread1",
        selected_chunks=selected_chunks
    )

    # Verify document store was queried with correct chunk_ids
    summarization_service.document_store.query_documents.assert_called_once_with(
        collection="chunks",
        filter_dict={"_id": {"$in": ["chunk1", "chunk2"]}},
        limit=2
    )

    # Verify context structure
    assert len(context["messages"]) == 2
    assert context["messages"][0] == "text1"
    assert context["messages"][1] == "text2"
    assert len(context["chunks"]) == 2
    
    # Verify selection metadata is added to chunks
    assert context["chunks"][0]["selection_score"] == 0.9
    assert context["chunks"][0]["selection_rank"] == 0
    assert context["chunks"][0]["selection_source"] == "thread_chunks"
    assert context["chunks"][1]["selection_score"] == 0.8
    assert context["chunks"][1]["selection_rank"] == 1


def test_retrieve_context_from_selected_chunks_preserves_order(summarization_service):
    """Test that _retrieve_context_from_selected_chunks preserves selection order."""
    selected_chunks = [
        {"chunk_id": "chunk2", "source": "thread_chunks", "score": 0.9, "rank": 0},
        {"chunk_id": "chunk1", "source": "thread_chunks", "score": 0.8, "rank": 1},
    ]

    # The mock_document_store fixture uses a side_effect; disable it for this test
    # so return_value controls the response.
    summarization_service.document_store.query_documents.side_effect = None
    summarization_service.document_store.query_documents.reset_mock()

    # Return chunks in different order than selected
    summarization_service.document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "text1"},
        {"_id": "chunk2", "text": "text2"},
    ]

    context = summarization_service._retrieve_context_from_selected_chunks(
        thread_id="thread1",
        selected_chunks=selected_chunks
    )

    # Verify order matches selected_chunks, not document store return order
    assert context["chunks"][0]["_id"] == "chunk2"
    assert context["chunks"][1]["_id"] == "chunk1"


def test_retrieve_context_from_selected_chunks_empty(summarization_service):
    """Test _retrieve_context_from_selected_chunks with empty selected_chunks."""
    context = summarization_service._retrieve_context_from_selected_chunks(
        thread_id="thread1",
        selected_chunks=[]
    )

    assert context["messages"] == []
    assert context["chunks"] == []


def test_retrieve_context_from_selected_chunks_missing_chunk_ids(summarization_service):
    """Test _retrieve_context_from_selected_chunks with invalid chunk data."""
    selected_chunks = [
        {"source": "thread_chunks", "score": 0.9, "rank": 0},  # Missing chunk_id
        {"chunk_id": None, "source": "thread_chunks", "score": 0.8, "rank": 1},  # None chunk_id
    ]

    context = summarization_service._retrieve_context_from_selected_chunks(
        thread_id="thread1",
        selected_chunks=selected_chunks
    )

    # Should handle gracefully and return empty
    assert context["messages"] == []
    assert context["chunks"] == []


def test_retrieve_context_from_selected_chunks_missing_in_store(summarization_service, caplog):
    """Test _retrieve_context_from_selected_chunks when chunks missing from document store."""
    import logging
    
    selected_chunks = [
        {"chunk_id": "chunk1", "source": "thread_chunks", "score": 0.9, "rank": 0},
        {"chunk_id": "chunk2", "source": "thread_chunks", "score": 0.8, "rank": 1},
        {"chunk_id": "chunk3", "source": "thread_chunks", "score": 0.7, "rank": 2},
    ]

    # The mock_document_store fixture uses a side_effect; disable it for this test
    # so return_value controls the response.
    summarization_service.document_store.query_documents.side_effect = None
    summarization_service.document_store.query_documents.reset_mock()

    # Only return 2 of 3 chunks (chunk3 missing)
    summarization_service.document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "text1"},
        {"_id": "chunk2", "text": "text2"},
    ]

    with caplog.at_level(logging.WARNING):
        context = summarization_service._retrieve_context_from_selected_chunks(
            thread_id="thread1",
            selected_chunks=selected_chunks
        )

    # Verify only 2 chunks returned (missing one skipped)
    assert len(context["chunks"]) == 2
    assert context["chunks"][0]["_id"] == "chunk1"
    assert context["chunks"][1]["_id"] == "chunk2"

    # Verify warning was logged about missing chunk
    assert any("Data inconsistency" in record.message for record in caplog.records)
    assert any("chunk3" in record.message for record in caplog.records)


def test_retrieve_context_from_selected_chunks_validates_dict_type(summarization_service):
    """Test _retrieve_context_from_selected_chunks validates chunk dict type."""
    selected_chunks = [
        {"chunk_id": "chunk1", "source": "thread_chunks", "score": 0.9, "rank": 0},
        None,  # Invalid - not a dict
        "invalid",  # Invalid - not a dict
        {"chunk_id": "chunk2", "source": "thread_chunks", "score": 0.8, "rank": 1},
    ]

    # The mock_document_store fixture uses a side_effect; disable it for this test
    # so return_value controls the response.
    summarization_service.document_store.query_documents.side_effect = None
    summarization_service.document_store.query_documents.reset_mock()

    summarization_service.document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "text1"},
        {"_id": "chunk2", "text": "text2"},
    ]

    context = summarization_service._retrieve_context_from_selected_chunks(
        thread_id="thread1",
        selected_chunks=selected_chunks
    )

    # Should only process valid dict entries
    assert len(context["chunks"]) == 2

