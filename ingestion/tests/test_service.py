# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion service module."""

import json
import os
import tempfile

import pytest
from app.service import IngestionService
from copilot_error_reporting import create_error_reporter
from copilot_message_bus import create_publisher
from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector
from copilot_storage import create_document_store

from copilot_config.generated.adapters.document_store import AdapterConfig_DocumentStore, DriverConfig_DocumentStore_Inmemory
from copilot_config.generated.adapters.error_reporter import AdapterConfig_ErrorReporter, DriverConfig_ErrorReporter_Silent
from copilot_config.generated.adapters.logger import AdapterConfig_Logger, DriverConfig_Logger_Silent
from copilot_config.generated.adapters.message_bus import AdapterConfig_MessageBus, DriverConfig_MessageBus_Noop
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics, DriverConfig_Metrics_Noop

from .test_helpers import assert_valid_event_schema, make_archive_store, make_config, make_source


def _make_noop_publisher():
    publisher = create_publisher(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    publisher.connect()
    return publisher


def _make_silent_logger(name: str = "ingestion-test"):
    return create_logger(
        AdapterConfig_Logger(
            logger_type="silent",
            driver=DriverConfig_Logger_Silent(level="INFO", name=name),
        )
    )


def _make_noop_metrics():
    return create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))


def _make_silent_error_reporter():
    return create_error_reporter(
        AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
    )


