# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for parsing service."""

import logging
from unittest.mock import Mock

import pytest
from app.service import ParsingService
from copilot_events import EventPublisher, EventSubscriber, NoopPublisher, NoopSubscriber
from copilot_storage import DocumentStore, InMemoryDocumentStore
from copilot_storage.validating_document_store import DocumentValidationError
from pymongo.errors import DuplicateKeyError

from .test_helpers import assert_valid_event_schema


class MockPublisher:
    """Mock publisher that tracks published events."""

    def __init__(self):
        self.published_events = []
        self.connected = False

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def publish(self, exchange, routing_key, event):
        self.published_events.append({
            "exchange": exchange,
            "routing_key": routing_key,
            "event": event,
        })
        return True


class TestParsingService:
    """Integration tests for ParsingService."""

    @pytest.fixture
    def document_store(self):
        """Create in-memory document store."""
        store = InMemoryDocumentStore()
        store.connect()
        return store

    @pytest.fixture
    def publisher(self):
        """Create noop publisher."""
        pub = NoopPublisher()
        pub.connect()
        return pub

    @pytest.fixture
    def subscriber(self):
        """Create noop subscriber."""
        sub = NoopSubscriber()
        sub.connect()
        return sub

    @pytest.fixture
    def service(self, document_store, publisher, subscriber):
        """Create parsing service."""
        return ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
        )

    @pytest.fixture
    def mock_service(self):
        """Create a parsing service with mocked dependencies."""
        store = Mock(spec=DocumentStore)
        publisher = Mock(spec=EventPublisher)
        subscriber = Mock(spec=EventSubscriber)
        return ParsingService(
            document_store=store,
            publisher=publisher,
            subscriber=subscriber,
        ), store

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.document_store is not None
        assert service.publisher is not None
        assert service.subscriber is not None
        assert service.parser is not None
        assert service.thread_builder is not None

    def test_process_archive_success(self, service, sample_mbox_file):
        """Test successful archive processing."""
        archive_data = {
            "archive_id": "test-archive-1",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Check stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2
        assert stats["threads_created"] == 1
        assert stats["last_processing_time_seconds"] > 0

        # Check document store
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 2

        threads = service.document_store.query_documents("threads", {})
        assert len(threads) == 1

    def test_process_archive_with_corrupted_file(self, service, corrupted_mbox_file):
        """Test processing corrupted archive."""
        archive_data = {
            "archive_id": "test-archive-2",
            "file_path": corrupted_mbox_file,
        }

        # Should handle gracefully
        service.process_archive(archive_data)

        # No messages should be parsed from corrupted file
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 0

    def test_process_archive_missing_file(self, service):
        """Test processing nonexistent archive."""
        archive_data = {
            "archive_id": "test-archive-3",
            "file_path": "/nonexistent/file.mbox",
        }

        # Should handle gracefully without crashing
        service.process_archive(archive_data)

        # No messages should be stored
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 0

    def test_message_persistence(self, service, sample_mbox_file):
        """Test that messages are persisted correctly."""
        archive_data = {
            "archive_id": "test-archive-4",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Retrieve messages
        messages = service.document_store.query_documents("messages", {})

        # Check required fields
        for msg in messages:
            assert "message_id" in msg
            assert "archive_id" in msg
            assert msg["archive_id"] == "test-archive-4"
            assert "thread_id" in msg
            assert "subject" in msg
            assert "from" in msg
            assert "body_normalized" in msg
            assert "draft_mentions" in msg
            assert "created_at" in msg

    def test_thread_persistence(self, service, sample_mbox_file):
        """Test that threads are persisted correctly."""
        archive_data = {
            "archive_id": "test-archive-5",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Retrieve threads
        threads = service.document_store.query_documents("threads", {})

        assert len(threads) == 1
        thread = threads[0]

        # Check required fields
        assert "thread_id" in thread
        assert "archive_id" in thread
        assert thread["archive_id"] == "test-archive-5"
        assert "subject" in thread
        assert "participants" in thread
        assert "message_count" in thread
        assert thread["message_count"] == 2
        assert "draft_mentions" in thread
        assert "has_consensus" in thread
        assert "consensus_type" in thread
        assert "summary_id" in thread

    def test_draft_detection_integration(self, service, sample_mbox_file):
        """Test draft detection in full pipeline."""
        archive_data = {
            "archive_id": "test-archive-6",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Check messages for draft mentions
        messages = service.document_store.query_documents("messages", {})

        draft_mentions_found = []
        for msg in messages:
            draft_mentions_found.extend(msg["draft_mentions"])

        # Should have detected drafts from the sample messages
        assert len(draft_mentions_found) > 0
        assert any("draft-ietf-quic-transport" in d for d in draft_mentions_found)
        assert any("RFC" in d for d in draft_mentions_found)

    def test_thread_relationships(self, service, sample_mbox_file):
        """Test thread relationship building."""
        archive_data = {
            "archive_id": "test-archive-7",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Retrieve messages
        messages = service.document_store.query_documents("messages", {})

        # Both messages should be in the same thread
        thread_ids = [msg["thread_id"] for msg in messages]
        assert len(set(thread_ids)) == 1  # All same thread

        # The thread_id should be the root message's canonical _id
        root_msg = [m for m in messages if not m.get("in_reply_to")][0]
        assert all(tid == root_msg["_id"] for tid in thread_ids)

    def test_get_stats(self, service, sample_mbox_file):
        """Test statistics reporting."""
        # Initial stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 0
        assert stats["messages_parsed"] == 0
        assert stats["threads_created"] == 0

        # Process archive
        archive_data = {
            "archive_id": "test-archive-8",
            "file_path": sample_mbox_file,
        }
        service.process_archive(archive_data)

        # Updated stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2
        assert stats["threads_created"] == 1
        assert stats["last_processing_time_seconds"] > 0

    def test_store_messages_skips_duplicates_and_continues(self, mock_service, caplog):
        """Duplicate messages are skipped, logged, and processing continues."""
        service, store = mock_service
        messages = [
            {"message_id": "m1"},
            {"message_id": "m2"},
        ]
        store.insert_document = Mock(side_effect=[DuplicateKeyError("dup"), None])

        with caplog.at_level(logging.DEBUG):
            service._store_messages(messages)

        assert store.insert_document.call_count == 2
        assert "Skipping message m1 (DuplicateKeyError)" in caplog.text
        assert "Stored 1 messages, skipped 1 (duplicates/validation)" in caplog.text

    def test_store_messages_skips_validation_errors_and_continues(self, mock_service, caplog):
        """Validation errors are skipped, logged, and processing continues."""
        service, store = mock_service
        messages = [
            {"message_id": "m1"},
            {"message_id": "m2"},
        ]
        validation_error = DocumentValidationError("messages", ["bad doc"])
        store.insert_document = Mock(side_effect=[validation_error, None])

        with caplog.at_level(logging.DEBUG):
            service._store_messages(messages)

        assert store.insert_document.call_count == 2
        assert "Skipping message m1 (DocumentValidationError)" in caplog.text
        assert "Stored 1 messages, skipped 1 (duplicates/validation)" in caplog.text

    def test_store_messages_raises_on_transient_errors(self, mock_service):
        """Non-permanent errors are re-raised for retry handling."""
        service, store = mock_service
        store.insert_document = Mock(side_effect=Exception("boom"))

        with pytest.raises(Exception, match="boom"):
            service._store_messages([{"message_id": "m1"}])

    def test_store_threads_skips_duplicates_and_continues(self, mock_service, caplog):
        """Duplicate threads are skipped, logged, and processing continues."""
        service, store = mock_service
        threads = [
            {"thread_id": "t1"},
            {"thread_id": "t2"},
        ]
        store.insert_document = Mock(side_effect=[DuplicateKeyError("dup"), None])

        with caplog.at_level(logging.DEBUG):
            service._store_threads(threads)

        assert store.insert_document.call_count == 2
        assert "Skipping thread t1 (DuplicateKeyError)" in caplog.text
        assert "Stored 1 threads, skipped 1 (duplicates/validation)" in caplog.text

    def test_store_threads_skips_validation_errors_and_continues(self, mock_service, caplog):
        """Validation errors for threads are skipped and logged."""
        service, store = mock_service
        threads = [
            {"thread_id": "t1"},
            {"thread_id": "t2"},
        ]
        validation_error = DocumentValidationError("threads", ["bad thread"])
        store.insert_document = Mock(side_effect=[validation_error, None])

        with caplog.at_level(logging.DEBUG):
            service._store_threads(threads)

        assert store.insert_document.call_count == 2
        assert "Skipping thread t1 (DocumentValidationError)" in caplog.text
        assert "Stored 1 threads, skipped 1 (duplicates/validation)" in caplog.text

    def test_store_threads_raises_on_transient_errors(self, mock_service):
        """Non-permanent thread errors are re-raised for retries."""
        service, store = mock_service
        store.insert_document = Mock(side_effect=Exception("boom"))

        with pytest.raises(Exception, match="boom"):
            service._store_threads([{"thread_id": "t1"}])

    def test_event_publishing_on_success(self, document_store, subscriber, sample_mbox_file):
        """Test that JSONParsed events are published (one per message) on successful parsing."""
        mock_publisher = MockPublisher()
        mock_publisher.connect()

        service = ParsingService(
            document_store=document_store,
            publisher=mock_publisher,
            subscriber=subscriber,
        )

        archive_data = {
            "archive_id": "test-archive-9",
            "file_path": sample_mbox_file,
        }

        service.process_archive(archive_data)

        # Verify JSONParsed events were published (one per message)
        # sample_mbox_file contains 2 messages
        assert len(mock_publisher.published_events) == 2

        # Check first event
        event1 = mock_publisher.published_events[0]
        assert event1["exchange"] == "copilot.events"
        assert event1["routing_key"] == "json.parsed"
        assert event1["event"]["event_type"] == "JSONParsed"
        assert event1["event"]["data"]["archive_id"] == "test-archive-9"
        assert event1["event"]["data"]["message_count"] == 1  # Single message per event
        assert len(event1["event"]["data"]["message_doc_ids"]) == 1

        # Check second event
        event2 = mock_publisher.published_events[1]
        assert event2["exchange"] == "copilot.events"
        assert event2["routing_key"] == "json.parsed"
        assert event2["event"]["event_type"] == "JSONParsed"
        assert event2["event"]["data"]["archive_id"] == "test-archive-9"
        assert event2["event"]["data"]["message_count"] == 1  # Single message per event
        assert len(event2["event"]["data"]["message_doc_ids"]) == 1

        # Verify messages are different
        assert event1["event"]["data"]["message_doc_ids"][0] != event2["event"]["data"]["message_doc_ids"][0]

    def test_event_publishing_on_failure(self, document_store, subscriber):
        """Test that ParsingFailed event is published on parsing failure."""
        mock_publisher = MockPublisher()
        mock_publisher.connect()

        service = ParsingService(
            document_store=document_store,
            publisher=mock_publisher,
            subscriber=subscriber,
        )

        archive_data = {
            "archive_id": "test-archive-10",
            "file_path": "/nonexistent/file.mbox",
        }

        service.process_archive(archive_data)

        # Verify ParsingFailed event was published
        assert len(mock_publisher.published_events) == 1
        event = mock_publisher.published_events[0]
        assert event["exchange"] == "copilot.events"
        assert event["routing_key"] == "parsing.failed"
        assert event["event"]["event_type"] == "ParsingFailed"
        assert event["event"]["data"]["archive_id"] == "test-archive-10"
        assert "error_message" in event["event"]["data"]
        assert event["event"]["data"]["messages_parsed_before_failure"] == 0

    def test_event_subscription(self, document_store, publisher, subscriber):
        """Test that service subscribes to archive.ingested events."""
        # Create a mock subscriber to track subscription
        mock_subscriber = Mock()
        mock_subscriber.connect.return_value = True

        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=mock_subscriber,
        )

        # Start the service
        service.start()

        # Verify subscription was called
        mock_subscriber.subscribe.assert_called_once()
        call_args = mock_subscriber.subscribe.call_args
        assert call_args[1]["exchange"] == "copilot.events"
        assert call_args[1]["routing_key"] == "archive.ingested"
        assert call_args[1]["callback"] == service._handle_archive_ingested

    def test_handle_archive_ingested_event(self, document_store, publisher, subscriber, sample_mbox_file):
        """Test that _handle_archive_ingested processes events correctly."""
        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
        )

        # Simulate receiving an event
        event = {
            "event_type": "ArchiveIngested",
            "data": {
                "archive_id": "test-archive-11",
                "file_path": sample_mbox_file,
            }
        }

        service._handle_archive_ingested(event)

        # Verify the archive was processed
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_json_parsed_event_schema_validation(document_store, sample_mbox_file):
    """Test that JSONParsed events validate against schema."""
    publisher = MockPublisher()
    publisher.connect()
    subscriber = NoopSubscriber()
    subscriber.connect()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    archive_data = {
        "archive_id": "aaaaaaaaaaaaaaaa",
        "file_path": sample_mbox_file,
    }

    service.process_archive(archive_data)

    # Get published events
    json_parsed_events = [
        e for e in publisher.published_events
        if e["event"]["event_type"] == "JSONParsed"
    ]

    assert len(json_parsed_events) >= 1

    # Validate each event
    for event_record in json_parsed_events:
        assert_valid_event_schema(event_record["event"])


def test_parsing_failed_event_schema_validation(document_store):
    """Test that ParsingFailed events validate against schema."""
    publisher = MockPublisher()
    publisher.connect()
    subscriber = NoopSubscriber()
    subscriber.connect()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Try to process a non-existent file
    archive_data = {
        "archive_id": "bbbbbbbbbbbbbbbb",
        "file_path": "/nonexistent/file.mbox",
    }

    service.process_archive(archive_data)

    # Get published events
    failure_events = [
        e for e in publisher.published_events
        if e["event"]["event_type"] == "ParsingFailed"
    ]

    assert len(failure_events) >= 1

    # Validate each event
    for event_record in failure_events:
        assert_valid_event_schema(event_record["event"])


# ============================================================================
# Message Consumption Tests
# ============================================================================


def test_consume_archive_ingested_event(document_store, sample_mbox_file):
    """Test consuming an ArchiveIngested event."""
    publisher = MockPublisher()
    publisher.connect()
    subscriber = NoopSubscriber()
    subscriber.connect()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Simulate receiving an ArchiveIngested event
    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "cccccccccccccccc",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": sample_mbox_file,
            "file_path": sample_mbox_file,
            "file_size_bytes": 1234,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2023-10-15T12:00:00Z",
            "ingestion_completed_at": "2023-10-15T12:01:00Z",
        }
    }

    # Validate incoming event
    assert_valid_event_schema(event)

    # Process the event
    service._handle_archive_ingested(event)

    # Verify processing succeeded
    stats = service.get_stats()
    assert stats["archives_processed"] == 1
    assert stats["messages_parsed"] == 2

    # Verify JSONParsed event was published
    json_parsed_events = [
        e for e in publisher.published_events
        if e["event"]["event_type"] == "JSONParsed"
    ]
    assert len(json_parsed_events) >= 1


# ============================================================================
# Invalid Message Handling Tests
# ============================================================================


def test_handle_malformed_event_missing_data(document_store):
    """Test handling event with missing data field."""
    publisher = MockPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Event missing 'data' field
    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
    }

    # Service should raise an exception for missing data field
    with pytest.raises(KeyError):
        service._handle_archive_ingested(event)


