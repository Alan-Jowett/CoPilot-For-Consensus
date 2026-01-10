# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for parsing service."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.service import ParsingService
from copilot_archive_store import create_archive_store
from copilot_message_bus import EventPublisher, EventSubscriber, create_publisher, create_subscriber
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStore, create_document_store
from copilot_storage.validating_document_store import DocumentValidationError
from pymongo.errors import DuplicateKeyError

from .test_helpers import assert_valid_event_schema


def create_test_archive_store():
    """Create a test archive store with automatic temporary directory cleanup."""
    tmpdir = tempfile.TemporaryDirectory()
    archive_store = create_archive_store("local", {"base_path": tmpdir.name})
    archive_store._tmpdir = tmpdir  # keep tempdir alive for duration of store
    return archive_store


def create_validating_document_store():
    """Create an in-memory document store with schema validation enabled."""
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
    schema_provider = create_schema_provider(schema_dir=schema_dir, schema_type="documents")
    store = create_document_store(
        driver_name="inmemory",
        driver_config={"schema_provider": schema_provider},
        enable_validation=True,
    )
    store.connect()
    return store


def create_noop_publisher():
    """Create a noop publisher using the factory API."""
    publisher = create_publisher(driver_name="noop", driver_config={}, enable_validation=False)
    publisher.connect()
    return publisher


def create_noop_subscriber():
    """Create a noop subscriber using the factory API."""
    subscriber = create_subscriber(
        driver_name="noop",
        driver_config={"queue_name": "json.parsed"},
        enable_validation=False,
    )
    subscriber.connect()
    return subscriber


