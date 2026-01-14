# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for storage-agnostic archive handling (optional file_path)."""

import tempfile
from pathlib import Path

import pytest
from app.service import ParsingService
from copilot_archive_store import create_archive_store
from copilot_message_bus import create_publisher, create_subscriber
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store


def create_test_archive_store():
    """Create a test archive store with automatic temporary directory cleanup."""
    from copilot_config.generated.adapters.archive_store import (
        AdapterConfig_ArchiveStore,
        DriverConfig_ArchiveStore_Local,
    )
    tmpdir = tempfile.TemporaryDirectory()
    archive_store = create_archive_store(
        AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(archive_base_path=tmpdir.name),
        )
    )
    archive_store._tmpdir = tmpdir  # keep tempdir alive for store lifetime
    return archive_store


def create_validating_document_store():
    """Create an in-memory document store with document schema validation."""
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
    schema_provider = create_schema_provider(schema_dir=schema_dir, schema_type="documents")
    store = create_document_store(
        driver_name="inmemory",
        driver_config={"schema_provider": schema_provider},
        enable_validation=True,
    )
    store.connect()
    return store


def create_tracking_publisher():
    """Create a noop publisher that records published events."""
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


class TestStorageAgnosticArchives:
    """Test that parsing service handles archives without file_path."""

    @pytest.fixture
    def document_store(self):
        """Create in-memory document store."""
        return create_validating_document_store()


    @pytest.fixture
    def publisher(self):
        """Create noop publisher that tracks events."""
        return create_tracking_publisher()


    @pytest.fixture
    def subscriber(self):
        """Create noop subscriber."""
        return create_noop_subscriber()

    @pytest.fixture
    def service(self, document_store, publisher, subscriber):
        """Create parsing service."""
        return ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            archive_store=create_test_archive_store(),
        )

    def test_parsing_failed_event_without_file_path(self, service):
        """Test that ParsingFailed events can be published without file_path (truly omitted)."""
        # Publish a ParsingFailed event with None file_path
        service._publish_parsing_failed(
            archive_id="test123",
            file_path=None,
            error_message="Test error",
            error_type="TestError",
            messages_parsed_before_failure=0,
        )

        # Check that event was published WITHOUT file_path field
        events = service.publisher.published_events
        assert len(events) == 1

        event = events[0]
        assert event["routing_key"] == "parsing.failed"
        assert event["event"]["event_type"] == "ParsingFailed"

        # file_path should NOT be in event data (truly optional/omitted for storage-agnostic)
        data = event["event"]["data"]
        assert "file_path" not in data, "file_path should be omitted entirely for storage-agnostic backends"
        assert data["archive_id"] == "test123"
        assert data["error_message"] == "Test error"

    def test_parsing_failed_event_with_file_path(self, service):
        """Test that ParsingFailed events preserve file_path when provided."""
        # Publish a ParsingFailed event with actual file_path
        service._publish_parsing_failed(
            archive_id="test456",
            file_path="/data/archives/test.mbox",
            error_message="Test error",
            error_type="TestError",
            messages_parsed_before_failure=5,
        )

        # Check that event was published with actual file_path
        events = service.publisher.published_events
        assert len(events) == 1

        event = events[0]
        data = event["event"]["data"]
        assert data["file_path"] == "/data/archives/test.mbox"
        assert data["archive_id"] == "test456"

    def test_process_archive_without_file_path_in_event_data(self, service, tmp_path):
        """Test processing archive without file_path in ArchiveIngested event data."""
        # Create a test mbox file
        test_mbox = tmp_path / "test.mbox"
        test_mbox.write_text(
            "From test@example.com Mon Jan 1 00:00:00 2024\n"
            "From: test@example.com\n"
            "To: dev@example.com\n"
            "Subject: Test Message\n"
            "Message-ID: <test123@example.com>\n"
            "Date: Mon, 1 Jan 2024 00:00:00 +0000\n"
            "\n"
            "Test content\n"
        )

        # Store archive in archive store
        with open(test_mbox, 'rb') as f:
            content = f.read()

        archive_id = service.archive_store.store_archive(
            source_name="test-source",
            file_path=str(test_mbox),
            content=content,
        )

        # Create archive data WITHOUT file_path (storage-agnostic)
        archive_data = {
            "archive_id": archive_id,
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "https://example.com/archives",
            "file_size_bytes": len(content),
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
            # NOTE: no file_path field - this is the key test scenario
        }

        # Process should succeed without file_path
        service.process_archive(archive_data)

        # Verify messages were parsed and stored
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) > 0

        # Verify JSONParsed events were published
        json_parsed_events = [
            e for e in service.publisher.published_events
            if e["routing_key"] == "json.parsed"
        ]
        assert len(json_parsed_events) > 0

    def test_archive_not_found_publishes_event_without_file_path(self, service):
        """Test that archive not found errors publish ParsingFailed without file_path."""
        # Try to process archive that doesn't exist
        archive_data = {
            "archive_id": "nonexistent123",
            "source_name": "test-source",
            "source_type": "local",
            "source_url": "https://example.com/archives",
            "file_size_bytes": 1000,
            "file_hash_sha256": "abc123",
            "ingestion_started_at": "2024-01-01T00:00:00Z",
            "ingestion_completed_at": "2024-01-01T00:00:01Z",
            # No file_path
        }

        # Process should handle missing archive gracefully
        service.process_archive(archive_data)

        # Verify ParsingFailed event was published
        parsing_failed_events = [
            e for e in service.publisher.published_events
            if e["routing_key"] == "parsing.failed"
        ]
        assert len(parsing_failed_events) == 1

        event = parsing_failed_events[0]
        data = event["event"]["data"]
        assert data["archive_id"] == "nonexistent123"
        # file_path should be omitted entirely (storage-agnostic mode)
        assert "file_path" not in data, "file_path should be omitted for storage-agnostic backends"
        assert "not found" in data["error_message"].lower()
