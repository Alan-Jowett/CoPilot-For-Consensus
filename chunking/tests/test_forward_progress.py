# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for forward progress (startup requeue) logic in chunking service."""

from unittest.mock import Mock, patch

import pytest
from app.service import ChunkingService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    store.aggregate_documents = Mock(return_value=[])
    store.insert_document = Mock()
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
    chunker = Mock()
    chunker.chunk = Mock(return_value=[])
    return chunker


@pytest.fixture
def mock_metrics_collector():
    """Create a mock metrics collector."""
    metrics = Mock()
    metrics.increment = Mock()
    return metrics


@pytest.fixture
def chunking_service(mock_document_store, mock_publisher, mock_subscriber, mock_chunker, mock_metrics_collector):
    """Create a chunking service instance."""
    return ChunkingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=mock_chunker,
        metrics_collector=mock_metrics_collector,
    )


class TestChunkingForwardProgress:
    """Test cases for chunking service forward progress logic."""

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_messages_without_chunks_on_startup(
        self, mock_requeue_class, chunking_service, mock_document_store, mock_publisher, mock_metrics_collector
    ):
        """Test that messages without chunks are requeued on startup."""
        # Setup mock document store with aggregation support
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1", "body_normalized": "Test message 1"},
            {"_id": "msg-002", "archive_id": "archive-1", "body_normalized": "Test message 2"},
            {"_id": "msg-003", "archive_id": "archive-2", "body_normalized": "Test message 3"},
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service with requeue enabled
        chunking_service.start(enable_startup_requeue=True)

        # Verify aggregation was called with correct pipeline
        mock_document_store.aggregate_documents.assert_called_once()
        call_kwargs = mock_document_store.aggregate_documents.call_args[1]

        assert call_kwargs["collection"] == "messages"
        pipeline = call_kwargs["pipeline"]

        # Verify pipeline structure
        assert len(pipeline) == 4
        assert pipeline[0]["$match"] == {"_id": {"$exists": True}}
        assert pipeline[1]["$lookup"]["from"] == "chunks"
        assert pipeline[1]["$lookup"]["localField"] == "_id"
        assert pipeline[1]["$lookup"]["foreignField"] == "message_doc_id"
        assert pipeline[2]["$match"] == {"chunks": {"$eq": []}}
        assert pipeline[3]["$limit"] == 1000

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_groups_messages_by_archive(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that messages are grouped by archive_id for efficient requeue."""
        # Setup messages from different archives
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1"},
            {"_id": "msg-002", "archive_id": "archive-1"},
            {"_id": "msg-003", "archive_id": "archive-2"},
            {"_id": "msg-004", "archive_id": "archive-2"},
            {"_id": "msg-005", "archive_id": "archive-3"},
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service
        chunking_service.start(enable_startup_requeue=True)

        # Verify publish_event was called for each archive
        assert mock_requeue_instance.publish_event.call_count == 3

        # Verify grouping correctness
        calls = mock_requeue_instance.publish_event.call_args_list

        # Check that we have the right number of messages per archive
        event_data_list = [call[1]["event_data"] for call in calls]

        # Find events for each archive
        archive_1_events = [ed for ed in event_data_list if ed["archive_id"] == "archive-1"]
        archive_2_events = [ed for ed in event_data_list if ed["archive_id"] == "archive-2"]
        archive_3_events = [ed for ed in event_data_list if ed["archive_id"] == "archive-3"]

        assert len(archive_1_events) == 1
        assert len(archive_2_events) == 1
        assert len(archive_3_events) == 1

        assert len(archive_1_events[0]["message_doc_ids"]) == 2
        assert len(archive_2_events[0]["message_doc_ids"]) == 2
        assert len(archive_3_events[0]["message_doc_ids"]) == 1

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_publishes_correct_event_format(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that requeued events have correct format."""
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1"},
            {"_id": "msg-002", "archive_id": "archive-1"},
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        chunking_service.start(enable_startup_requeue=True)

        # Verify publish_event was called with correct parameters
        mock_requeue_instance.publish_event.assert_called_once()
        call_kwargs = mock_requeue_instance.publish_event.call_args[1]

        assert call_kwargs["event_type"] == "JSONParsed"
        assert call_kwargs["routing_key"] == "json.parsed"

        event_data = call_kwargs["event_data"]
        assert event_data["archive_id"] == "archive-1"
        assert event_data["message_doc_ids"] == ["msg-001", "msg-002"]
        assert event_data["message_count"] == 2

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_skips_messages_with_invalid_ids(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that messages with missing/invalid IDs are skipped."""
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1"},
            {"_id": None, "archive_id": "archive-1"},  # Invalid _id
            {"archive_id": "archive-1"},  # Missing _id
            {"_id": "msg-002", "archive_id": None},  # Invalid archive_id
            {"_id": "msg-003"},  # Missing archive_id
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        chunking_service.start(enable_startup_requeue=True)

        # Only msg-001 should be requeued
        mock_requeue_instance.publish_event.assert_called_once()
        event_data = mock_requeue_instance.publish_event.call_args[1]["event_data"]
        assert event_data["message_doc_ids"] == ["msg-001"]

    @patch("copilot_startup.StartupRequeue")
    def test_no_requeue_when_all_messages_have_chunks(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that no requeue happens when all messages have chunks."""
        # No unchunked messages
        mock_document_store.aggregate_documents.return_value = []

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        chunking_service.start(enable_startup_requeue=True)

        # Verify no events were published
        mock_requeue_instance.publish_event.assert_not_called()

    @patch("copilot_startup.StartupRequeue")
    def test_no_requeue_when_disabled(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that requeue is skipped when disabled."""
        # Start service with requeue disabled
        chunking_service.start(enable_startup_requeue=False)

        # Verify aggregation was never called
        mock_document_store.aggregate_documents.assert_not_called()

        # Verify StartupRequeue was never instantiated
        mock_requeue_class.assert_not_called()

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_continues_on_import_error(
        self, mock_requeue_class, chunking_service, mock_subscriber, mock_document_store
    ):
        """Test that service continues startup if copilot_startup is unavailable."""
        # Set up aggregation to return some results
        mock_document_store.aggregate_documents.return_value = [{"_id": "msg-001", "archive_id": "archive-1"}]

        # Simulate ImportError when StartupRequeue is imported
        mock_requeue_class.side_effect = ImportError("Module not found")

        # Should not raise - service should continue startup
        chunking_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        assert mock_subscriber.subscribe.call_count == 2

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_continues_on_aggregation_error(
        self, mock_requeue_class, chunking_service, mock_subscriber, mock_document_store, mock_metrics_collector
    ):
        """Test that service continues startup even if aggregation fails."""
        # Setup mock to raise exception during aggregation
        mock_document_store.aggregate_documents.side_effect = Exception("Database error")

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - service should continue startup
        chunking_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        assert mock_subscriber.subscribe.call_count == 2

        # Verify error metrics were collected
        mock_metrics_collector.increment.assert_called_once()
        call_args = mock_metrics_collector.increment.call_args[0]
        assert call_args[0] == "startup_requeue_errors_total"

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_handles_missing_aggregation_support(
        self, mock_requeue_class, chunking_service, mock_document_store
    ):
        """Test that requeue gracefully handles stores without aggregation."""
        # Remove aggregate_documents method to simulate unsupported store
        delattr(mock_document_store, "aggregate_documents")

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - should log warning and continue
        chunking_service.start(enable_startup_requeue=True)

        # Verify no publish attempts
        mock_requeue_instance.publish_event.assert_not_called()

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_respects_limit(self, mock_requeue_class, chunking_service, mock_document_store):
        """Test that requeue respects the 1000 document limit."""
        mock_document_store.aggregate_documents.return_value = []

        chunking_service.start(enable_startup_requeue=True)

        # Verify limit is set in pipeline
        call_kwargs = mock_document_store.aggregate_documents.call_args[1]
        pipeline = call_kwargs["pipeline"]
        limit_stage = pipeline[-1]
        assert "$limit" in limit_stage
        assert limit_stage["$limit"] == 1000

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_emits_metrics(
        self, mock_requeue_class, chunking_service, mock_document_store, mock_metrics_collector
    ):
        """Test that requeue emits appropriate metrics."""
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1"},
            {"_id": "msg-002", "archive_id": "archive-1"},
            {"_id": "msg-003", "archive_id": "archive-2"},
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        mock_requeue_instance = Mock()
        mock_requeue_class.return_value = mock_requeue_instance

        chunking_service.start(enable_startup_requeue=True)

        # Verify metrics were emitted (3 messages requeued)
        mock_metrics_collector.increment.assert_called_once_with(
            "startup_requeue_documents_total", 3, tags={"collection": "messages"}
        )

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_continues_on_individual_publish_failure(
        self, mock_requeue_class, chunking_service, mock_document_store
    ):
        """Test that requeue continues even if individual publish fails."""
        unchunked_messages = [
            {"_id": "msg-001", "archive_id": "archive-1"},
            {"_id": "msg-002", "archive_id": "archive-2"},
            {"_id": "msg-003", "archive_id": "archive-3"},
        ]
        mock_document_store.aggregate_documents.return_value = unchunked_messages

        mock_requeue_instance = Mock()
        # Make second publish fail
        mock_requeue_instance.publish_event.side_effect = [
            None,  # First succeeds
            Exception("Network error"),  # Second fails
            None,  # Third succeeds
        ]
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - should continue with other archives
        chunking_service.start(enable_startup_requeue=True)

        # Verify all 3 publish attempts were made
        assert mock_requeue_instance.publish_event.call_count == 3