def prepare_archive_for_processing(archive_store, file_path, archive_id=None):
    """Store a file in the archive store and return storage-agnostic archive_data.
    
    Args:
        archive_store: ArchiveStore instance
        file_path: Path to the mbox file to store
        archive_id: Optional custom archive_id. WARNING: If provided and it does not match
                   the ID returned by the archive store, the store's ID will be used to avoid
                   mismatches between returned data and stored archives. Use archive_id=None
                   for normal tests; only provide a custom ID for error case testing.
    
    Returns:
        dict: Storage-agnostic archive_data suitable for process_archive()
    """
    with open(file_path, 'rb') as f:
        content = f.read()
    
    # Always store the archive and get the actual ID
    actual_archive_id = archive_store.store_archive(
        source_name="test-source",
        file_path=file_path,
        content=content,
    )
    
    # Ensure the archive_id in returned data matches what is stored
    if archive_id is not None and archive_id != actual_archive_id:
        logging.warning(
            "prepare_archive_for_processing: provided archive_id %s does not "
            "match stored archive_id %s; using stored ID instead",
            archive_id,
            actual_archive_id,
        )
    
    # Always use the ID returned by the archive store to avoid mismatches
    result_archive_id = actual_archive_id
    
    return {
        "archive_id": result_archive_id,
        "source_name": "test-source",
        "source_type": "local",
        "source_url": file_path,
        "file_path": file_path,
        "file_size_bytes": len(content),
        "file_hash_sha256": "abc123",  # Simplified for tests
        "ingestion_started_at": "2024-01-01T00:00:00Z",
        "ingestion_completed_at": "2024-01-01T00:00:01Z",
    }


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
        return create_validating_document_store()

    @pytest.fixture
    def publisher(self):
        """Create noop publisher."""
        return create_noop_publisher()

    @pytest.fixture
    def subscriber(self):
        """Create noop subscriber."""
        return create_noop_subscriber()

    @pytest.fixture
    def service(self, document_store, publisher, subscriber, temp_dir):
        """Create parsing service with temp directory for ArchiveStore."""
        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )
        yield service

    @pytest.fixture
    def mock_service(self, temp_dir):
        """Create a parsing service with mocked dependencies."""
        store = Mock(spec=DocumentStore)
        publisher = Mock(spec=EventPublisher)
        subscriber = Mock(spec=EventSubscriber)
        service = ParsingService(
            document_store=store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )
        yield service, store

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.document_store is not None
        assert service.publisher is not None
        assert service.subscriber is not None
        assert service.parser is not None
        assert service.thread_builder is not None

    def test_process_archive_success(self, service, sample_mbox_file):
        """Test successful archive processing."""
        # Store the file in ArchiveStore first
        with open(sample_mbox_file, 'rb') as f:
            content = f.read()
        archive_id = service.archive_store.store_archive(
            source_name="test-source",
            file_path=sample_mbox_file,
            content=content,
        )
        
        archive_data = {
            "archive_id": archive_id,
            "source_name": "test-source",
            "source_type": "local",
            "source_url": sample_mbox_file,
            "file_size_bytes": len(content),
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
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
        # Store the corrupted file in ArchiveStore first
        with open(corrupted_mbox_file, 'rb') as f:
            content = f.read()
        archive_id = service.archive_store.store_archive(
            source_name="test-source",
            file_path=corrupted_mbox_file,
            content=content,
        )
        
        archive_data = {
            "archive_id": archive_id,
            "source_name": "test-source",
            "source_type": "local",
            "source_url": corrupted_mbox_file,
            "file_size_bytes": len(content),
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
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
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "/nonexistent/file.mbox",
            "file_size_bytes": 0,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
        }

        # Should handle gracefully without crashing
        service.process_archive(archive_data)

        # No messages should be stored
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 0

    def test_message_persistence(self, service, sample_mbox_file):
        """Test that messages are persisted correctly."""
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

        service.process_archive(archive_data)

        # Retrieve messages
        messages = service.document_store.query_documents("messages", {})

        # Check required fields
        for msg in messages:
            assert "message_id" in msg
            assert "archive_id" in msg
            assert msg["archive_id"] == archive_data["archive_id"]  # Use the generated archive_id
            assert "thread_id" in msg
            assert "subject" in msg
            assert "from" in msg
            assert "body_normalized" in msg
            assert "draft_mentions" in msg
            assert "created_at" in msg

    def test_thread_persistence(self, service, sample_mbox_file):
        """Test that threads are persisted correctly."""
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

        service.process_archive(archive_data)

        # Retrieve threads
        threads = service.document_store.query_documents("threads", {})

        assert len(threads) == 1
        thread = threads[0]

        # Check required fields
        assert "thread_id" in thread
        assert "archive_id" in thread
        assert thread["archive_id"] == archive_data["archive_id"]
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
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

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
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

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
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)
        service.process_archive(archive_data)

        # Updated stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2
        assert stats["threads_created"] == 1
        assert stats["last_processing_time_seconds"] > 0

    def test_parsing_duration_always_positive(self, service, sample_mbox_file):
        """Test that parsing_duration_seconds is always >= 0.
        
        This test verifies the fix for negative duration issue caused by system clock skew.
        Using time.monotonic() ensures duration is never negative even if system clock
        is adjusted backwards (e.g., NTP sync, DST transitions, VM time sync).
        """
        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)
        
        service.process_archive(archive_data)
        
        # Duration in stats should be >= 0
        stats = service.get_stats()
        assert stats["last_processing_time_seconds"] >= 0, \
            f"Duration should never be negative, got {stats['last_processing_time_seconds']}"

    def test_parsing_duration_always_positive_on_error(self, service):
        """Test that parsing duration is >= 0 even when processing fails.
        
        This verifies that the error handling path also uses monotonic time
        and cannot produce negative durations.
        """
        archive_data = {
            "archive_id": "test-archive-error-duration",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "/nonexistent/file.mbox",
            "file_size_bytes": 0,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
        }
        
        # Process should handle error gracefully
        service.process_archive(archive_data)
        
        # Duration should still be >= 0 even after error
        stats = service.get_stats()
        assert stats["last_processing_time_seconds"] >= 0, \
            f"Duration should never be negative even on error, got {stats['last_processing_time_seconds']}"

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

    def test_store_messages_metrics_for_skipped_messages(self):
        """Metrics are collected for skipped messages with proper categorization."""
        store = Mock(spec=DocumentStore)
        publisher = Mock(spec=EventPublisher)
        subscriber = Mock(spec=EventSubscriber)
        metrics = Mock()
        
        service = ParsingService(
            document_store=store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics,
            archive_store=create_test_archive_store(),
        )
        
        # Test different skip reasons
        messages = [
            {"message_id": "m1", "body_raw": "some text", "attachments": []},  # duplicate
            {"message_id": "m2", "body_raw": "", "attachments": []},  # empty body
            {"message_id": "m3", "body_raw": "text", "attachments": ["file.pdf"]},  # other validation
            {"message_id": "m4"},  # success
        ]
        
        duplicate_error = DuplicateKeyError("duplicate key")
        empty_body_error = DocumentValidationError("messages", ["'' should be non-empty at 'body_normalized'"])
        other_validation_error = DocumentValidationError("messages", ["missing required field"])
        
        store.insert_document = Mock(side_effect=[
            duplicate_error,
            empty_body_error,
            other_validation_error,
            None,
        ])
        
        service._store_messages(messages)
        
        # Verify metrics were collected with correct reasons
        assert metrics.increment.call_count == 3
        
        # Check duplicate metric
        metrics.increment.assert_any_call(
            "parsing_messages_skipped_total",
            tags={"reason": "duplicate"}
        )
        
        # Check empty body metric
        metrics.increment.assert_any_call(
            "parsing_messages_skipped_total",
            tags={"reason": "empty_body"}
        )
        
        # Check other validation metric
        metrics.increment.assert_any_call(
            "parsing_messages_skipped_total",
            tags={"reason": "validation_error"}
        )

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

    def test_store_threads_metrics_for_skipped_threads(self):
        """Metrics are collected for skipped threads with proper categorization."""
        store = Mock(spec=DocumentStore)
        publisher = Mock(spec=EventPublisher)
        subscriber = Mock(spec=EventSubscriber)
        metrics = Mock()

        service = ParsingService(
            document_store=store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics,
            archive_store=create_test_archive_store(),
        )

        # Test different skip reasons
        threads = [
            {"thread_id": "t1"},  # duplicate
            {"thread_id": "t2"},  # validation error
            {"thread_id": "t3"},  # success
        ]

        duplicate_error = DuplicateKeyError("duplicate key")
        validation_error = DocumentValidationError("threads", ["missing required field"])

        store.insert_document = Mock(side_effect=[
            duplicate_error,
            validation_error,
            None,
        ])

        service._store_threads(threads)

        # Verify metrics were collected with correct reasons
        assert metrics.increment.call_count == 2

        # Check duplicate metric
        metrics.increment.assert_any_call(
            "parsing_threads_skipped_total",
            tags={"reason": "duplicate"}
        )

        # Check validation error metric
        metrics.increment.assert_any_call(
            "parsing_threads_skipped_total",
            tags={"reason": "validation_error"}
        )

    def test_event_publishing_on_success(self, document_store, subscriber, sample_mbox_file):
        """Test that JSONParsed events are published (one per message) on successful parsing."""
        mock_publisher = MockPublisher()
        mock_publisher.connect()

        service = ParsingService(
            document_store=document_store,
            publisher=mock_publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

        archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

        service.process_archive(archive_data)

        # Verify JSONParsed events were published (one per message)
        # sample_mbox_file contains 2 messages
        assert len(mock_publisher.published_events) == 2

        # Check first event
        event1 = mock_publisher.published_events[0]
        assert event1["exchange"] == "copilot.events"
        assert event1["routing_key"] == "json.parsed"
        assert event1["event"]["event_type"] == "JSONParsed"
        assert event1["event"]["data"]["archive_id"] == archive_data["archive_id"]  # Use generated ID
        assert event1["event"]["data"]["message_count"] == 1  # Single message per event
        assert len(event1["event"]["data"]["message_doc_ids"]) == 1

        # Check second event
        event2 = mock_publisher.published_events[1]
        assert event2["exchange"] == "copilot.events"
        assert event2["routing_key"] == "json.parsed"
        assert event2["event"]["event_type"] == "JSONParsed"
        assert event2["event"]["data"]["archive_id"] == archive_data["archive_id"]  # Use generated ID
        assert event2["event"]["data"]["message_count"] == 1  # Single message per event
        assert len(event2["event"]["data"]["message_doc_ids"]) == 1

        # Verify messages are different
        assert event1["event"]["data"]["message_doc_ids"][0] != event2["event"]["data"]["message_doc_ids"][0]

        # Verify parsing_duration_seconds is non-negative in published events
        assert event1["event"]["data"]["parsing_duration_seconds"] >= 0, \
            f"Published event should have non-negative duration, got {event1['event']['data']['parsing_duration_seconds']}"
        assert event2["event"]["data"]["parsing_duration_seconds"] >= 0, \
            f"Published event should have non-negative duration, got {event2['event']['data']['parsing_duration_seconds']}"

    def test_event_publishing_on_failure(self, document_store, subscriber):
        """Test that ParsingFailed event is published on parsing failure."""
        mock_publisher = MockPublisher()
        mock_publisher.connect()

        service = ParsingService(
            document_store=document_store,
            publisher=mock_publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

        archive_data = {
            "archive_id": "test-archive-10",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "/nonexistent/file.mbox",
            "file_size_bytes": 0,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
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
            archive_store=create_test_archive_store(),
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
        import hashlib
        
        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

        # Store file in archive store first (without custom archive_id so it gets stored correctly)
        archive_data = prepare_archive_for_processing(
            service.archive_store,
            sample_mbox_file,
        )

        # Compute actual file hash for document store validation
        with open(sample_mbox_file, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        # Create archive document in document store for status updates
        document_store.insert_document("archives", {
            "_id": archive_data["archive_id"],
            "file_hash": file_hash,
            "file_size_bytes": archive_data["file_size_bytes"],
            "source": archive_data["source_name"],
            "source_url": archive_data["source_url"],
            "format": "mbox",
            "ingestion_date": archive_data["ingestion_completed_at"],
            "status": "pending",
            "message_count": 0,
            "storage_backend": "local",
            "created_at": archive_data["ingestion_started_at"],
        })

        # Simulate receiving an event (storage-agnostic format)
        event = {
            "event_type": "ArchiveIngested",
            "data": archive_data
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
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    archive_data = prepare_archive_for_processing(service.archive_store, sample_mbox_file)

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
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    # Try to process a non-existent file
    archive_data = {
            "archive_id": "bbbbbbbbbbbbbbbb",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "/nonexistent/file.mbox",
            "file_size_bytes": 0,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
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
    import hashlib
    
    publisher = MockPublisher()
    publisher.connect()
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    # Store file in archive store first (without custom archive_id so it gets stored correctly)
    archive_data = prepare_archive_for_processing(
        service.archive_store,
        sample_mbox_file,
    )

    # Compute actual file hash for document store validation
    with open(sample_mbox_file, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Create archive document in document store for status updates
    document_store.insert_document("archives", {
        "_id": archive_data["archive_id"],
        "file_hash": file_hash,
        "file_size_bytes": archive_data["file_size_bytes"],
        "source": archive_data["source_name"],
        "source_url": archive_data["source_url"],
        "format": "mbox",
        "ingestion_date": archive_data["ingestion_completed_at"],
        "status": "pending",
        "message_count": 0,
        "storage_backend": "local",
        "created_at": archive_data["ingestion_started_at"],
    })

    # Simulate receiving an ArchiveIngested event (storage-agnostic format)
    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": archive_data
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
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
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
    """Test handling event where archive is not found in ArchiveStore.
    
    The service should handle this gracefully by logging an error and publishing
    a ParsingFailed event, rather than raising an exception.
    """
    publisher = MockPublisher()
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    # Event with archive_id that doesn't exist in ArchiveStore
    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "test-archive-nonexistent",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "test.mbox",
            "file_size_bytes": 100,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
        }
    }

    # Service should handle this gracefully (no exception)
    service._handle_archive_ingested(event)
    
    # Verify that a ParsingFailed event was published
    failed_events = [
        e for e in publisher.published_events
        if e["event"]["event_type"] == "ParsingFailed"
    ]
    assert len(failed_events) == 1
    
    # Verify the error message is appropriate
    failed_event = failed_events[0]["event"]
    assert "not found in ArchiveStore" in failed_event["data"]["error_message"]
    assert failed_event["data"]["archive_id"] == "test-archive-nonexistent"


def test_publish_json_parsed_with_publisher_failure(document_store):
    """Test that _publish_json_parsed raises exception when publisher fails."""
    class FailingPublisher(MockPublisher):
        """Publisher that raises exception to indicate failure."""
        def publish(self, exchange, routing_key, event):
            raise Exception("Publish failed")

    publisher = FailingPublisher()
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
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
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
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
    """Test that _handle_archive_ingested handles publisher failure for success event gracefully.
    
    When the publisher fails on json.parsed events, the service should:
    1. Catch the exception
    2. Update archive status to 'failed'
    3. Publish a ParsingFailed event
    4. Return gracefully (no exception raised)
    """
    import hashlib
    
    class FailingPublisher(MockPublisher):
        """Publisher that fails on json.parsed routing key."""
        def publish(self, exchange, routing_key, event):
            if routing_key == "json.parsed":
                raise Exception("Publish failed")
            # Call parent's publish to record the event
            return super().publish(exchange, routing_key, event)

    publisher = FailingPublisher()
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    # Store file in archive store first
    archive_data = prepare_archive_for_processing(
        service.archive_store,
        sample_mbox_file,
    )

    # Compute actual file hash for document store validation
    with open(sample_mbox_file, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Create archive document in document store for status updates
    document_store.insert_document("archives", {
        "_id": archive_data["archive_id"],
        "file_hash": file_hash,
        "file_size_bytes": archive_data["file_size_bytes"],
        "source": archive_data["source_name"],
        "source_url": archive_data["source_url"],
        "format": "mbox",
        "ingestion_date": archive_data["ingestion_completed_at"],
        "status": "pending",
        "message_count": 0,
        "storage_backend": "local",
        "created_at": archive_data["ingestion_started_at"],
    })

    event = {
        "event_type": "ArchiveIngested",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": archive_data
    }

    # Should handle publisher failure gracefully (no exception)
    service._handle_archive_ingested(event)
    
    # Verify that archive status was updated to 'failed'
    updated_archive = document_store.get_document("archives", archive_data["archive_id"])
    assert updated_archive is not None
    assert updated_archive["status"] == "failed"
    
    # Verify that a ParsingFailed event was published
    failed_events = [
        e for e in publisher.published_events
        if e["event"]["event_type"] == "ParsingFailed"
    ]
    assert len(failed_events) == 1
    assert "Publish failed" in failed_events[0]["event"]["data"]["error_message"]


def test_handle_archive_ingested_with_publish_parsing_failed_failure(document_store):
    """Test that _handle_archive_ingested handles publisher failure for failure event."""
    class FailingPublisher(MockPublisher):
        """Publisher that fails on parsing.failed routing key."""
        def publish(self, exchange, routing_key, event):
            if routing_key == "parsing.failed":
                raise Exception("Publish failed")
            return True

    publisher = FailingPublisher()
    subscriber = create_noop_subscriber()

    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
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

    subscriber = create_noop_subscriber()
    subscriber.connect()

    service = ParsingService(
        document_store=document_store,
        publisher=mock_publisher,
        subscriber=subscriber,
            archive_store=create_test_archive_store(),
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


def test_service_initialization_with_archive_store(document_store, publisher, subscriber):
    """Test that parsing service can be initialized with ArchiveStore."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_store = create_archive_store("local", {"base_path": tmpdir})

        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=archive_store,
        )

        assert service.archive_store is not None
        assert service.archive_store.__class__.__name__ == "LocalVolumeArchiveStore"


def test_process_archive_retrieves_from_archive_store(document_store, publisher, subscriber):
    """Test that process_archive retrieves content from ArchiveStore."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create ArchiveStore and store test content
        archive_store = create_archive_store("local", {"base_path": tmpdir})
        
        # Create a simple mbox file content
        mbox_content = b"""From test@example.com Mon Jan 01 00:00:00 2024
From: test@example.com
To: list@example.com
Subject: Test Message
Date: Mon, 01 Jan 2024 00:00:00 +0000
Message-ID: <test@example.com>

Test message body.
"""
        
        # Store the archive
        archive_id = archive_store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=mbox_content,
        )
        
        # Verify archive_id is valid (16-64 hex chars)
        assert archive_id is not None
        assert len(archive_id) >= 16
        assert len(archive_id) <= 64
        assert all(c in '0123456789abcdef' for c in archive_id)
        
        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=archive_store,
        )
        
        # Create archive record in document store to test status updates
        import hashlib
        file_hash = hashlib.sha256(mbox_content).hexdigest()
        document_store.insert_document("archives", {
            "_id": archive_id,
            "file_hash": file_hash,
            "file_size_bytes": len(mbox_content),
            "source": "test-source",
            "source_url": "test.mbox",
            "format": "mbox",
            "ingestion_date": "2024-01-01T00:00:00Z",
            "status": "pending",
            "message_count": 0,
            "storage_backend": "local",
            "created_at": "2024-01-01T00:00:00Z",
        })
        
        # Track temp files before processing
        temp_files_before = set(os.listdir(tempfile.gettempdir()))
        
        # Process archive with storage-agnostic event data (no file_path)
        archive_data = {
            "archive_id": archive_id,
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "test.mbox",
            "file_size_bytes": len(mbox_content),
            "file_hash_sha256": file_hash,
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
        }
        
        # Process should succeed (archive content retrieved from store)
        service.process_archive(archive_data)
        
        # Verify archive status was updated to completed
        updated_archive = document_store.get_document("archives", archive_id)
        assert updated_archive is not None
        assert updated_archive["status"] == "completed"
        assert updated_archive["message_count"] == 1
        
        # Verify no new parsing_ temp files remain (cleanup worked)
        temp_files_after = set(os.listdir(tempfile.gettempdir()))
        new_parsing_files = [f for f in temp_files_after - temp_files_before if f.startswith('parsing_')]
        assert len(new_parsing_files) == 0, f"Temporary files not cleaned up: {new_parsing_files}"
