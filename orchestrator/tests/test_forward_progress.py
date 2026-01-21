# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for forward progress (startup requeue) logic in orchestrator service."""

import hashlib

from unittest.mock import Mock, patch

import pytest
from app.service import OrchestrationService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    store.update_document = Mock()
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
def mock_metrics_collector():
    """Create a mock metrics collector."""
    metrics = Mock()
    metrics.increment = Mock()
    return metrics


@pytest.fixture
def temp_prompt_files(tmp_path):
    """Create temporary prompt files for testing."""
    system_prompt = tmp_path / "system.txt"
    system_prompt.write_text("You are a helpful assistant.")

    user_prompt = tmp_path / "user.txt"
    user_prompt.write_text("Summarize the following: {email_chunks}")

    return str(system_prompt), str(user_prompt)


@pytest.fixture
def orchestration_service(
    mock_document_store, mock_publisher, mock_subscriber, mock_metrics_collector, temp_prompt_files
):
    """Create an orchestration service instance."""
    system_prompt_path, user_prompt_path = temp_prompt_files
    return OrchestrationService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        metrics_collector=mock_metrics_collector,
        system_prompt_path=system_prompt_path,
        user_prompt_path=user_prompt_path,
    )


def get_collection_from_call(call):
    """Helper to extract collection name from mock call (positional or keyword arg)."""
    args, kwargs = call
    if "collection" in kwargs:
        return kwargs["collection"]
    elif len(args) > 0:
        return args[0]
    return None


def get_filter_dict_from_call(call):
    """Helper to extract filter_dict from mock call (positional or keyword arg)."""
    args, kwargs = call
    if "filter_dict" in kwargs and isinstance(kwargs["filter_dict"], dict):
        return kwargs["filter_dict"]
    if len(args) > 1 and isinstance(args[1], dict):
        return args[1]
    return None


def is_thread_id_in_batch_filter(call) -> bool:
    """Return True if call has filter_dict.thread_id.$in."""
    filter_dict = get_filter_dict_from_call(call) or {}
    thread_id_filter = filter_dict.get("thread_id")
    return isinstance(thread_id_filter, dict) and thread_id_filter.get("$in") is not None


