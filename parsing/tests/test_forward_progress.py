# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for forward progress (startup requeue) logic in parsing service."""

import logging
from unittest.mock import Mock, patch

import pytest
from app.service import ParsingService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.query_documents = Mock(return_value=[])
    store.update_document = Mock()
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
def mock_archive_store():
    """Create a mock archive store."""
    archive_store = Mock()
    archive_store.get_archive = Mock(return_value=b"mock archive content")
    return archive_store


@pytest.fixture
def mock_metrics_collector():
    """Create a mock metrics collector."""
    metrics = Mock()
    metrics.increment = Mock()
    return metrics


@pytest.fixture
def parsing_service(mock_document_store, mock_publisher, mock_subscriber, mock_archive_store, mock_metrics_collector):
    """Create a parsing service instance."""
    return ParsingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        metrics_collector=mock_metrics_collector,
        archive_store=mock_archive_store,
    )


class TestParsingForwardProgress:
    """Test cases for parsing service forward progress logic."""

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_incomplete_archives_on_startup(
        self, mock_requeue_class, parsing_service, mock_document_store, mock_publisher, mock_metrics_collector
    ):
        """Test that incomplete archives are requeued on startup."""
        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=3)
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service with requeue enabled
        parsing_service.start(enable_startup_requeue=True)

        # Verify StartupRequeue was instantiated with correct parameters
        mock_requeue_class.assert_called_once_with(
            document_store=mock_document_store,
            publisher=mock_publisher,
            metrics_collector=mock_metrics_collector,
        )

        # Verify requeue_incomplete was called with correct parameters
        mock_requeue_instance.requeue_incomplete.assert_called_once()
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]

        assert call_kwargs["collection"] == "archives"
        assert call_kwargs["query"] == {"status": {"$in": ["pending", "processing"]}}
        assert call_kwargs["event_type"] == "ArchiveIngested"
        assert call_kwargs["routing_key"] == "archive.ingested"
        assert call_kwargs["id_field"] == "archive_id"
        assert call_kwargs["limit"] == 1000
        assert callable(call_kwargs["build_event_data"])

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_builds_correct_event_data(self, mock_requeue_class, parsing_service):
        """Test that event data is built correctly from archive documents."""
        # Setup mock requeue instance
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        # Start service
        parsing_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs["build_event_data"]

        # Test event data building
        test_doc = {
            "archive_id": "test-archive-123",
            "_id": "fallback-id",
            "source": "test-source",
            "source_type": "local",
            "source_url": "file:///path/to/archive.mbox",
            "file_size_bytes": 1024,
            "file_hash": "abc123def456",
            "created_at": "2024-01-01T00:00:00Z",
            "ingestion_date": "2024-01-01T01:00:00Z",
        }

        event_data = build_event_data(test_doc)

        assert event_data["archive_id"] == "test-archive-123"
        assert event_data["source_name"] == "test-source"
        assert event_data["source_type"] == "local"
        assert event_data["source_url"] == "file:///path/to/archive.mbox"
        assert event_data["file_size_bytes"] == 1024
        assert event_data["file_hash_sha256"] == "abc123def456"
        assert event_data["ingestion_started_at"] == "2024-01-01T00:00:00Z"
        assert event_data["ingestion_completed_at"] == "2024-01-01T01:00:00Z"

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_handles_missing_archive_id(self, mock_requeue_class, parsing_service):
        """Test that missing archive_id falls back to _id field."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs["build_event_data"]

        # Test with missing archive_id
        test_doc = {
            "_id": "fallback-id-456",
            "source": "test-source",
            "source_type": "local",
        }

        event_data = build_event_data(test_doc)
        assert event_data["archive_id"] == "fallback-id-456"

    @patch("copilot_startup.StartupRequeue")
    def test_no_requeue_when_disabled(self, mock_requeue_class, parsing_service):
        """Test that requeue is skipped when disabled."""
        # Start service with requeue disabled
        parsing_service.start(enable_startup_requeue=False)

        # Verify StartupRequeue was never instantiated
        mock_requeue_class.assert_not_called()

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_continues_on_import_error(self, mock_requeue_class, parsing_service, mock_subscriber):
        """Test that service continues startup if copilot_startup is unavailable."""
        # Simulate ImportError when StartupRequeue is accessed
        mock_requeue_class.side_effect = ImportError("Module not found")

        # Should not raise - service should continue startup
        parsing_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        assert mock_subscriber.subscribe.call_count == 2

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_continues_on_error(self, mock_requeue_class, parsing_service, mock_subscriber):
        """Test that service continues startup even if requeue fails."""
        # Setup mock to raise exception
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(side_effect=Exception("Database error"))
        mock_requeue_class.return_value = mock_requeue_instance

        # Should not raise - service should continue startup
        parsing_service.start(enable_startup_requeue=True)

        # Verify subscription still happened
        assert mock_subscriber.subscribe.call_count == 2

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_respects_query_status_filter(self, mock_requeue_class, parsing_service):
        """Test that only pending and processing archives are queried."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Verify query includes both pending and processing statuses
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        expected_query = {"status": {"$in": ["pending", "processing"]}}
        assert call_kwargs["query"] == expected_query

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_uses_correct_event_routing(self, mock_requeue_class, parsing_service):
        """Test that requeue uses correct event type and routing key."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=0)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Verify correct event type and routing
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs["event_type"] == "ArchiveIngested"
        assert call_kwargs["routing_key"] == "archive.ingested"

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_limit_prevents_overload(self, mock_requeue_class, parsing_service):
        """Test that requeue respects limit to prevent startup overload."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1000)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Verify limit is set appropriately
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        assert call_kwargs["limit"] == 1000

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_handles_legacy_archives_without_source_type(self, mock_requeue_class, parsing_service, caplog):
        """Test that legacy archives missing source_type are handled with default value."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=1)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs["build_event_data"]

        # Test with legacy document missing source_type
        legacy_doc = {
            "archive_id": "legacy-archive-001",
            "source": "legacy-source",
            # source_type is missing (legacy document)
            "source_url": "file:///legacy/archive.mbox",
            "file_size_bytes": 2048,
            "file_hash": "legacy123",
            "created_at": "2023-01-01T00:00:00Z",
            "ingestion_date": "2023-01-01T01:00:00Z",
        }

        # Should not raise - should default to 'local'
        with caplog.at_level(logging.WARNING):
            event_data = build_event_data(legacy_doc)

        assert event_data["archive_id"] == "legacy-archive-001"
        assert event_data["source_name"] == "legacy-source"
        assert event_data["source_type"] == "local"  # Defaults to 'local' for legacy docs
        assert event_data["source_url"] == "file:///legacy/archive.mbox"
        assert event_data["file_size_bytes"] == 2048
        
        # Verify warning is logged for legacy document
        assert "Archive legacy-archive-001 missing 'source_type' field (legacy document)" in caplog.text
        assert "Defaulting to 'local'" in caplog.text

    @patch("copilot_startup.StartupRequeue")
    def test_requeue_handles_mixed_valid_and_legacy_archives(self, mock_requeue_class, parsing_service, caplog):
        """Test that requeue handles a mix of valid and legacy archive documents."""
        mock_requeue_instance = Mock()
        mock_requeue_instance.requeue_incomplete = Mock(return_value=2)
        mock_requeue_class.return_value = mock_requeue_instance

        parsing_service.start(enable_startup_requeue=True)

        # Get the build_event_data function
        call_kwargs = mock_requeue_instance.requeue_incomplete.call_args[1]
        build_event_data = call_kwargs["build_event_data"]

        # Test with valid document
        valid_doc = {
            "archive_id": "valid-archive-001",
            "source": "modern-source",
            "source_type": "rsync",
        }

        # Test with legacy document
        legacy_doc = {
            "archive_id": "legacy-archive-002",
            "source": "legacy-source",
            # source_type is missing
        }

        # Valid document should work without warning
        with caplog.at_level(logging.WARNING):
            caplog.clear()
            valid_data = build_event_data(valid_doc)
        assert valid_data["source_type"] == "rsync"
        assert "missing 'source_type' field" not in caplog.text

        # First legacy document should log WARNING
        with caplog.at_level(logging.WARNING):
            caplog.clear()
            legacy_data = build_event_data(legacy_doc)
        assert legacy_data["source_type"] == "local"
        assert "Archive legacy-archive-002 missing 'source_type' field (legacy document)" in caplog.text
        assert "Defaulting to 'local'" in caplog.text
        
        # Second legacy document should log at INFO level (rate-limited)
        legacy_doc2 = {
            "archive_id": "legacy-archive-003",
            "source": "legacy-source",
            # source_type is missing
        }
        with caplog.at_level(logging.INFO):
            caplog.clear()
            legacy_data2 = build_event_data(legacy_doc2)
        assert legacy_data2["source_type"] == "local"
        # Should be at INFO level now, not WARNING
        assert "Archive legacy-archive-003 missing 'source_type' field (legacy document)" in caplog.text
        assert "defaulting to 'local'" in caplog.text
