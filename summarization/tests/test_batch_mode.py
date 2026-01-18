# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for batch mode summarization service."""

from unittest.mock import Mock

import pytest
from app.service import SummarizationService
from copilot_summarization import Summary


@pytest.fixture
def mock_document_store_batch():
    """Create a mock document store for batch tests."""
    store = Mock()

    def query_side_effect(collection, *args, **kwargs):
        if collection == "messages":
            # Return different messages based on thread_id filter
            thread_id = kwargs.get("filter_dict", {}).get("thread_id")
            if thread_id == "thread-1":
                return [
                    {
                        "_id": "msg1_id",
                        "message_id": "<msg1@example.com>",
                        "thread_id": "thread-1",
                        "body_normalized": "Message 1 for thread 1",
                        "from": {"email": "user1@example.com", "name": "User One"},
                        "date": "2023-10-15T12:00:00Z",
                    },
                ]
            elif thread_id == "thread-2":
                return [
                    {
                        "_id": "msg2_id",
                        "message_id": "<msg2@example.com>",
                        "thread_id": "thread-2",
                        "body_normalized": "Message 1 for thread 2",
                        "from": {"email": "user2@example.com", "name": "User Two"},
                        "date": "2023-10-15T13:00:00Z",
                    },
                ]
            else:
                return []
        return []

    store.query_documents = Mock(side_effect=query_side_effect)
    return store


@pytest.fixture
def mock_batch_summarizer():
    """Create a mock summarizer that supports batch mode."""
    summarizer = Mock()

    # Mock interactive mode
    summarizer.summarize = Mock(return_value=Summary(
        thread_id="thread-1",
        summary_markdown="Summary for thread 1",
        citations=[],
        llm_backend="openai",
        llm_model="gpt-4o-mini",
        tokens_prompt=100,
        tokens_completion=50,
        latency_ms=150,
    ))

    # Mock batch mode methods
    summarizer.create_batch = Mock(return_value="batch-123")

    def get_batch_status_side_effect(batch_id):
        # Simulate immediate completion for testing
        return {
            "status": "completed",
            "request_counts": {
                "total": 2,
                "completed": 2,
                "failed": 0
            },
            "output_file_id": "file-output-123"
        }

    summarizer.get_batch_status = Mock(side_effect=get_batch_status_side_effect)

    def retrieve_batch_results_side_effect(batch_id):
        return [
            Summary(
                thread_id="thread-1",
                summary_markdown="Batch summary for thread 1",
                citations=[],
                llm_backend="openai",
                llm_model="gpt-4o-mini",
                tokens_prompt=100,
                tokens_completion=50,
                latency_ms=0,
            ),
            Summary(
                thread_id="thread-2",
                summary_markdown="Batch summary for thread 2",
                citations=[],
                llm_backend="openai",
                llm_model="gpt-4o-mini",
                tokens_prompt=110,
                tokens_completion=55,
                latency_ms=0,
            ),
        ]

    summarizer.retrieve_batch_results = Mock(side_effect=retrieve_batch_results_side_effect)

    return summarizer


@pytest.fixture
def batch_summarization_service(
    mock_document_store_batch,
    mock_batch_summarizer,
):
    """Create a batch-enabled summarization service instance."""
    return SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=mock_batch_summarizer,
        top_k=10,
        citation_count=10,
        retry_max_attempts=3,
        retry_backoff_seconds=1,
        batch_mode_enabled=True,
        batch_max_threads=50,
        batch_poll_interval_seconds=1,  # Short interval for testing
    )


def test_batch_mode_enabled_for_multiple_threads(
    batch_summarization_service,
    mock_batch_summarizer,
):
    """Test that batch mode is used when processing multiple threads."""
    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    batch_summarization_service.process_summarization(event_data)

    # Verify batch methods were called, not individual summarize
    mock_batch_summarizer.create_batch.assert_called_once()
    mock_batch_summarizer.get_batch_status.assert_called()
    mock_batch_summarizer.retrieve_batch_results.assert_called_once()
    mock_batch_summarizer.summarize.assert_not_called()

    # Verify stats
    assert batch_summarization_service.summaries_generated == 2