def test_handle_event_missing_required_fields(document_store):
    """Test handling event with missing required fields in data."""
    publisher = MockPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Event missing required 'file_path' field
    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "test-archive",
        }
    }

    # Service should raise an exception for missing required fields
    with pytest.raises((KeyError, FileNotFoundError)):
        service._handle_archive_ingested(event)


def test_publish_json_parsed_with_publisher_failure(document_store):
    """Test that _publish_json_parsed raises exception when publisher fails."""
    class FailingPublisher(MockPublisher):
        """Publisher that raises exception to indicate failure."""
        def publish(self, exchange, routing_key, event):
            raise Exception("Publish failed")

    publisher = FailingPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Should raise exception when publisher fails on any message
    parsed_messages = [
        {"message_id": "msg-1", "_id": "mk-1", "thread_id": "thread-1"},
        {"message_id": "msg-2", "_id": "mk-2", "thread_id": "thread-1"},
    ]
    threads = [
        {"thread_id": "thread-1"},
    ]

    with pytest.raises(Exception) as exc_info:
        service._publish_json_parsed_per_message(
            archive_id="test-archive",
            parsed_messages=parsed_messages,
            threads=threads,
            duration=1.5
        )

    assert "Publish failed" in str(exc_info.value)


def test_publish_parsing_failed_with_publisher_failure(document_store):
    """Test that _publish_parsing_failed raises exception when publisher fails."""
    class FailingPublisher(MockPublisher):
        """Publisher that raises exception to indicate failure."""
        def publish(self, exchange, routing_key, event):
            raise Exception("Publish failed")

    publisher = FailingPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    # Should raise exception when publisher fails
    with pytest.raises(Exception) as exc_info:
        service._publish_parsing_failed(
            archive_id="test-archive",
            file_path="/path/to/file.mbox",
            error_message="Test error",
            error_type="ValueError",
            messages_parsed_before_failure=5
        )

    assert "Publish failed" in str(exc_info.value)


