# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for forward progress (startup requeue) logic in summarization service."""

from unittest.mock import Mock, patch

import pytest
from app.service import SummarizationService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    vector_store = Mock()
    return vector_store


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
    return summarizer


@pytest.fixture
def mock_metrics_collector():
    """Create a mock metrics collector."""
    metrics = Mock()
    metrics.increment = Mock()
    return metrics


@pytest.fixture
def summarization_service(mock_document_store, mock_vector_store, mock_publisher, mock_subscriber, mock_summarizer, mock_metrics_collector):
    """Create a summarization service instance."""
    return SummarizationService(
        document_store=mock_document_store,
        vector_store=mock_vector_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        summarizer=mock_summarizer,
        metrics_collector=mock_metrics_collector,
        top_k=12,
        llm_backend="ollama",
        llm_model="mistral",
        context_window_tokens=4096,
        prompt_template="Summarize: {email_chunks}",
    )


class TestSummarizationForwardProgress:
    """Test cases for summarization service forward progress logic."""

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_threads_without_summaries_on_startup(self, mock_requeue_class, summarization_service, mock_document_store, mock_publisher, mock_metrics_collector):
        """Test that threads without summaries are requeued on startup."""
        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=5)
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service with requeue enabled
        summarization_service.start(enable_startup_requeue=True)

        # Verify StartupRequeue was instantiated with correct parameters
        mock_requeue_class.assert_called_once_with(
            document_store=mock_document_store,
            publisher=mock_publisher,
            metrics_collector=mock_metrics_collector,
        )

        # Verify requeue_incomplete was called with correct parameters
        mock_requeue_instance.requeue_incomplete.assert_called_once()
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        
        assert call_kwargs['collection'] == 'threads'
        assert call_kwargs['query'] == {"summary_id": None}
        assert call_kwargs['event_type'] == 'SummarizationRequested'
        assert call_kwargs['routing_key'] == 'summarization.requested'
        assert call_kwargs['id_field'] == 'thread_id'
        assert call_kwargs['limit'] == 500
        assert callable(call_kwargs['build_event_data'])

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_builds_correct_event_data(self, mock_requeue_class, summarization_service):
        """Test that event data is built correctly from thread documents."""
        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service
        summarization_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs['build_event_data']

        # Test event data building
        test_doc = {
            "thread_id": "thread-abc123",
            "archive_id": "archive-xyz789",
            "summary_id": None,
        }

        event_data = build_event_data(test_doc)

        assert event_data['thread_ids'] == ["thread-abc123"]
        assert event_data['top_k'] == 12
        assert event_data['llm_backend'] == "ollama"
        assert event_data['llm_model'] == "mistral"
        assert event_data['context_window_tokens'] == 4096
        assert event_data['prompt_template'] == "Summarize: {email_chunks}"

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_uses_service_configuration(self, mock_requeue_class, mock_document_store, mock_vector_store, mock_publisher, mock_subscriber, mock_summarizer):
        """Test that requeue uses the service's configured parameters."""
        # Create service with custom config
        service = SummarizationService(
            document_store=mock_document_store,
            vector_store=mock_vector_store,
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            summarizer=mock_summarizer,
            top_k=20,
            llm_backend="azure",
            llm_model="gpt-4",
            context_window_tokens=8192,
            prompt_template="Custom prompt: {email_chunks}",
        )

        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        service.start(enable_startup_requeue=True)

        # Get the build_event_data function and test it
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs['build_event_data']

        test_doc = {"thread_id": "thread-001"}
        event_data = build_event_data(test_doc)

        assert event_data['top_k'] == 20
        assert event_data['llm_backend'] == "azure"
        assert event_data['llm_model'] == "gpt-4"
        assert event_data['context_window_tokens'] == 8192
        assert event_data['prompt_template'] == "Custom prompt: {email_chunks}"

    @patch('copilot_startup.StartupRequeue')
    def test_no_requeue_when_disabled(self, mock_requeue_class, summarization_service):
        """Test that requeue is skipped when disabled."""
        # Start service with requeue disabled
        summarization_service.start(enable_startup_requeue=False)

        # Verify StartupRequeue was never instantiated
        mock_requeue_class.assert_not_called()

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_continues_on_import_error(self, mock_requeue_class, summarization_service, mock_subscriber):
        """Test that service continues startup if copilot_startup is unavailable."""
        # Simulate ImportError when StartupRequeue is accessed
        mock_requeue_class.side_effect = ImportError("Module not found")

        # Should not raise - service should continue startup
        summarization_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_continues_on_error(self, mock_requeue_class, summarization_service, mock_subscriber):
        """Test that service continues startup even if requeue fails."""
        # Setup mock to raise exception
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(side_effect=Exception("Database error"))
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - service should continue startup
        summarization_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        mock_subscriber.subscribe.assert_called_once()

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_query_filters_by_null_summary_id(self, mock_requeue_class, summarization_service):
        """Test that requeue query only finds threads without summaries."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify query filters for null summary_id
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs['query'] == {"summary_id": None}

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_uses_correct_event_routing(self, mock_requeue_class, summarization_service):
        """Test that requeue uses correct event type and routing key."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify correct event type and routing
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs['event_type'] == 'SummarizationRequested'
        assert call_kwargs['routing_key'] == 'summarization.requested'

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_limit_prevents_overload(self, mock_requeue_class, summarization_service):
        """Test that requeue respects limit to prevent startup overload."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=500)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify limit is set appropriately
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs['limit'] == 500

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_uses_thread_id_field(self, mock_requeue_class, summarization_service):
        """Test that requeue uses thread_id as the document ID field."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify id_field is set to thread_id
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs['id_field'] == 'thread_id'

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_wraps_thread_id_in_list(self, mock_requeue_class, summarization_service):
        """Test that thread_id is wrapped in a list for the event data."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs['build_event_data']

        # Test that thread_id is wrapped in a list
        test_doc = {"thread_id": "single-thread-id"}
        event_data = build_event_data(test_doc)

        assert isinstance(event_data['thread_ids'], list)
        assert len(event_data['thread_ids']) == 1
        assert event_data['thread_ids'][0] == "single-thread-id"

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_handles_default_configuration(self, mock_requeue_class, mock_document_store, mock_vector_store, mock_publisher, mock_subscriber, mock_summarizer):
        """Test that requeue works with default configuration."""
        # Create service with defaults
        service = SummarizationService(
            document_store=mock_document_store,
            vector_store=mock_vector_store,
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            summarizer=mock_summarizer,
        )

        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        service.start(enable_startup_requeue=True)

        # Get the build_event_data function and verify defaults
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs['build_event_data']

        test_doc = {"thread_id": "thread-001"}
        event_data = build_event_data(test_doc)

        # Verify default values
        assert event_data['top_k'] == 12  # Default from __init__
        assert event_data['llm_backend'] == "local"  # Default from __init__
        assert event_data['llm_model'] == "mistral"  # Default from __init__
        assert event_data['context_window_tokens'] == 4096  # Default from __init__
        assert event_data['prompt_template'] == ""  # Default from __init__

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_subscribes_after_requeue(self, mock_requeue_class, summarization_service, mock_subscriber):
        """Test that service subscribes to events after requeue completes."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=10)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify requeue happened first
        mock_requeue_instance.requeue_incomplete.assert_called_once()
        
        # Verify subscription happened after
        mock_subscriber.subscribe.assert_called_once()
        call_kwargs = mock_subscriber.subscribe.call_args[1]
        assert call_kwargs['event_type'] == 'SummarizationRequested'
        assert call_kwargs['routing_key'] == 'summarization.requested'

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_called_on_each_start(self, mock_requeue_class, summarization_service):
        """Test that calling start multiple times requeues each time."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service multiple times
        summarization_service.start(enable_startup_requeue=True)
        summarization_service.start(enable_startup_requeue=True)

        # Verify requeue was called both times
        assert mock_requeue_instance.requeue_incomplete.call_count == 2

    @patch('copilot_startup.StartupRequeue')
    def test_requeue_respects_collection_name(self, mock_requeue_class, summarization_service):
        """Test that requeue queries the correct collection."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        summarization_service.start(enable_startup_requeue=True)

        # Verify collection is threads
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs['collection'] == 'threads'