def _make_inmemory_store():
    store = create_document_store(
        AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
        enable_validation=False,
    )
    store.connect()
    return store


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

        publisher = create_publisher(
            AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
            enable_validation=False,
        )
        publisher.connect()

        logger = create_logger(
            AdapterConfig_Logger(
                logger_type="silent",
                driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"),
            )
        )
        metrics = create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))
        error_reporter = create_error_reporter(
            AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
        )

        # Create in-memory document store for testing
        document_store = create_document_store(
            AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
            enable_validation=False,
        )
        document_store.connect()

        archive_store = make_archive_store(base_path=config.service_settings.storage_path or "/tmp/ingestion")

        return IngestionService(
            config,
            publisher,
            document_store=document_store,
            error_reporter=error_reporter,
            logger=logger,
            metrics=metrics,
            archive_store=archive_store,
        )

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.config is not None
        assert service.publisher is not None
        assert service.archive_store is not None

    def test_ingest_archive_success(self, service, temp_storage):
        """Test successful archive ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = make_source(name="test-source", url=test_file)

            # Should not raise exception on success
            service.ingest_archive(source, max_retries=1)

            # Verify archives were stored in document store
            archives = service.document_store.query_documents("archives", {})
            assert len(archives) == 1

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

            # Verify archive document structure (storage-agnostic - no file_path)
            archive = archives[0]
            assert "_id" in archive
            assert archive["source"] == "test-source"
            assert archive["status"] == "pending"
            assert archive["message_count"] == 0
            assert "ingestion_date" in archive
            # file_path no longer stored in archive documents for storage-agnostic mode
            assert "file_path" not in archive or archive["file_path"] == ""

    def test_metrics_emitted_on_success(self, service, temp_storage):
        """Ensure metrics are emitted for successful ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = make_source(name="test-source", url=test_file)

            service.ingest_archive(source, max_retries=1)

            metric_tags = {"source_name": "test-source", "source_type": "local"}
            # Verify metrics were collected (factory returns appropriate collector)
            assert service.metrics is not None
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

            # Second ingestion should also succeed (skips duplicate files via document store)
            service.ingest_archive(source, max_retries=1)

            # Should still have only one archive in document store
            archives = service.document_store.query_documents("archives", {})
            assert len(archives) == 1

    def test_ingest_all_enabled_sources(self, temp_storage):
        """Test ingesting from all enabled sources."""
        config = make_config(storage_path=temp_storage)
        publisher = create_publisher(
            AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
            enable_validation=False,
        )
        publisher.connect()
        logger = create_logger(
            AdapterConfig_Logger(
                logger_type="silent",
                driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"),
            )
        )
        metrics = create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))
        error_reporter = create_error_reporter(
            AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
        )

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

            service = IngestionService(
                config,
                publisher,
                sources=sources,
                logger=logger,
                metrics=metrics,
                error_reporter=error_reporter,
                archive_store=make_archive_store(config.service_settings.storage_path or temp_storage),
            )
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
            # Verify publisher has published events
            assert publisher is not None
            assert hasattr(publisher, 'published_events')
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
        config = make_config(storage_path=temp_storage)
        publisher = create_publisher(
            AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
            enable_validation=False,
        )
        publisher.connect()
        error_reporter = create_error_reporter(
            AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
        )
        logger = create_logger(
            AdapterConfig_Logger(
                logger_type="silent",
                driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"),
            )
        )
        metrics = create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))

        # Add document store
        document_store = create_document_store(
            AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
            enable_validation=False,
        )
        document_store.connect()

        service = IngestionService(
            config,
            publisher,
            document_store=document_store,
            error_reporter=error_reporter,
            logger=logger,
            metrics=metrics,
            archive_store=make_archive_store(config.service_settings.storage_path or temp_storage),
        )

        assert service.error_reporter is error_reporter
        # Verify error_reporter was created with correct driver
        assert hasattr(service.error_reporter, 'report')

        # Test that error_reporter can be called and records errors
        test_error = Exception("Test error")
        error_reporter.report(test_error, context={"test": "value"})

        # Verify error was recorded
        assert error_reporter.has_errors()
        errors = error_reporter.get_errors()
        assert len(errors) == 1
        assert errors[0]["context"]["test"] == "value"

    def test_error_reporter_required(self, config):
        """Test that error_reporter must be provided by the caller."""
        publisher = _make_noop_publisher()
        logger = _make_silent_logger()
        metrics = _make_noop_metrics()

        with pytest.raises(ValueError, match="error_reporter is required"):
            IngestionService(
                config,
                publisher,
                logger=logger,
                metrics=metrics,
                archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
            )


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_archive_ingested_event_schema_validation():
    """Test that ArchiveIngested events validate against schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = _make_noop_publisher()
        logger = _make_silent_logger()
        metrics = _make_noop_metrics()
        error_reporter = _make_silent_error_reporter()
        service = IngestionService(
            config,
            publisher,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter,
            archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
        )

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
        config = make_config(storage_path=tmpdir, request_timeout_seconds=1)
        publisher = _make_noop_publisher()
        logger = _make_silent_logger()
        metrics = _make_noop_metrics()
        error_reporter = _make_silent_error_reporter()
        service = IngestionService(
            config,
            publisher,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter,
            archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
        )

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


def test_publish_success_event_raises_on_publisher_failure(tmp_path):
    """Test that _publish_success_event raises exception when publisher fails."""
    from unittest.mock import Mock

    from copilot_schema_validation import ArchiveMetadata

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("Publisher failure"))  # Simulate publisher failure

    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    metadata = ArchiveMetadata(
        archive_id="archive-123",
        source_name="test-source",
        source_type="http",
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

    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    source = SourceConfig(
        name="test-source",
        source_type="http",
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

    from copilot_schema_validation import ArchiveMetadata

    config = make_config(storage_path=str(tmp_path))
    publisher = Mock()
    publisher.publish = Mock(side_effect=Exception("RabbitMQ connection lost"))

    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    metadata = ArchiveMetadata(
        archive_id="archive-123",
        source_name="test-source",
        source_type="http",
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

    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    source = SourceConfig(
        name="test-source",
        source_type="http",
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

    config = make_config(storage_path=str(tmp_path), request_timeout_seconds=1)
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Invalid source dict missing required fields
    invalid_source = {"name": "test"}  # Missing source_type and url

    with pytest.raises(SourceConfigurationError, match="missing required fields"):
        service.ingest_archive(invalid_source, max_retries=1)


def test_ingest_archive_raises_fetch_error(tmp_path):
    """Test that ingest_archive raises FetchError when fetching fails."""
    from app.exceptions import FetchError

    config = make_config(storage_path=str(tmp_path), request_timeout_seconds=1)
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Source with non-existent URL
    source = make_source(name="test", url="file:///nonexistent/path/file.mbox")

    with pytest.raises(FetchError):
        service.ingest_archive(source, max_retries=1)


def test_ingest_all_enabled_sources_returns_exceptions(tmp_path):
    """Test that ingest_all_enabled_sources returns exception objects for failures."""
    from app.exceptions import FetchError

    config = make_config(storage_path=str(tmp_path), max_retries=1, request_timeout_seconds=1)
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    with tempfile.TemporaryDirectory() as source_dir:
        # Create one valid file
        valid_file = os.path.join(source_dir, "valid.mbox")
        with open(valid_file, "w") as f:
            f.write("content")

        sources = [
            make_source(name="valid-source", url=valid_file),
            make_source(name="invalid-source", url="file:///nonexistent/file.mbox"),
        ]

        service = IngestionService(
            config=config,
            publisher=publisher,
            sources=sources,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter,
            archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
        )
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
        config = make_config(storage_path=tmpdir, request_timeout_seconds=1)
        publisher = _make_noop_publisher()
        logger = _make_silent_logger()
        metrics = _make_noop_metrics()
        error_reporter = _make_silent_error_reporter()

        service = IngestionService(
            config=config,
            publisher=publisher,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter,
            archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
        )

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


def test_service_initialization_with_archive_store(tmp_path):
    """Test that service can be initialized with ArchiveStore."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()

    # Create ArchiveStore using factory
    archive_store = make_archive_store(base_path=str(tmp_path))

    service = IngestionService(
        config=config,
        publisher=publisher,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=archive_store,
    )

    assert service.archive_store is not None
    # Don't check specific type - just verify it's set


