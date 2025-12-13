# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion service module."""

import json
import os
import tempfile
import pytest

from copilot_events import NoopPublisher
from copilot_logging import create_logger
from copilot_metrics import NoOpMetricsCollector

from app.service import IngestionService
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
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", name="ingestion-test")
        metrics = NoOpMetricsCollector()
        return IngestionService(config, publisher, logger=logger, metrics=metrics)

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

            success = service.ingest_archive(source, max_retries=1)

            assert success is True
            assert len(service.checksums) == 1

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

            success1 = service.ingest_archive(source, max_retries=1)
            assert success1 is True

            success2 = service.ingest_archive(source, max_retries=1)
            assert success2 is True

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
            assert results["source1"] is True
            assert results["source2"] is True

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

            with open(log_path, "r") as f:
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
            assert isinstance(publisher, NoopPublisher)
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
        logger = create_logger(logger_type="silent", name="ingestion-test")
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
        service.save_checksums()

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
        logger = create_logger(logger_type="silent", name="ingestion-test")
        metrics = NoOpMetricsCollector()

        service = IngestionService(config, publisher, logger=logger, metrics=metrics)

        from copilot_reporting import SilentErrorReporter
        assert isinstance(service.error_reporter, SilentErrorReporter)


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_archive_ingested_event_schema_validation():
    """Test that ArchiveIngested events validate against schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", name="ingestion-test")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(storage_path=tmpdir)
        publisher = NoopPublisher()
        publisher.connect()
        logger = create_logger(logger_type="silent", name="ingestion-test")
        metrics = NoOpMetricsCollector()
        service = IngestionService(config, publisher, logger=logger, metrics=metrics)

        source = make_source(name="test-source", url="/nonexistent/file.mbox")

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
    from app.service import IngestionService
    from copilot_events import NoopPublisher
    from .test_helpers import make_config
    
    config = make_config(storage_path=str(tmp_path))
    
    publisher = NoopPublisher()
    service = IngestionService(config=config, publisher=publisher)
    
    # Add a checksum
    service.checksums["test"] = "abc123"
    
    # Make the metadata directory read-only to trigger write error
    import os
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    os.chmod(metadata_dir, 0o444)
    
    # Verify exception is raised, not swallowed
    try:
        with pytest.raises(Exception):
            service.save_checksums()
    finally:
        # Restore permissions for cleanup
        os.chmod(metadata_dir, 0o755)


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
