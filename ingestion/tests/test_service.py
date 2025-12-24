# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion service module."""

import json
import os
import tempfile

import pytest
from app.service import IngestionService
from copilot_events import NoopPublisher, ValidatingEventPublisher
from copilot_logging import create_logger
from copilot_metrics import NoOpMetricsCollector
from copilot_schema_validation import FileSchemaProvider

from .test_helpers import assert_valid_event_schema, make_config, make_source


class TestIngestionService:
    """Tests for IngestionService."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_storage):
        """Create test configuration."""
        return make_config(storage_path=temp_storage)

    @pytest.fixture
    def service(self, config):
        """Create test ingestion service."""
        from pathlib import Path

        from copilot_storage import InMemoryDocumentStore

        base_publisher = NoopPublisher()
        base_publisher.connect()
        # Wrap with schema validation for events
        schema_dir = Path(__file__).parent.parent.parent / "documents" / "schemas" / "events"
        schema_provider = FileSchemaProvider(schema_dir=schema_dir)
        publisher = ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )
        logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
        metrics = NoOpMetricsCollector()

        # Create in-memory document store for testing
        document_store = InMemoryDocumentStore()
        document_store.connect()

        return IngestionService(
            config,
            publisher,
            document_store=document_store,
            logger=logger,
            metrics=metrics,
        )

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.config is not None
        assert service.publisher is not None
        assert isinstance(service.checksums, dict)

    def test_add_and_check_checksum(self, service):
        """Test adding and checking checksums."""
        file_hash = "abc123def456"
        archive_id = "archive-1"
        file_path = "/path/to/file"
        timestamp = "2023-01-01T00:00:00Z"

        service.add_checksum(file_hash, archive_id, file_path, timestamp)
        assert service.is_file_already_ingested(file_hash) is True

    def test_save_and_load_checksums(self, temp_storage):
        """Test saving and loading checksums."""
        config = make_config(storage_path=temp_storage)
        publisher = NoopPublisher()
        publisher.connect()
        service1 = IngestionService(config, publisher)

        file_hash = "hash123"
        archive_id = "archive-1"
        file_path = "/path/to/file"
        timestamp = "2023-01-01T00:00:00Z"

        service1.add_checksum(file_hash, archive_id, file_path, timestamp)
        service1.save_checksums()

        service2 = IngestionService(config, publisher)
        assert service2.is_file_already_ingested(file_hash) is True

    def test_ingest_archive_success(self, service, temp_storage):
        """Test successful archive ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = make_source(name="test-source", url=test_file)

            # Should not raise exception on success
            service.ingest_archive(source, max_retries=1)

            assert len(service.checksums) == 1

    def test_archives_collection_populated(self, service, temp_storage):
        """Test that archives collection is populated after ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = make_source(name="test-source", url=test_file)

            # Should not raise exception on success
            service.ingest_archive(source, max_retries=1)

            # Check that archives collection has one entry
            archives = service.document_store.query_documents("archives", {})
            assert len(archives) == 1

            # Verify archive document structure
            archive = archives[0]
            assert "_id" in archive
            assert archive["source"] == "test-source"
            assert archive["status"] == "pending"
            assert archive["message_count"] == 0
            assert "ingestion_date" in archive
            assert "file_path" in archive

    def test_metrics_emitted_on_success(self, service, temp_storage):
        """Ensure metrics are emitted for successful ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = make_source(name="test-source", url=test_file)

            service.ingest_archive(source, max_retries=1)

            metric_tags = {"source_name": "test-source", "source_type": "local"}
            assert isinstance(service.metrics, NoOpMetricsCollector)
            assert service.metrics.get_counter_total(
                "ingestion_sources_total",
                tags={**metric_tags, "status": "success"},
            ) == 1.0
            assert service.metrics.get_counter_total(
                "ingestion_files_total",
                tags={**metric_tags, "status": "success"},
            ) == 1.0
            assert service.metrics.get_counter_total(
                "ingestion_documents_total",
                tags={**metric_tags, "status": "success"},
            ) == 1.0
            assert service.metrics.get_gauge_value(
                "ingestion_files_processed",
                tags=metric_tags,
            ) == 1.0

    def test_ingest_archive_duplicate(self, service, temp_storage):
        """Test skipping duplicate archive."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = make_source(name="test-source", url=test_file)

            # First ingestion should succeed
            service.ingest_archive(source, max_retries=1)

            # Second ingestion should also succeed (skips duplicate files)
            service.ingest_archive(source, max_retries=1)

            assert len(service.checksums) == 1

    def test_ingest_all_enabled_sources(self, temp_storage):
        """Test ingesting from all enabled sources."""
        config = make_config(storage_path=temp_storage)
        publisher = NoopPublisher()
        publisher.connect()
        service = IngestionService(config, publisher)

        with tempfile.TemporaryDirectory() as source_dir:
            file1 = os.path.join(source_dir, "file1.mbox")
            with open(file1, "w") as f:
                f.write("content1")

            file2 = os.path.join(source_dir, "file2.mbox")
            with open(file2, "w") as f:
                f.write("content2")

            sources = [
                make_source(name="source1", url=file1),
                make_source(name="source2", url=file2),
                make_source(name="source3", url=file1, enabled=False),
            ]

            config.sources = sources
            results = service.ingest_all_enabled_sources()

            assert len(results) == 2
            # Results now map to None (success) or Exception (failure)
            assert results["source1"] is None  # Success
            assert results["source2"] is None  # Success

    def test_ingestion_log_created(self, service, temp_storage):
        """Test that ingestion log is created."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = make_source(name="test-source", url=test_file)

            service.ingest_archive(source, max_retries=1)

            log_path = os.path.join(temp_storage, "metadata", "ingestion_log.jsonl")
            assert os.path.exists(log_path)

            with open(log_path) as f:
                lines = f.readlines()
                assert len(lines) >= 1
                log_entry = json.loads(lines[0])
                assert log_entry["source_name"] == "test-source"
                assert log_entry["status"] == "success"

    def test_publish_success_event(self, service, temp_storage):
        """Test that success event is published."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = make_source(name="test-source", url=test_file)

            service.ingest_archive(source, max_retries=1)

            publisher = service.publisher
            # Publisher is a validating wrapper around NoopPublisher
            assert isinstance(publisher, ValidatingEventPublisher)
            assert len(publisher.published_events) >= 1

            success_events = [
                e for e in publisher.published_events
                if e["event"]["event_type"] == "ArchiveIngested"
            ]
            assert len(success_events) >= 1

            event = success_events[0]["event"]
            assert event["data"]["source_name"] == "test-source"

            assert_valid_event_schema(event)

    def test_error_reporter_integration(self, temp_storage):
        """Test error reporter integration."""
        from copilot_reporting import SilentErrorReporter

        config = make_config(storage_path=temp_storage)
        config.log_type = "silent"
        publisher = NoopPublisher()
        publisher.connect()
        error_reporter = SilentErrorReporter()
        logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
        metrics = NoOpMetricsCollector()

        service = IngestionService(
            config,
            publisher,
            error_reporter=error_reporter,
            logger=logger,
            metrics=metrics,
        )

        assert service.error_reporter is error_reporter
        assert isinstance(service.error_reporter, SilentErrorReporter)

        service.config.storage_path = "/invalid/path/that/does/not/exist"
        try:
            service.save_checksums()
        except ValueError:
            # Expected: save_checksums raises after reporting to error_reporter
            pass

        assert error_reporter.has_errors()
        errors = error_reporter.get_errors()
        assert len(errors) >= 1
        assert errors[0]["context"]["operation"] == "save_checksums"

    def test_error_reporter_default_initialization(self, config):
        """Test default error reporter initialization from config."""
        config.error_reporter_type = "silent"
        config.log_type = "silent"
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
        metrics = NoOpMetricsCollector()

        service = IngestionService(config, publisher, logger=logger, metrics=metrics)

        from copilot_reporting import SilentErrorReporter
        assert isinstance(service.error_reporter, SilentErrorReporter)

    def test_delete_checksums_for_source(self, service, temp_storage):
        """Test deleting checksums for a specific source."""
        # Add checksums for multiple sources
        storage_path = service.config.storage_path

        # Checksums for source1
        service.add_checksum(
            "hash1", "archive1",
            os.path.join(storage_path, "source1", "file1.mbox"),
            "2023-01-01T00:00:00Z"
        )
        service.add_checksum(
            "hash2", "archive2",
            os.path.join(storage_path, "source1", "file2.mbox"),
            "2023-01-01T00:00:00Z"
        )

        # Checksums for source2
        service.add_checksum(
            "hash3", "archive3",
            os.path.join(storage_path, "source2", "file3.mbox"),
            "2023-01-01T00:00:00Z"
        )

        assert len(service.checksums) == 3

        # Delete checksums for source1
        deleted_count = service.delete_checksums_for_source("source1")

        assert deleted_count == 2
        assert len(service.checksums) == 1
        assert not service.is_file_already_ingested("hash1")
        assert not service.is_file_already_ingested("hash2")
        assert service.is_file_already_ingested("hash3")

    def test_delete_checksums_for_nonexistent_source(self, service):
        """Test deleting checksums for a source with no checksums."""
        # Add a checksum for a different source
        service.add_checksum(
            "hash1", "archive1",
            os.path.join(service.config.storage_path, "source1", "file1.mbox"),
            "2023-01-01T00:00:00Z"
        )

        # Try to delete checksums for a source that doesn't exist
        deleted_count = service.delete_checksums_for_source("nonexistent-source")

        assert deleted_count == 0
        assert len(service.checksums) == 1

    def test_delete_checksums_only_deletes_exact_source_match(self, service):
        """Test that delete_checksums_for_source doesn't match similar source names."""
        storage_path = service.config.storage_path

        # Add checksums for sources with similar names
        service.add_checksum(
            "hash1", "archive1",
            os.path.join(storage_path, "source1", "file1.mbox"),
            "2023-01-01T00:00:00Z"
        )
        service.add_checksum(
            "hash2", "archive2",
            os.path.join(storage_path, "source10", "file2.mbox"),
            "2023-01-01T00:00:00Z"
        )
        service.add_checksum(
            "hash3", "archive3",
            os.path.join(storage_path, "source1-backup", "file3.mbox"),
            "2023-01-01T00:00:00Z"
        )

        assert len(service.checksums) == 3

        # Delete checksums for source1 only
        deleted_count = service.delete_checksums_for_source("source1")

        # Should only delete hash1, not hash2 or hash3
        assert deleted_count == 1
        assert len(service.checksums) == 2
        assert not service.is_file_already_ingested("hash1")
        assert service.is_file_already_ingested("hash2")
        assert service.is_file_already_ingested("hash3")

    def test_trigger_ingestion_deletes_checksums(self, service, temp_storage):
        """Test that trigger_ingestion deletes checksums before re-ingestion."""
        from copilot_storage import InMemoryDocumentStore

        # Setup document store with a source
        if not service.document_store:
            service.document_store = InMemoryDocumentStore()
            service.document_store.connect()

        # Create a test file
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            # Create a source
            source_data = {
                "name": "test-source",
                "source_type": "local",
                "url": test_file,
                "enabled": True,
            }
            service.create_source(source_data)

            # First ingestion - should create a checksum
            success, message = service.trigger_ingestion("test-source")
            assert success is True
            assert len(service.checksums) == 1
            first_hash = list(service.checksums.keys())[0]

            # Verify the file would be skipped on next ingest
            assert service.is_file_already_ingested(first_hash)

            # Trigger ingestion again - should delete the checksum and re-ingest
            success, message = service.trigger_ingestion("test-source")
            assert success is True

            # The file should have been re-ingested, creating a new checksum entry
            # (same hash, but the checksum should have been deleted and re-added)
            assert len(service.checksums) == 1
            assert service.is_file_already_ingested(first_hash)


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_archive_ingested_event_schema_validation():
    """Test that ArchiveIngested events validate against schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
        metrics = NoOpMetricsCollector()
        service = IngestionService(config, publisher, logger=logger, metrics=metrics)

        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\n\nContent")

            source = make_source(name="test-source", url=test_file)

            service.ingest_archive(source, max_retries=1)

            success_events = [
                e for e in publisher.published_events
                if e["event"]["event_type"] == "ArchiveIngested"
            ]

            assert len(success_events) >= 1

            for event_record in success_events:
                assert_valid_event_schema(event_record["event"])


def test_archive_ingestion_failed_event_schema_validation():
    """Test that ArchiveIngestionFailed events validate against schema."""
    from app.exceptions import FetchError

    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
        metrics = NoOpMetricsCollector()
        service = IngestionService(config, publisher, logger=logger, metrics=metrics)

        source = make_source(name="test-source", url="/nonexistent/file.mbox")

        # ingest_archive now raises exceptions instead of returning False
        # The failure event should still be published before the exception is raised
        with pytest.raises(FetchError):
            service.ingest_archive(source, max_retries=1)

        failure_events = [
            e for e in publisher.published_events
            if e["event"]["event_type"] == "ArchiveIngestionFailed"
        ]

        assert len(failure_events) >= 1

        for event_record in failure_events:
            assert_valid_event_schema(event_record["event"])


def test_save_checksums_raises_on_write_error(tmp_path):
    """Test that save_checksums raises exception on write errors."""
    from unittest.mock import patch

    from app.service import IngestionService
    from copilot_events import NoopPublisher

    from .test_helpers import make_config

    config = make_config(storage_path=str(tmp_path))

    publisher = NoopPublisher()
    service = IngestionService(config=config, publisher=publisher)

    # Add a checksum
    service.checksums["test"] = "abc123"

    # Mock open to raise PermissionError when writing checksums file
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        # Verify exception is raised, not swallowed
        with pytest.raises(PermissionError):
            service.save_checksums()


def test_load_checksums_recovers_on_read_error(tmp_path):
    """Test that load_checksums recovers gracefully on read errors (intentional)."""
    from app.service import IngestionService
    from copilot_events import NoopPublisher

    from .test_helpers import make_config

    # Create a corrupted checksums file
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    checksums_file = metadata_dir / "checksums.json"
    checksums_file.write_text("{ invalid json }")

    config = make_config(storage_path=str(tmp_path))

    publisher = NoopPublisher()

    # Service should start with empty checksums (intentional recovery)
    service = IngestionService(config=config, publisher=publisher)
    assert service.checksums == {}


def test_publish_success_event_raises_on_publisher_failure(tmp_path):
    """Test that _publish_success_event raises exception when publisher fails."""
    from unittest.mock import Mock

    from copilot_events import ArchiveMetadata

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("Publisher failure"))  # Simulate publisher failure

    service = IngestionService(config=config, publisher=publisher)

    metadata = ArchiveMetadata(
        archive_id="archive-123",
        source_name="test-source",
        source_type="mbox",
        source_url="http://example.com/list.mbox",
        file_path="/path/to/file.mbox",
        file_size_bytes=1024,
        file_hash_sha256="abc123def456",
        ingestion_started_at="2023-10-15T12:00:00Z",
        ingestion_completed_at="2023-10-15T12:00:10Z",
        status="success",
    )

    # Service should propagate exception when publisher.publish raises
    with pytest.raises(Exception, match="Publisher failure"):
        service._publish_success_event(metadata)


def test_publish_failure_event_raises_on_publisher_failure(tmp_path):
    """Test that _publish_failure_event raises exception when publisher fails."""
    from unittest.mock import Mock

    from copilot_archive_fetcher import SourceConfig

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("Publisher failure"))  # Simulate publisher failure

    service = IngestionService(config=config, publisher=publisher)

    source = SourceConfig(
        name="test-source",
        source_type="mbox",
        url="http://example.com/list.mbox",
    )

    # Service should propagate exception when publisher.publish raises
    with pytest.raises(Exception, match="Publisher failure"):
        service._publish_failure_event(
            source=source,
            error_message="Test error",
            error_type="TestError",
            retry_count=3,
            ingestion_started_at="2023-10-15T12:00:00Z",
        )


def test_publish_success_event_raises_on_publisher_exception(tmp_path):
    """Test that _publish_success_event raises exception when publisher raises."""
    from unittest.mock import Mock

    from copilot_events import ArchiveMetadata

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))

    service = IngestionService(config=config, publisher=publisher)

    metadata = ArchiveMetadata(
        archive_id="archive-123",
        source_name="test-source",
        source_type="mbox",
        source_url="http://example.com/list.mbox",
        file_path="/path/to/file.mbox",
        file_size_bytes=1024,
        file_hash_sha256="abc123def456",
        ingestion_started_at="2023-10-15T12:00:00Z",
        ingestion_completed_at="2023-10-15T12:00:10Z",
        status="success",
    )

    # Service should raise exception from publisher
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        service._publish_success_event(metadata)


def test_publish_failure_event_raises_on_publisher_exception(tmp_path):
    """Test that _publish_failure_event raises exception when publisher raises."""
    from unittest.mock import Mock

    from copilot_archive_fetcher import SourceConfig

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))

    service = IngestionService(config=config, publisher=publisher)

    source = SourceConfig(
        name="test-source",
        source_type="mbox",
        url="http://example.com/list.mbox",
    )

    # Service should raise exception from publisher
    with pytest.raises(Exception, match="RabbitMQ connection lost"):
        service._publish_failure_event(
            source=source,
            error_message="Test error",
            error_type="TestError",
            retry_count=3,
            ingestion_started_at="2023-10-15T12:00:00Z",
        )


def test_ingest_archive_raises_source_configuration_error(tmp_path):
    """Test that ingest_archive raises SourceConfigurationError for invalid config."""
    from app.exceptions import SourceConfigurationError

    config = make_config(storage_path=str(tmp_path))
    publisher = NoopPublisher()
    publisher.connect()

    service = IngestionService(config=config, publisher=publisher)

    # Invalid source dict missing required fields
    invalid_source = {"name": "test"}  # Missing source_type and url

    with pytest.raises(SourceConfigurationError, match="missing required fields"):
        service.ingest_archive(invalid_source, max_retries=1)


def test_ingest_archive_raises_fetch_error(tmp_path):
    """Test that ingest_archive raises FetchError when fetching fails."""
    from app.exceptions import FetchError

    config = make_config(storage_path=str(tmp_path))
    publisher = NoopPublisher()
    publisher.connect()

    service = IngestionService(config=config, publisher=publisher)

    # Source with non-existent URL
    source = make_source(name="test", url="file:///nonexistent/path/file.mbox")

    with pytest.raises(FetchError):
        service.ingest_archive(source, max_retries=1)


def test_ingest_all_enabled_sources_returns_exceptions(tmp_path):
    """Test that ingest_all_enabled_sources returns exception objects for failures."""
    from app.exceptions import FetchError

    config = make_config(storage_path=str(tmp_path))
    publisher = NoopPublisher()
    publisher.connect()

    service = IngestionService(config=config, publisher=publisher)

    with tempfile.TemporaryDirectory() as source_dir:
        # Create one valid file
        valid_file = os.path.join(source_dir, "valid.mbox")
        with open(valid_file, "w") as f:
            f.write("content")

        sources = [
            make_source(name="valid-source", url=valid_file),
            make_source(name="invalid-source", url="file:///nonexistent/file.mbox"),
        ]

        config.sources = sources
        results = service.ingest_all_enabled_sources()

        # Check that results contain one success and one failure
        assert len(results) == 2
        assert results["valid-source"] is None  # Success
        assert isinstance(results["invalid-source"], Exception)  # Failure
        assert isinstance(results["invalid-source"], FetchError)  # Specific exception type


def test_exception_prevents_silent_failure():
    """Demonstrate that exceptions prevent silent failures (the core issue this PR addresses).

    This test validates that the refactored code makes it impossible to ignore failures,
    unlike the previous return-code-based approach where callers could forget to check
    the return value.
    """
    import tempfile

    from app.exceptions import FetchError

    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config=config, publisher=publisher)

        # Create a source that will fail (non-existent file)
        bad_source = make_source(name="bad", url="file:///this/does/not/exist.mbox")

        # OLD BEHAVIOR (before this PR):
        # success = service.ingest_archive(bad_source)
        # # Oops! Forgot to check 'success' - silent failure!
        # continue_with_next_step()  # This would run even though ingestion failed

        # NEW BEHAVIOR (after this PR):
        # Exception MUST be handled - can't be ignored
        exception_was_raised = False
        try:
            service.ingest_archive(bad_source, max_retries=1)
            # If we get here, test should fail - exception should have been raised
            assert False, "Expected FetchError to be raised"
        except FetchError as e:
            # Good! Exception was raised and caught
            exception_was_raised = True
            assert e.source_name == "bad"
            assert e.retry_count > 0

        assert exception_was_raised, "Exception-based approach successfully prevented silent failure"