def test_handle_archive_ingested_with_publish_json_parsed_failure(document_store, sample_mbox_file):
    """Test that _handle_archive_ingested handles publisher failure for success event."""
    class FailingPublisher(MockPublisher):
        """Publisher that fails on json.parsed routing key."""
        def publish(self, exchange, routing_key, event):
            if routing_key == "json.parsed":
                raise Exception("Publish failed")
            return True

    publisher = FailingPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "test-archive",
            "file_path": sample_mbox_file,
        }
    }

    # Should raise exception when publisher fails on json.parsed event
    with pytest.raises(Exception):
        service._handle_archive_ingested(event)


def test_handle_archive_ingested_with_publish_parsing_failed_failure(document_store):
    """Test that _handle_archive_ingested handles publisher failure for failure event."""
    class FailingPublisher(MockPublisher):
        """Publisher that fails on parsing.failed routing key."""
        def publish(self, exchange, routing_key, event):
            if routing_key == "parsing.failed":
                raise Exception("Publish failed")
            return True

    publisher = FailingPublisher()
    subscriber = NoopSubscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )

    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-124",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "test-archive-fail",
            "file_path": "/nonexistent/path.mbox",  # This will cause processing to fail
        }
    }

    # Should raise exception when publisher fails on parsing.failed event
    with pytest.raises(Exception):
        service._handle_archive_ingested(event)


def test_publish_json_parsed_raises_on_missing_message_id(document_store):
    """Test that _publish_json_parsed_per_message raises on messages without message_id."""
    mock_publisher = MockPublisher()
    mock_publisher.connect()

    subscriber = NoopSubscriber()
    subscriber.connect()

    service = ParsingService(
        document_store=document_store,
        publisher=mock_publisher,
        subscriber=subscriber,
    )

    # Create messages with one missing _id
    parsed_messages = [
        {"message_id": "msg-1", "_id": "mk-1", "thread_id": "thread-1"},
        {"message_id": "msg-2", "thread_id": "thread-1"},  # Missing _id
        {"message_id": "msg-3", "_id": "mk-3", "thread_id": "thread-1"},
    ]
    threads = [{"thread_id": "thread-1"}]

    # Should raise exception due to invalid message
    with pytest.raises(ValueError) as exc_info:
        service._publish_json_parsed_per_message(
            archive_id="test-archive",
            parsed_messages=parsed_messages,
            threads=threads,
            duration=1.5
        )

    assert "_id" in str(exc_info.value)
    # Should have attempted to publish for the valid messages before the error
    assert len(mock_publisher.published_events) >= 1
