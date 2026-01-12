# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for forward progress (startup requeue) logic in orchestrator service."""

from unittest.mock import Mock, patch

import pytest
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
def orchestration_service(mock_document_store, mock_publisher, mock_subscriber, mock_metrics_collector, temp_prompt_files):
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


class TestOrchestratorForwardProgress:
    """Test cases for orchestrator service forward progress logic."""

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_threads_ready_for_summarization(self, mock_requeue_class, orchestration_service, mock_document_store):
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
        def query_side_effect(collection, filter_dict, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks_with_embeddings
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service
        orchestration_service.start(enable_startup_requeue=True)

        # Verify threads were queried
        calls = mock_document_store.query_documents.call_args_list
        thread_query_call = [c for c in calls if c[1]['collection'] == 'threads'][0]
        assert thread_query_call[1]['filter_dict'] == {"summary_id": None}
        assert thread_query_call[1]['limit'] == 500

        # Verify chunks were queried in batch
        chunk_query_call = [c for c in calls if c[1]['collection'] == 'chunks'][0]
        assert chunk_query_call[1]['filter_dict'] == {"thread_id": {"$in": ["thread-001", "thread-002"]}}

        # Verify both threads were requeued
        assert mock_requeue_instance.publish_event.call_count == 2

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_skips_threads_without_all_embeddings(self, mock_requeue_class, orchestration_service, mock_document_store):
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

        def query_side_effect(collection, filter_dict, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        orchestration_service.start(enable_startup_requeue=True)

        # Only thread-001 should be requeued
        mock_requeue_instance.publish_event.assert_called_once()
        event_data = mock_requeue_instance.publish_event.call_args[1]['event_data']
        assert event_data['thread_ids'] == ['thread-001']

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_skips_threads_without_chunks(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that threads without any chunks are not requeued."""
        threads_without_summaries = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]

        # Only thread-001 has chunks
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
        ]

        def query_side_effect(collection, filter_dict, limit=None):
            if collection == "threads":
                return threads_without_summaries
            elif collection == "chunks":
                return chunks
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        orchestration_service.start(enable_startup_requeue=True)

        # Only thread-001 should be requeued
        mock_requeue_instance.publish_event.assert_called_once()
        event_data = mock_requeue_instance.publish_event.call_args[1]['event_data']
        assert event_data['thread_ids'] == ['thread-001']

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_publishes_correct_event_format(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that requeued events have correct format."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
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

        # Verify event format
        mock_requeue_instance.publish_event.assert_called_once()
        call_kwargs = mock_requeue_instance.publish_event.call_args[1]

        assert call_kwargs['event_type'] == 'SummarizationRequested'
        assert call_kwargs['routing_key'] == 'summarization.requested'

        event_data = call_kwargs['event_data']
        assert event_data['thread_ids'] == ['thread-001']
        assert event_data['archive_id'] == 'archive-1'

    @patch('copilot_startup.StartupRequeue')
    def test_no_requeue_when_all_threads_have_summaries(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that no requeue happens when all threads have summaries."""
        # No threads without summaries
        mock_document_store.query_documents.return_value = []

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        orchestration_service.start(enable_startup_requeue=True)

        # Verify no events were published
        mock_requeue_instance.publish_event.assert_not_called()

    @patch('copilot_startup.StartupRequeue')
    def test_no_requeue_when_disabled(self, mock_requeue_class, orchestration_service):
        """Test that requeue is skipped when disabled."""
        # Start service with requeue disabled
        orchestration_service.start(enable_startup_requeue=False)

        # Verify StartupRequeue was never instantiated
        mock_requeue_class.assert_not_called()

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_continues_on_import_error(self, mock_requeue_class, orchestration_service, mock_subscriber):
        """Test that service continues startup if copilot_startup is unavailable."""
        # Simulate ImportError when StartupRequeue is imported
        mock_requeue_class.side_effect = ImportError("Module not found")

        # Should not raise - service should continue startup
        orchestration_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_continues_on_query_error(self, mock_requeue_class, orchestration_service, mock_subscriber, mock_document_store, mock_metrics_collector):
        """Test that service continues startup even if query fails."""
        # Setup mock to raise exception during query
        mock_document_store.query_documents.side_effect = Exception("Database error")

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - service should continue startup
        orchestration_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

        # Verify error metrics were collected
        mock_metrics_collector.increment.assert_called_once()
        call_args = mock_metrics_collector.increment.call_args[0]
        assert call_args[0] == "startup_requeue_errors_total"

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_handles_threads_with_missing_thread_id(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that threads with missing thread_id are skipped."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": None, "summary_id": None, "archive_id": "archive-1"},  # Missing thread_id
            {"summary_id": None, "archive_id": "archive-1"},  # Missing thread_id field
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
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

        # Only thread-001 should be requeued
        mock_requeue_instance.publish_event.assert_called_once()
        event_data = mock_requeue_instance.publish_event.call_args[1]['event_data']
        assert event_data['thread_ids'] == ['thread-001']

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_batches_chunk_queries_efficiently(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that chunks are queried in a single batch for all threads."""
        threads = [
            {"thread_id": f"thread-{i:03d}", "summary_id": None, "archive_id": "archive-1"}
            for i in range(10)
        ]
        chunks = [
            {"thread_id": f"thread-{i:03d}", "embedding_generated": True, "_id": f"chunk-{i:03d}"}
            for i in range(10)
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

        # Verify chunks were queried in a single batch
        calls = mock_document_store.query_documents.call_args_list
        chunk_query_calls = [c for c in calls if c[1]['collection'] == 'chunks']
        assert len(chunk_query_calls) == 1

        # Verify all thread IDs were included
        chunk_filter = chunk_query_calls[0][1]['filter_dict']
        assert len(chunk_filter['thread_id']['$in']) == 10

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_respects_thread_limit(self, mock_requeue_class, orchestration_service, mock_document_store):
        """Test that requeue respects the 500 thread limit."""
        mock_document_store.query_documents.return_value = []

        orchestration_service.start(enable_startup_requeue=True)

        # Verify limit is set on thread query
        calls = mock_document_store.query_documents.call_args_list
        thread_query_call = [c for c in calls if c[1]['collection'] == 'threads'][0]
        assert thread_query_call[1]['limit'] == 500

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_emits_metrics(self, mock_requeue_class, orchestration_service, mock_document_store, mock_metrics_collector):
        """Test that requeue emits appropriate metrics."""
        threads = [
            {"thread_id": "thread-001", "summary_id": None, "archive_id": "archive-1"},
            {"thread_id": "thread-002", "summary_id": None, "archive_id": "archive-1"},
        ]
        chunks = [
            {"thread_id": "thread-001", "embedding_generated": True, "_id": "chunk-001"},
            {"thread_id": "thread-002", "embedding_generated": True, "_id": "chunk-002"},
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

        # Verify metrics were emitted (2 threads requeued)
        mock_metrics_collector.increment.assert_called_once_with(
            "startup_requeue_documents_total",
            2,
            tags={"collection": "threads"}
        )

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_continues_on_individual_publish_failure(self, mock_requeue_class, orchestration_service, mock_document_store):
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

        def query_side_effect(collection, filter_dict, limit=None):
            if collection == "threads":
                return threads
            elif collection == "chunks":
                return chunks
            return []

        mock_document_store.query_documents.side_effect = query_side_effect

        mock_requeue_instance = Mock()
        # Make second publish fail
        mock_requeue_instance.publish_event.side_effect = [
            None,  # First succeeds
            Exception("Network error"),  # Second fails
            None,  # Third succeeds
        ]
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - should continue with other threads
        orchestration_service.start(enable_startup_requeue=True)

        # Verify all 3 publish attempts were made
        assert mock_requeue_instance.publish_event.call_count == 3