def test_batch_mode_disabled_for_single_thread(
    mock_document_store_batch,
    mock_batch_summarizer,
):
    """Test that single threads use interactive mode even with batch enabled."""
    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=mock_batch_summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,  # Batch enabled
        batch_max_threads=50,
        batch_poll_interval_seconds=1,
    )

    event_data = {
        "thread_ids": ["thread-1"],  # Single thread
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    service.process_summarization(event_data)

    # Verify interactive mode was used
    mock_batch_summarizer.summarize.assert_called_once()
    mock_batch_summarizer.create_batch.assert_not_called()


def test_batch_mode_disabled_uses_interactive(
    mock_document_store_batch,
    mock_batch_summarizer,
):
    """Test that batch mode disabled uses interactive mode."""
    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=mock_batch_summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=False,  # Batch disabled
        batch_max_threads=50,
        batch_poll_interval_seconds=1,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    service.process_summarization(event_data)

    # Verify interactive mode was used for both threads
    assert mock_batch_summarizer.summarize.call_count == 2
    mock_batch_summarizer.create_batch.assert_not_called()


def test_batch_mode_not_available_fallback(
    mock_document_store_batch,
):
    """Test fallback to interactive mode when summarizer doesn't support batch."""
    # Create a summarizer without batch methods
    simple_summarizer = Mock(spec=['summarize'])  # Only has summarize method
    simple_summarizer.summarize = Mock(return_value=Summary(
        thread_id="thread-1",
        summary_markdown="Summary",
        citations=[],
        llm_backend="local",
        llm_model="mistral",
        tokens_prompt=100,
        tokens_completion=50,
        latency_ms=150,
    ))

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=simple_summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,  # Batch enabled but not supported
        batch_max_threads=50,
        batch_poll_interval_seconds=1,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    service.process_summarization(event_data)

    # Should fall back to interactive mode
    assert simple_summarizer.summarize.call_count == 2


def test_batch_citations_generated_from_chunks(
    batch_summarization_service,
    mock_batch_summarizer,
):
    """Test that batch mode generates citations from chunks."""
    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    publisher = batch_summarization_service.publisher

    batch_summarization_service.process_summarization(event_data)

    # Verify SummaryComplete events were published with citations
    assert publisher.publish.call_count == 2

    # Check that citations were generated from chunks
    for call in publisher.publish.call_args_list:
        event_data = call[1]["event"]["data"]
        citations = event_data["citations"]
        # Citations should be generated from chunks
        assert len(citations) > 0
        assert "message_id" in citations[0]
        assert "chunk_id" in citations[0]


def test_batch_job_failed_status(
    mock_document_store_batch,
):
    """Test handling of failed batch job status."""
    summarizer = Mock()
    summarizer.create_batch = Mock(return_value="batch-failed-123")
    
    # Mock batch status to return 'failed'
    summarizer.get_batch_status = Mock(return_value={
        "status": "failed",
        "request_counts": {"total": 2, "completed": 0, "failed": 2},
    })

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,
        batch_poll_interval_seconds=1,
        batch_timeout_hours=24,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    # Should raise RuntimeError for failed status
    with pytest.raises(RuntimeError, match="ended with status: failed"):
        service.process_summarization(event_data)


def test_batch_job_expired_status(
    mock_document_store_batch,
):
    """Test handling of expired batch job status."""
    summarizer = Mock()
    summarizer.create_batch = Mock(return_value="batch-expired-123")
    
    # Mock batch status to return 'expired'
    summarizer.get_batch_status = Mock(return_value={
        "status": "expired",
        "request_counts": {"total": 2, "completed": 0, "failed": 0},
    })

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,
        batch_poll_interval_seconds=1,
        batch_timeout_hours=24,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    # Should raise RuntimeError for expired status
    with pytest.raises(RuntimeError, match="ended with status: expired"):
        service.process_summarization(event_data)


def test_batch_job_timeout(
    mock_document_store_batch,
):
    """Test handling of batch job timeout."""
    summarizer = Mock()
    summarizer.create_batch = Mock(return_value="batch-timeout-123")
    
    # Mock batch status to always return 'in_progress'
    summarizer.get_batch_status = Mock(return_value={
        "status": "in_progress",
        "request_counts": {"total": 2, "completed": 0, "failed": 0},
    })

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,
        batch_poll_interval_seconds=1,
        batch_timeout_hours=0.0001,  # Very short timeout (~0.36 seconds)
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    # Should raise RuntimeError for timeout
    with pytest.raises(RuntimeError, match="did not complete within"):
        service.process_summarization(event_data)


def test_batch_polling_multiple_iterations(
    mock_document_store_batch,
):
    """Test that batch polling correctly iterates through multiple status checks."""
    summarizer = Mock()
    summarizer.create_batch = Mock(return_value="batch-polling-123")
    
    # Mock batch status to transition through states
    status_sequence = [
        {"status": "validating", "request_counts": {"total": 2, "completed": 0, "failed": 0}},
        {"status": "in_progress", "request_counts": {"total": 2, "completed": 1, "failed": 0}},
        {"status": "completed", "request_counts": {"total": 2, "completed": 2, "failed": 0}, "output_file_id": "file-123"},
    ]
    summarizer.get_batch_status = Mock(side_effect=status_sequence)
    
    # Mock retrieve results
    summarizer.retrieve_batch_results = Mock(return_value=[
        Summary(
            thread_id="thread-1",
            summary_markdown="Summary 1",
            citations=[],
            llm_backend="openai",
            llm_model="gpt-4o-mini",
            tokens_prompt=100,
            tokens_completion=50,
            latency_ms=0,
        ),
        Summary(
            thread_id="thread-2",
            summary_markdown="Summary 2",
            citations=[],
            llm_backend="openai",
            llm_model="gpt-4o-mini",
            tokens_prompt=110,
            tokens_completion=55,
            latency_ms=0,
        ),
    ])

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,
        batch_poll_interval_seconds=1,
        batch_timeout_hours=24,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    service.process_summarization(event_data)

    # Verify get_batch_status was called multiple times
    assert summarizer.get_batch_status.call_count == 3
    
    # Verify batch results were retrieved
    summarizer.retrieve_batch_results.assert_called_once()


def test_batch_size_exceeds_maximum(
    mock_document_store_batch,
):
    """Test that batch size validation raises error when exceeding maximum."""
    summarizer = Mock()
    summarizer.create_batch = Mock(return_value="batch-123")

    service = SummarizationService(
        document_store=mock_document_store_batch,
        vector_store=Mock(),
        publisher=Mock(),
        subscriber=Mock(),
        summarizer=summarizer,
        top_k=10,
        citation_count=10,
        batch_mode_enabled=True,
        batch_max_threads=1,  # Very low limit
        batch_poll_interval_seconds=1,
        batch_timeout_hours=24,
    )

    event_data = {
        "thread_ids": ["thread-1", "thread-2"],  # 2 threads > max of 1
        "top_k": 10,
        "prompt_template": "Summarize: {email_chunks}",
    }

    # Should raise ValueError for exceeding batch size
    with pytest.raises(ValueError, match="exceeds configured maximum"):
        service.process_summarization(event_data)
    
    # Verify batch was not created
    summarizer.create_batch.assert_not_called()