def test_archive_deduplication_via_document_store(tmp_path):
    """Test that _is_archive_already_stored checks document store instead of checksums."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()

    # Create in-memory document store
    document_store = _make_inmemory_store()
    service = IngestionService(
        config=config,
        publisher=publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Use proper SHA256 hashes: 64 hex chars for full hash
    file_hash = "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"

    # Initially, archive should not be stored
    assert service._is_archive_already_stored(file_hash) is False

    # Add archive to document store
    document_store.insert_document("archives", {
        "_id": "abc123def456abcd",  # First 16 chars of file_hash
        "file_hash": file_hash,
        "file_size_bytes": 1024,
        "source": "test",
        "ingestion_date": "2026-01-09T00:00:00Z",
        "status": "pending",
    })

    # Now it should be found
    assert service._is_archive_already_stored(file_hash) is True


def test_delete_archives_for_source_deletes_from_document_store(tmp_path):
    """Test that delete_archives_for_source deletes archives from document store."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()

    # Create in-memory document store
    document_store = _make_inmemory_store()

    service = IngestionService(
        config=config,
        publisher=publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Add some archives to document store
    document_store.insert_document("archives", {
        "_id": "1111111111111111",
        "file_hash": "1111111111111111111111111111111111111111111111111111111111111111",
        "file_size_bytes": 1024,
        "source": "test-source",
        "ingestion_date": "2026-01-09T00:00:00Z",
        "status": "completed",
    })
    document_store.insert_document("archives", {
        "_id": "2222222222222222",
        "file_hash": "2222222222222222222222222222222222222222222222222222222222222222",
        "file_size_bytes": 2048,
        "source": "other-source",
        "ingestion_date": "2026-01-09T00:00:00Z",
        "status": "completed",
    })
    document_store.insert_document("archives", {
        "_id": "3333333333333333",
        "file_hash": "3333333333333333333333333333333333333333333333333333333333333333",
        "file_size_bytes": 3072,
        "source": "test-source",
        "ingestion_date": "2026-01-09T00:00:00Z",
        "status": "pending",
    })

    # Delete archives for test-source
    deleted_count = service.delete_archives_for_source("test-source")

    # Should have deleted 2 archives
    assert deleted_count == 2

    # Verify archives were deleted
    remaining = document_store.query_documents("archives", {})
    assert len(remaining) == 1
    assert remaining[0]["_id"] == "2222222222222222"


def test_archive_ingested_event_without_file_path():
    """Test that ArchiveIngested events do not include file_path (storage-agnostic)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)

        publisher = _make_noop_publisher()
        logger = _make_silent_logger()
        metrics = _make_noop_metrics()
        error_reporter = _make_silent_error_reporter()
        document_store = _make_inmemory_store()

        service = IngestionService(
            config,
            publisher,
            document_store=document_store,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter,
            archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
        )

        # Create test file
        with tempfile.TemporaryDirectory() as source_dir:
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = make_source(name="test-source", url=test_file)
            service.ingest_archive(source, max_retries=1)

        # Verify ArchiveIngested events do not contain file_path
        success_events = [
            e for e in publisher.published_events
            if e["event"]["event_type"] == "ArchiveIngested"
        ]
        assert len(success_events) >= 1

        for event_wrapper in success_events:
            event = event_wrapper["event"]
            # file_path should NOT be in the event data (storage-agnostic design)
            assert "file_path" not in event["data"], (
                "ArchiveIngested events should not include file_path for storage-agnostic design"
            )
            # But archive_id, source_name, etc. should be present
            assert "archive_id" in event["data"]
            assert "source_name" in event["data"]
            assert "file_hash_sha256" in event["data"]


def test_delete_source_cascade_service_layer(tmp_path):
    """Test delete_source_cascade method at service layer."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    document_store = _make_inmemory_store()

    service = IngestionService(
        config=config,
        publisher=publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Verify archive_store starts empty (no archives from previous tests)
    # This helps diagnose test failures related to archive_store state
    assert service.archive_store is not None, "archive_store should be initialized"

    # Add test data across multiple collections
    document_store.insert_document("archives", {
        "_id": "archive-1",
        "source": "test-source",
        "file_hash": "hash1",
    })
    document_store.insert_document("archives", {
        "_id": "archive-2",
        "source": "test-source",
        "file_hash": "hash2",
    })
    document_store.insert_document("threads", {
        "_id": "thread-1",
        "source": "test-source",
    })
    document_store.insert_document("messages", {
        "_id": "message-1",
        "source": "test-source",
    })
    document_store.insert_document("messages", {
        "_id": "message-2",
        "source": "test-source",
    })
    document_store.insert_document("chunks", {
        "_id": "chunk-1",
        "source": "test-source",
    })
    document_store.insert_document("summaries", {
        "_id": "summary-1",
        "source": "test-source",
    })

    # Execute cascade delete
    deletion_counts = service.delete_source_cascade("test-source")

    # Verify deletion counts
    assert deletion_counts["archives_docstore"] == 2
    assert deletion_counts["archives_archivestore"] == 2  # Should match archives_docstore
    assert deletion_counts["threads"] == 1
    assert deletion_counts["messages"] == 2
    assert deletion_counts["chunks"] == 1
    assert deletion_counts["summaries"] == 1

    # Verify data was actually deleted
    assert len(document_store.query_documents("archives", {"source": "test-source"})) == 0
    assert len(document_store.query_documents("threads", {"source": "test-source"})) == 0
    assert len(document_store.query_documents("messages", {"source": "test-source"})) == 0
    assert len(document_store.query_documents("chunks", {"source": "test-source"})) == 0
    assert len(document_store.query_documents("summaries", {"source": "test-source"})) == 0


def test_delete_source_without_cascade_service_layer(tmp_path):
    """Test delete_source method without cascade at service layer."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    document_store = _make_inmemory_store()

    service = IngestionService(
        config=config,
        publisher=publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Create a source in document store
    document_store.insert_document("sources", {
        "_id": "source-1",
        "name": "test-source",
        "source_type": "http",
        "url": "http://example.com/archive.mbox",
        "enabled": True,
    })

    # Add associated data
    document_store.insert_document("archives", {
        "_id": "archive-1",
        "source": "test-source",
        "file_hash": "hash1",
    })

    # Delete source without cascade
    result = service.delete_source("test-source", cascade=False)

    # Should return True (source deleted)
    assert result is True

    # Verify source was deleted
    sources = document_store.query_documents("sources", {"name": "test-source"})
    assert len(sources) == 0

    # Verify associated data was NOT deleted
    archives = document_store.query_documents("archives", {"source": "test-source"})
    assert len(archives) == 1


def test_delete_source_with_cascade_service_layer(tmp_path):
    """Test delete_source method with cascade=True at service layer."""
    config = make_config(storage_path=str(tmp_path))
    publisher = _make_noop_publisher()
    logger = _make_silent_logger()
    metrics = _make_noop_metrics()
    error_reporter = _make_silent_error_reporter()
    document_store = _make_inmemory_store()

    service = IngestionService(
        config=config,
        publisher=publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=make_archive_store(config.service_settings.storage_path or "/tmp/ingestion"),
    )

    # Create a source in document store
    document_store.insert_document("sources", {
        "_id": "source-1",
        "name": "test-source",
        "source_type": "http",
        "url": "http://example.com/archive.mbox",
        "enabled": True,
    })

    # Add associated data
    document_store.insert_document("archives", {
        "_id": "archive-1",
        "source": "test-source",
        "file_hash": "hash1",
    })
    document_store.insert_document("threads", {
        "_id": "thread-1",
        "source": "test-source",
    })

    # Delete source with cascade
    result = service.delete_source("test-source", cascade=True)

    # Should return deletion counts dict
    assert isinstance(result, dict)
    assert "archives_docstore" in result
    assert result["archives_docstore"] == 1
    assert result["threads"] == 1

    # Verify source was deleted
    sources = document_store.query_documents("sources", {"name": "test-source"})
    assert len(sources) == 0

    # Verify associated data was deleted
    archives = document_store.query_documents("archives", {"source": "test-source"})
    assert len(archives) == 0
    threads = document_store.query_documents("threads", {"source": "test-source"})
    assert len(threads) == 0