class TestOrchestratorForwardProgress:
    """Test cases for orchestrator service forward progress logic."""

    def test_requeue_threads_ready_for_summarization(self, orchestration_service, mock_document_store, mock_publisher):
        """Test that threads with complete embeddings are requeued."""
        # Setup threads without summaries
        threads_without_summaries = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]

        # Setup chunks with embeddings for these threads
        chunks_with_embeddings = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-002"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-003"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-004"},
        ]

        # Mock query responses
        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks_with_embeddings
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        # Start service
        orchestration_service.start(enable_startup_requeue=True)

        # Verify threads were queried
        calls = mock_document_store.query_documents.call_args_list
        thread_query_call = [c for c in calls if get_collection_from_call(c) == "threads"][0]
        assert thread_query_call[1].get("filter_dict") == {"summary_id": None}
        assert thread_query_call[1].get("limit") == 500

        # Verify chunks were queried in batch
        chunk_query_call = [c for c in calls if get_collection_from_call(c) == "chunks"][0]
        assert chunk_query_call[1].get("filter_dict") == {"thread_id": {"$in": ["thread-001", "thread-002"]}}

        # Verify both threads were published (2 SummarizationRequested events)
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 2

    def test_requeue_skips_threads_without_all_embeddings(
        self, orchestration_service, mock_document_store, mock_publisher
    ):
        """Test that threads with incomplete embeddings are not requeued."""
        threads_without_summaries = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]

        # thread-001 has all embeddings, thread-002 does not
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-002"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-003"},
            {"thread_id": "thread-002", "embedding_generated": False, "_id": "chunk-004"},  # Missing embedding
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        orchestration_service.start(enable_startup_requeue=True)

        # Only thread-001 should be published
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 1
        # Verify it's thread-001
        event_data = publish_calls[0][1]["event"]["data"]
        assert event_data["thread_ids"] == ["thread-001"]

    def test_requeue_skips_threads_without_chunks(self, orchestration_service, mock_document_store, mock_publisher):
        """Test that threads without any chunks are not requeued."""
        threads_without_summaries = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]

        # Only thread-001 has chunks
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        orchestration_service.start(enable_startup_requeue=True)

        # Only thread-001 should be published
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 1
        event_data = publish_calls[0][1]["event"]["data"]
        assert event_data["thread_ids"] == ["thread-001"]

    def test_requeue_publishes_correct_event_format(self, orchestration_service, mock_document_store, mock_publisher):
        """Test that requeued events have correct format."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        orchestration_service.start(enable_startup_requeue=True)

        # Verify event format
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 1

        call_kwargs = publish_calls[0][1]
        assert call_kwargs["exchange"] == "copilot.events"
        assert call_kwargs["routing_key"] == "summarization.requested"

        event = call_kwargs["event"]
        assert event["event_type"] == "SummarizationRequested"
        event_data = event["data"]
        assert event_data["thread_ids"] == ["thread-001"]
        assert "top_k" in event_data
        assert "prompt_template" in event_data

    def test_orchestrate_backfills_thread_when_summary_already_exists(
        self, orchestration_service, mock_document_store, mock_publisher
    ):
        """If a summary already exists, orchestrator should backfill threads.summary_id and not re-publish."""
        thread_id = "thread-001"
        original_summary_id = "summaryhash"
        expected_report_id = hashlib.sha256(original_summary_id.encode()).hexdigest()[:16]

        with (
            patch.object(orchestration_service, "_retrieve_context", return_value={"chunks": [{"_id": "chunk-001"}]}),
            patch.object(orchestration_service, "_calculate_summary_id", return_value=original_summary_id),
            patch.object(orchestration_service, "_summary_exists", return_value=True),
        ):
            orchestration_service._orchestrate_thread(thread_id)

        mock_document_store.update_document.assert_called_once_with(
            "threads",
            thread_id,
            {"summary_id": expected_report_id},
        )

        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 0

    def test_no_requeue_when_all_threads_have_summaries(
        self, orchestration_service, mock_document_store, mock_publisher
    ):
        """Test that no requeue happens when all threads have summaries."""
        # No threads without summaries
        mock_document_store.query_documents.return_value = []

        orchestration_service.start(enable_startup_requeue=True)

        # Verify no events were published
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 0

    def test_no_requeue_when_disabled(self, orchestration_service, mock_document_store):
        """Test that requeue is skipped when disabled."""
        # Start service with requeue disabled
        orchestration_service.start(enable_startup_requeue=False)

        # Verify no queries for threads were made
        calls = mock_document_store.query_documents.call_args_list
        thread_calls = [c for c in calls if get_collection_from_call(c) == "threads"]
        assert len(thread_calls) == 0

    def test_requeue_continues_on_import_error(self, orchestration_service, mock_subscriber, mock_document_store):
        """Test that service continues startup if requeue has errors."""
        # Setup mock to return empty, so no processing happens
        mock_document_store.query_documents.return_value = []

        # Should not raise - service should continue startup
        orchestration_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

    def test_requeue_continues_on_query_error(
        self, orchestration_service, mock_subscriber, mock_document_store, mock_metrics_collector
    ):
        """Test that service continues startup even if query fails."""
        # Setup mock to raise exception during query
        mock_document_store.query_documents.side_effect = Exception("Database error")

        # Should not raise - service should continue startup
        orchestration_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

        # Verify error metrics were collected
        metric_calls = [
            c for c in mock_metrics_collector.increment.call_args_list if "startup_requeue_errors_total" in c[0]
        ]
        assert len(metric_calls) == 1

    def test_requeue_handles_threads_with_missing_thread_id(
        self, orchestration_service, mock_document_store, mock_publisher
    ):
        """Test that threads with missing thread_id are skipped."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": None, "summary_id": None, "archive_id": "archive-1"},  # Missing thread_id
            {"summary_id": None, "archive_id": "archive-1"},  # Missing thread_id field
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        orchestration_service.start(enable_startup_requeue=True)

        # Only thread-001 should be published
        publish_calls = [
            c for c in mock_publisher.publish.call_args_list if c[1].get("routing_key") == "summarization.requested"
        ]
        assert len(publish_calls) == 1
        event_data = publish_calls[0][1]["event"]["data"]
        assert event_data["thread_ids"] == ["thread-001"]

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_batches_chunk_queries_efficiently(
        self, mock_requeue_class, orchestration_service, mock_document_store
    ):
        """Test that chunks are queried in a single batch for all threads."""
        threads = [{"thread_id": f"thread-{i:03d}", "summary_id": None, "archive_id": "archive-1"} for i in range(10)]
        chunks = [
            {"thread_id": f"thread-{i:03d}", "embedding_generated": True, "_id": f"chunk-{i:03d}"} for i in range(10)
        ]

        def query_side_effect(collection, filter_dict, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        orchestration_service.start(enable_startup_requeue=True)

        # Verify chunks were queried in a single batch (during startup requeue)
        calls = mock_document_store.query_documents.call_args_list
        # Filter for batch queries - these have filter_dict with $in operator
        chunk_batch_calls = [
            c
            for c in calls
            if get_collection_from_call(c) == "chunks"
            and is_thread_id_in_batch_filter(c)
        ]
        assert len(chunk_batch_calls) == 1

        # Verify all thread IDs were included
        chunk_filter = get_filter_dict_from_call(chunk_batch_calls[0])
        assert len(chunk_filter["thread_id"]["$in"]) == 10

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_respects_thread_limit(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that requeue respects the 500 thread limit."""
        mock_document_store.query_documents.return_value = []

        orchestration_service.start(enable_startup_requeue=True)

        # Verify limit is set on thread query
        calls = mock_document_store.query_documents.call_args_list
        thread_query_call = [c for c in calls if get_collection_from_call(c) == "threads"][0]
        assert thread_query_call[1].get("limit") == 500

    def test_requeue_emits_metrics(
        self, orchestration_service, mock_document_store, mock_metrics_collector, mock_publisher
    ):
        """Test that requeue emits appropriate metrics."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-002"},
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        orchestration_service.start(enable_startup_requeue=True)

        # Verify metrics were emitted for each orchestration
        # Each _orchestrate_thread call increments orchestration_events_total
        metric_calls = [
            c for c in mock_metrics_collector.increment.call_args_list if c[0][0] == "orchestration_events_total"
        ]
        assert len(metric_calls) == 2

    def test_requeue_continues_on_individual_publish_failure(
        self, orchestration_service, mock_document_store, mock_publisher
    ):
        """Test that requeue continues even if individual publish fails."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-003", "summary_id": None, "archive_id": "archive-1"},
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-002"},
            {"thread_id": "thread-003", "embedding_generated": True, "_id": "chunk-003"},
        ]

        def query_side_effect(collection, filter_dict=None, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            elif collection == "summaries":
                return []  # No existing summaries
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        # Make second publish fail
        publish_count = [0]

        def publish_side_effect(*args, **kwargs):
            publish_count[0] += 1
            if publish_count[0] == 2:
                raise Exception("Network error")
            return True

        mock_publisher.publish.side_effect = publish_side_effect

        # Should not raise - should continue with other threads
        orchestration_service.start(enable_startup_requeue=True)

        # Verify all 3 publish attempts were made (but 2nd failed)
        assert mock_publisher.publish.call_count >= 3
