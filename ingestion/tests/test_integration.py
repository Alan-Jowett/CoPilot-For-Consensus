# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the ingestion service."""

import json
import os
import tempfile

import pytest
from app.service import IngestionService
from copilot_events import NoopPublisher, ValidatingEventPublisher
from copilot_schema_validation import FileSchemaProvider

from .test_helpers import make_config, make_source


class TestIngestionIntegration:
    """Integration tests for the complete ingestion workflow."""

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

    def test_end_to_end_ingestion(self, temp_environment, test_sources):
        """Test complete end-to-end ingestion workflow."""
        from pathlib import Path

        from copilot_storage import InMemoryDocumentStore

        # Create configuration
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
            retry_max_attempts=1,
        )

        # Create publisher and service
        base_publisher = NoopPublisher()
        base_publisher.connect()
        # Wrap with schema validation for events
        schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "events"
        schema_provider = FileSchemaProvider(schema_dir=schema_dir)
        publisher = ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )

        # Create in-memory document store for testing
        document_store = InMemoryDocumentStore()
        document_store.connect()

        service = IngestionService(config, publisher, document_store=document_store)

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

        # Verify each archive has correct structure
        for archive in archives:
            assert "_id" in archive
            assert archive["status"] == "pending"
            assert archive["message_count"] == 0
            assert "ingestion_date" in archive
            assert "file_path" in archive
            assert "source" in archive

        # Verify checksums were saved
        checksums_path = os.path.join(
            temp_environment["storage_path"], "metadata", "checksums.json"
        )
        assert os.path.exists(checksums_path)

        with open(checksums_path) as f:
            checksums = json.load(f)
            assert len(checksums) == 3

        # Verify ingestion log
        log_path = os.path.join(
            temp_environment["storage_path"], "metadata", "ingestion_log.jsonl"
        )
        assert os.path.exists(log_path)

        with open(log_path) as f:
            lines = f.readlines()
            assert len(lines) == 3

        # Verify events were published
        # Validate events published on underlying NoopPublisher
        assert len(base_publisher.published_events) == 3

        # All should be success events
        for event_wrapper in base_publisher.published_events:
            assert event_wrapper["event"]["event_type"] == "ArchiveIngested"

    def test_ingestion_with_duplicates(self, temp_environment, test_sources):
        """Test ingestion handling of duplicate archives."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
        )

        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config, publisher)

        # First ingestion
        results1 = service.ingest_all_enabled_sources()
        # All results should be None (success), not exceptions
        assert all(exc is None for exc in results1.values()), f"Some sources failed: {results1}"

        initial_event_count = len(publisher.published_events)

        # Second ingestion (should skip duplicates)
        results2 = service.ingest_all_enabled_sources()
        # All results should be None (success), not exceptions
        assert all(exc is None for exc in results2.values()), f"Some sources failed on retry: {results2}"

        # Should have same number of events (no new success events for duplicates)
        # Note: actual behavior depends on implementation
        # For now we expect same count if duplicates are skipped
        assert len(publisher.published_events) == initial_event_count

    def test_ingestion_with_mixed_sources(self, temp_environment, test_sources):
        """Test ingestion with mix of enabled and disabled sources."""
        # Mix enabled and disabled
        test_sources[1]["enabled"] = False
        test_sources[2]["enabled"] = False

        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources,
        )

        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config, publisher)

        results = service.ingest_all_enabled_sources()

        # Only one source should be ingested
        assert len(results) == 1
        # Result should be None (success), not an exception
        assert results["test-list-0"] is None

    def test_checksums_persist_across_instances(self, temp_environment, test_sources):
        """Test that checksums persist across service instances."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],  # Just first source
        )

        # First service instance
        publisher1 = NoopPublisher()
        publisher1.connect()
        service1 = IngestionService(config, publisher1)
        service1.ingest_all_enabled_sources()

        first_checksum = list(service1.checksums.keys())[0]

        # Second service instance
        publisher2 = NoopPublisher()
        publisher2.connect()
        service2 = IngestionService(config, publisher2)

        # Verify checksum was loaded
        assert first_checksum in service2.checksums

    def test_ingestion_log_format(self, temp_environment, test_sources):
        """Test that ingestion log has correct format."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],
        )

        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config, publisher)
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

    def test_published_event_format(self, temp_environment, test_sources):
        """Test that published events have correct format."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:1],
        )

        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config, publisher)
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

            # Verify event data
            if event["event_type"] == "ArchiveIngested":
                data = event["data"]
                assert "archive_id" in data
                assert "source_name" in data
                assert "source_type" in data
                assert "source_url" in data
                assert "file_path" in data
                assert "file_size_bytes" in data
                assert "file_hash_sha256" in data
                assert "ingestion_started_at" in data
                assert "ingestion_completed_at" in data

    def test_storage_directory_structure(self, temp_environment, test_sources):
        """Test that storage directory structure is correct."""
        config = make_config(
            storage_path=temp_environment["storage_path"],
            sources=test_sources[:2],
        )

        publisher = NoopPublisher()
        publisher.connect()

        service = IngestionService(config, publisher)
        service.ingest_all_enabled_sources()

        storage_path = temp_environment["storage_path"]

        # Verify directory structure
        assert os.path.exists(storage_path)
        assert os.path.exists(os.path.join(storage_path, "metadata"))

        # Verify source directories were created
        for source in test_sources[:2]:
            source_dir = os.path.join(storage_path, source["name"])
            assert os.path.exists(source_dir)

        # Verify metadata files
        assert os.path.exists(os.path.join(storage_path, "metadata", "checksums.json"))
        assert os.path.exists(os.path.join(storage_path, "metadata", "ingestion_log.jsonl"))
