# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion service module."""

import json
import os
import tempfile
import pytest

from copilot_events import NoopPublisher

from app.config import IngestionConfig, SourceConfig
from app.service import IngestionService


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
        return IngestionConfig(storage_path=temp_storage)

    @pytest.fixture
    def service(self, config):
        """Create test ingestion service."""
        publisher = NoopPublisher()
        publisher.connect()
        return IngestionService(config, publisher)

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
        config = IngestionConfig(storage_path=temp_storage)
        publisher = NoopPublisher()
        publisher.connect()
        service1 = IngestionService(config, publisher)

        # Add checksum and save
        file_hash = "hash123"
        archive_id = "archive-1"
        file_path = "/path/to/file"
        timestamp = "2023-01-01T00:00:00Z"

        service1.add_checksum(file_hash, archive_id, file_path, timestamp)
        service1.save_checksums()

        # Create new service and verify checksum was loaded
        service2 = IngestionService(config, publisher)
        assert service2.is_file_already_ingested(file_hash) is True

    def test_ingest_archive_success(self, service, temp_storage):
        """Test successful archive ingestion."""
        with tempfile.TemporaryDirectory() as source_dir:
            # Create a test mbox file
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            # Create local source
            source = SourceConfig(
                name="test-source",
                source_type="local",
                url=test_file,
            )

            # Ingest
            success = service.ingest_archive(source, max_retries=1)

            assert success is True
            assert len(service.checksums) == 1

    def test_ingest_archive_duplicate(self, service, temp_storage):
        """Test skipping duplicate archive."""
        with tempfile.TemporaryDirectory() as source_dir:
            # Create a test mbox file
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nTo: dev@example.com\nSubject: Test\n\nContent")

            source = SourceConfig(
                name="test-source",
                source_type="local",
                url=test_file,
            )

            # First ingestion
            success1 = service.ingest_archive(source, max_retries=1)
            assert success1 is True

            # Second ingestion (should be skipped)
            success2 = service.ingest_archive(source, max_retries=1)
            assert success2 is True

            # Should still have only one checksum
            assert len(service.checksums) == 1

    def test_ingest_all_enabled_sources(self, temp_storage):
        """Test ingesting from all enabled sources."""
        config = IngestionConfig(storage_path=temp_storage)
        publisher = NoopPublisher()
        publisher.connect()
        service = IngestionService(config, publisher)

        with tempfile.TemporaryDirectory() as source_dir:
            # Create test files
            file1 = os.path.join(source_dir, "file1.mbox")
            with open(file1, "w") as f:
                f.write("content1")

            file2 = os.path.join(source_dir, "file2.mbox")
            with open(file2, "w") as f:
                f.write("content2")

            # Create sources
            sources = [
                SourceConfig(
                    name="source1",
                    source_type="local",
                    url=file1,
                    enabled=True,
                ),
                SourceConfig(
                    name="source2",
                    source_type="local",
                    url=file2,
                    enabled=True,
                ),
                SourceConfig(
                    name="source3",
                    source_type="local",
                    url=file1,
                    enabled=False,  # Disabled
                ),
            ]

            config.sources = sources
            results = service.ingest_all_enabled_sources()

            assert len(results) == 2
            assert results["source1"] is True
            assert results["source2"] is True

    def test_ingestion_log_created(self, service, temp_storage):
        """Test that ingestion log is created."""
        with tempfile.TemporaryDirectory() as source_dir:
            # Create a test file
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = SourceConfig(
                name="test-source",
                source_type="local",
                url=test_file,
            )

            service.ingest_archive(source, max_retries=1)

            # Check log file
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
            # Create a test file
            test_file = os.path.join(source_dir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("content")

            source = SourceConfig(
                name="test-source",
                source_type="local",
                url=test_file,
            )

            service.ingest_archive(source, max_retries=1)

            # Check published events
            publisher = service.publisher
            assert isinstance(publisher, NoopPublisher)
            assert len(publisher.published_events) >= 1

            # Find success event
            success_events = [
                e for e in publisher.published_events
                if e["event"]["event_type"] == "ArchiveIngested"
            ]
            assert len(success_events) >= 1

            event = success_events[0]["event"]
            assert event["data"]["source_name"] == "test-source"
