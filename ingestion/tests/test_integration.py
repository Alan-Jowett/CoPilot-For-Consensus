# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the ingestion service."""

import json
import os
import tempfile

import pytest
from app.service import IngestionService
from copilot_archive_store import create_archive_store
from copilot_message_bus import create_publisher
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store
from copilot_logging import create_logger
from copilot_config import load_driver_config

from .test_helpers import make_config, make_source

pytestmark = pytest.mark.integration


class TestIngestionIntegration:
    """Integration tests for the complete ingestion workflow."""

    @pytest.fixture
    def test_logger(self):
        """Create a test logger."""
        logger_config = load_driver_config(
            service=None, adapter="logger", driver="silent", fields={"level": "INFO", "name": "ingestion-test"}
        )
        return create_logger(driver_name="silent", driver_config=logger_config)

    @pytest.fixture
    def temp_environment(self):
        """Create temporary environment for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "archives")
            os.makedirs(storage_path)

            yield {
                "storage_path": storage_path,
                "source_dir": os.path.join(tmpdir, "sources"),
                "tmpdir": tmpdir,
            }

    @pytest.fixture
    def test_sources(self, temp_environment):
        """Create test mail sources."""
        source_dir = temp_environment["source_dir"]
        os.makedirs(source_dir)

        # Create multiple test mbox files
        sources = []
        for i in range(3):
            source_name = f"test-list-{i}"
            source_file = os.path.join(source_dir, f"{source_name}.mbox")

            with open(source_file, "w") as f:
                # Write minimal mbox format
                for j in range(5):
                    f.write(f"From: user{j}@example.com\n")
                    f.write(f"To: {source_name}@example.com\n")
                    f.write(f"Subject: Test Message {j}\n")
                    f.write(f"Date: Mon, 01 Jan 2023 {j:02d}:00:00 +0000\n")
                    f.write("\n")
                    f.write(f"This is test message {j}\n")
                    f.write("\n")

            sources.append(
                make_source(
                    name=source_name,
                    source_type="local",
                    url=source_file,
                    enabled=True,
                )
            )

        return sources

    def test_end_to_end_ingestion(self, temp_environment, test_sources, test_logger):
        """Test complete end-to-end ingestion workflow."""
        from pathlib import Path

        # Create configuration
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
            retry_max_attempts=1,
        )

        # Create publisher and service
        schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "events"
        publisher = create_publisher(
            driver_name="noop",
            driver_config={
                "schema_provider": create_schema_provider(schema_dir=str(schema_dir)),
                "validation_enabled": True,
                "strict": True,
            },
        )

        # Create in-memory document store for testing
        store_config = load_driver_config(service=None, adapter="document_store", driver="inmemory", fields={})
        document_store = create_document_store(driver_name="inmemory", driver_config=store_config)
        document_store.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(
            config, publisher, document_store=document_store, archive_store=archive_store, logger=test_logger
        )

        # Ingest all sources
        results = service.ingest_all_enabled_sources()

        # Verify results - now returns Dict[str, Optional[Exception]]
        assert len(results) == 3
        for source_name, exception in results.items():
            # None indicates success, any Exception indicates failure
            assert exception is None, f"Source {source_name} failed with: {exception}"

        # Verify archives collection was populated
        archives = document_store.query_documents("archives", {})
        assert len(archives) == 3

        # Verify each archive has correct structure (storage-agnostic)
        for archive in archives:
            assert "_id" in archive
            assert archive["status"] == "pending"
            assert archive["message_count"] == 0
            assert "ingestion_date" in archive
            # file_path no longer stored for storage-agnostic mode
            assert "source" in archive

        # Verify ingestion log
        log_path = os.path.join(
            temp_environment["storage_path"], "metadata", "ingestion_log.jsonl"
        )
        assert os.path.exists(log_path)

        with open(log_path) as f:
            lines = f.readlines()
            assert len(lines) == 3

        # Verify events were published (noop publisher exposes published_events directly)
        assert len(publisher.published_events) == 3

        # All should be success events
        for event_wrapper in publisher.published_events:
            assert event_wrapper["event"]["event_type"] == "ArchiveIngested"

    def test_ingestion_with_duplicates(self, temp_environment, test_sources, test_logger):
        """Test ingestion handling of duplicate archives."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
        )

        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher.connect()

        # Create document store for deduplication
        store_config = load_driver_config(service=None, adapter="document_store", driver="inmemory", fields={})
        document_store = create_document_store(driver_name="inmemory", driver_config=store_config)
        document_store.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(
            config, publisher, document_store=document_store, archive_store=archive_store, logger=test_logger
        )

        # First ingestion
        results1 = service.ingest_all_enabled_sources()
        # All results should be None (success), not exceptions
        assert all(exc is None for exc in results1.values()), f"Some sources failed: {results1}"

        initial_event_count = len(publisher.published_events)

        # Second ingestion (should skip duplicates via document store)
        results2 = service.ingest_all_enabled_sources()
        # All results should be None (success), not exceptions
        assert all(exc is None for exc in results2.values()), f"Some sources failed on retry: {results2}"

        # Should have same number of events (no new success events for duplicates)
        # Deduplication via document store prevents re-ingestion
        assert len(publisher.published_events) == initial_event_count

    def test_ingestion_with_mixed_sources(self, temp_environment, test_sources, test_logger):
        """Test ingestion with mix of enabled and disabled sources."""
        # Mix enabled and disabled
        test_sources[1]["enabled"] = False
        test_sources[2]["enabled"] = False

        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
        )

        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(config, publisher, archive_store=archive_store, logger=test_logger)

        results = service.ingest_all_enabled_sources()

        # Only one source should be ingested
        assert len(results) == 1
        # Result should be None (success), not an exception
        assert results["test-list-0"] is None

    def test_deduplication_persists_across_instances(self, temp_environment, test_sources, test_logger):
        """Test that deduplication via document store works across service instances."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],  # Just first source
        )

        # Create shared document store
        store_config = load_driver_config(service=None, adapter="document_store", driver="inmemory", fields={})
        document_store = create_document_store(driver_name="inmemory", driver_config=store_config)
        document_store.connect()

        # First service instance
        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher1 = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher1.connect()
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )
        service1 = IngestionService(
            config, publisher1, document_store=document_store, archive_store=archive_store, logger=test_logger
        )
        service1.ingest_all_enabled_sources()

        # Get the first archive record
        archives = document_store.query_documents("archives", {})
        assert len(archives) > 0

        # Second service instance with same document store
        publisher2 = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher2.connect()
        service2 = IngestionService(
            config, publisher2, document_store=document_store, archive_store=archive_store, logger=test_logger
        )

        # Ingest again - should skip because hash exists in document store
        service2.ingest_all_enabled_sources()

        # Should still have only the original archives (no duplicates)
        archives_after = document_store.query_documents("archives", {})
        assert len(archives_after) == len(archives)

    def test_ingestion_log_format(self, temp_environment, test_sources, test_logger):
        """Test that ingestion log has correct format."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],
        )

        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(config, publisher, archive_store=archive_store, logger=test_logger)
        service.ingest_all_enabled_sources()

        log_path = os.path.join(
            temp_environment["storage_path"], "metadata", "ingestion_log.jsonl"
        )

        with open(log_path) as f:
            for line in f:
                entry = json.loads(line)

                # Verify required fields
                assert "archive_id" in entry
                assert "source_name" in entry
                assert "source_type" in entry
                assert "source_url" in entry
                assert "file_path" in entry
                assert "file_size_bytes" in entry
                assert "file_hash_sha256" in entry
                assert "ingestion_started_at" in entry
                assert "ingestion_completed_at" in entry
                assert "status" in entry

    def test_published_event_format(self, temp_environment, test_sources, test_logger):
        """Test that published events have correct format."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],
        )

        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(config, publisher, archive_store=archive_store, logger=test_logger)
        service.ingest_all_enabled_sources()

        # Get published events
        assert len(publisher.published_events) >= 1

        for event_wrapper in publisher.published_events:
            event = event_wrapper["event"]

            # Verify event structure
            assert "event_type" in event
            assert "event_id" in event
            assert "timestamp" in event
            assert "version" in event
            assert "data" in event

            # Verify event data (schema-required fields; file_path is optional per storage-agnostic design)
            if event["event_type"] == "ArchiveIngested":
                data = event["data"]
                assert "archive_id" in data
                assert "source_name" in data
                assert "source_type" in data
                assert "source_url" in data
                # file_path is optional (omitted for storage-agnostic mode)
                assert "file_size_bytes" in data
                assert "file_hash_sha256" in data
                assert "ingestion_started_at" in data
                assert "ingestion_completed_at" in data

    def test_storage_directory_structure(self, temp_environment, test_sources, test_logger):
        """Test that storage directory structure is correct."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:2],
        )

        publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})
        publisher = create_publisher(driver_name="noop", driver_config=publisher_config)
        publisher.connect()

        # Create archive store for local file operations
        from copilot_config.generated.adapters.archive_store import (
            AdapterConfig_ArchiveStore,
            DriverConfig_ArchiveStore_Local,
        )

        archive_store = create_archive_store(
            AdapterConfig_ArchiveStore(
                archive_store_type="local",
                driver=DriverConfig_ArchiveStore_Local(
                    archive_base_path=temp_environment["storage_path"],
                ),
            )
        )

        service = IngestionService(config, publisher, archive_store=archive_store, logger=test_logger)
        service.ingest_all_enabled_sources()

        storage_path = temp_environment["storage_path"]

        # Verify directory structure
        assert os.path.exists(storage_path)
        assert os.path.exists(os.path.join(storage_path, "metadata"))

        # Verify source directories were created by ArchiveStore
        for source in test_sources[:2]:
            source_dir = os.path.join(storage_path, source["name"])
            assert os.path.exists(source_dir)

        # Verify metadata files (checksums.json no longer created)
        assert os.path.exists(os.path.join(storage_path, "metadata", "ingestion_log.jsonl"))






