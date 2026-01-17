# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion API endpoints."""

import pytest
from unittest.mock import patch

from app.api import create_api_router
from app.service import IngestionService
from copilot_config.generated.adapters.document_store import AdapterConfig_DocumentStore, DriverConfig_DocumentStore_Inmemory
from copilot_config.generated.adapters.error_reporter import AdapterConfig_ErrorReporter, DriverConfig_ErrorReporter_Silent
from copilot_config.generated.adapters.logger import AdapterConfig_Logger, DriverConfig_Logger_Silent
from copilot_config.generated.adapters.message_bus import AdapterConfig_MessageBus, DriverConfig_MessageBus_Noop
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics, DriverConfig_Metrics_Noop
from copilot_error_reporting import create_error_reporter
from copilot_message_bus import create_publisher
from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector
from copilot_storage import create_document_store
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_helpers import make_config


@pytest.fixture
def document_store():
    """Create in-memory document store for testing."""
    store = create_document_store(
        AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
        enable_validation=False,
    )
    store.connect()
    return store


@pytest.fixture
def service(document_store, tmp_path):
    """Create ingestion service for testing."""
    from .test_helpers import make_archive_store

    sources: list[dict] = []
    config = make_config(
        storage_path=str(tmp_path / "raw_archives"),
    )

    publisher = create_publisher(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    publisher.connect()

    logger = create_logger(
        AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"))
    )
    metrics = create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))
    error_reporter = create_error_reporter(
        AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
    )
    archive_store = make_archive_store(base_path=config.service_settings.storage_path or str(tmp_path / "raw_archives"))

    service = IngestionService(
        config,
        publisher,
        sources=sources,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=archive_store,
    )
    service.version = "test-1.0.0"

    return service


@pytest.fixture
def client(service):
    """Create test client for API."""
    logger = create_logger(
        AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="api-test"))
    )

    app = FastAPI()
    api_router = create_api_router(service, logger)
    app.include_router(api_router)

    return TestClient(app)


class TestStatsEndpoint:
    """Tests for /stats endpoint."""

    def test_get_stats(self, client):
        """Test stats endpoint returns service statistics."""
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()

        assert "sources_configured" in data
        assert "sources_enabled" in data
        assert "total_files_ingested" in data


class TestSourcesEndpoints:
    """Tests for sources CRUD endpoints."""

    def test_list_sources_empty(self, client):
        """Test listing sources when none configured."""
        response = client.get("/api/sources")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 0
        assert data["sources"] == []

    def test_create_source(self, client):
        """Test creating a new source."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        response = client.post("/api/sources", json=source_data)

        assert response.status_code == 201
        data = response.json()

        assert "source" in data
        assert data["source"]["name"] == "test-source"
        assert data["source"]["source_type"] == "http"

    def test_create_source_duplicate(self, client, service):
        """Test creating a duplicate source returns 400."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        # Create first source via API
        client.post("/api/sources", json=source_data)

        # Try to create duplicate
        response = client.post("/api/sources", json=source_data)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_source_missing_fields(self, client):
        """Test creating source with missing required fields."""
        source_data = {
            "name": "test-source",
            # Missing source_type and url
        }

        response = client.post("/api/sources", json=source_data)

        # FastAPI validation should catch this
        assert response.status_code == 422

    def test_list_sources(self, client):
        """Test listing sources."""
        # Create some sources via API
        sources = [
            {
                "name": "source-1",
                "source_type": "http",
                "url": "https://example.com/1.mbox",
                "enabled": True,
            },
            {
                "name": "source-2",
                "source_type": "rsync",
                "url": "rsync://example.com/2",
                "enabled": False,
            },
        ]

        for source in sources:
            client.post("/api/sources", json=source)

        response = client.get("/api/sources")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 2
        assert len(data["sources"]) == 2

    def test_list_sources_enabled_only(self, client):
        """Test listing only enabled sources."""
        sources = [
            {
                "name": "source-1",
                "source_type": "http",
                "url": "https://example.com/1.mbox",
                "enabled": True,
            },
            {
                "name": "source-2",
                "source_type": "rsync",
                "url": "rsync://example.com/2",
                "enabled": False,
            },
        ]

        for source in sources:
            client.post("/api/sources", json=source)

        response = client.get("/api/sources?enabled_only=true")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert data["sources"][0]["name"] == "source-1"

    def test_get_source(self, client):
        """Test getting a specific source."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        client.post("/api/sources", json=source_data)

        response = client.get("/api/sources/test-source")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "test-source"
        assert data["source_type"] == "http"

    def test_get_source_not_found(self, client):
        """Test getting a non-existent source."""
        response = client.get("/api/sources/nonexistent")

        assert response.status_code == 404

    def test_update_source(self, client):
        """Test updating a source."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        client.post("/api/sources", json=source_data)

        # Update the source
        updated_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/updated.mbox",
            "enabled": False,
        }

        response = client.put("/api/sources/test-source", json=updated_data)

        assert response.status_code == 200
        data = response.json()

        assert data["source"]["url"] == "https://example.com/updated.mbox"
        assert data["source"]["enabled"] is False

    def test_update_source_name_mismatch(self, client):
        """Test updating source with mismatched names."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        client.post("/api/sources", json=source_data)

        # Try to update with different name
        updated_data = {
            "name": "different-name",
            "source_type": "http",
            "url": "https://example.com/updated.mbox",
            "enabled": False,
        }

        response = client.put("/api/sources/test-source", json=updated_data)

        assert response.status_code == 400

    def test_update_source_not_found(self, client):
        """Test updating a non-existent source."""
        updated_data = {
            "name": "nonexistent",
            "source_type": "http",
            "url": "https://example.com/updated.mbox",
            "enabled": False,
        }

        response = client.put("/api/sources/nonexistent", json=updated_data)

        assert response.status_code == 404

    def test_delete_source(self, client):
        """Test deleting a source."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        client.post("/api/sources", json=source_data)

        response = client.delete("/api/sources/test-source")

        assert response.status_code == 200
        data = response.json()

        assert "deleted successfully" in data["message"]

    def test_delete_source_not_found(self, client):
        """Test deleting a non-existent source."""
        response = client.delete("/api/sources/nonexistent")

        assert response.status_code == 404

    def test_delete_source_with_cascade(self, client, service):
        """Test deleting a source with cascade=true."""
        # Create a source
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }
        client.post("/api/sources", json=source_data)

        # Add some mock data to document store to simulate associated data
        if service.document_store:
            # Add an archive
            service.document_store.insert_document("archives", {
                "_id": "archive-123",
                "source": "test-source",
                "file_hash": "abc123",
            })
            # Add a thread
            service.document_store.insert_document("threads", {
                "_id": "thread-123",
                "source": "test-source",
            })
            # Add a message
            service.document_store.insert_document("messages", {
                "_id": "message-123",
                "source": "test-source",
            })
            # Add a chunk
            service.document_store.insert_document("chunks", {
                "_id": "chunk-123",
                "source": "test-source",
            })
            # Add a summary
            service.document_store.insert_document("summaries", {
                "_id": "summary-123",
                "source": "test-source",
            })

        # Delete with cascade
        response = client.delete("/api/sources/test-source?cascade=true")

        assert response.status_code == 200
        data = response.json()

        assert data["cascade"] is True
        assert "deletion_counts" in data
        assert "deleted successfully" in data["message"]

        # Verify associated data was deleted
        if service.document_store:
            archives_after = service.document_store.query_documents("archives", {"source": "test-source"})
            assert len(archives_after) == 0

            threads_after = service.document_store.query_documents("threads", {"source": "test-source"})
            assert len(threads_after) == 0

            messages_after = service.document_store.query_documents("messages", {"source": "test-source"})
            assert len(messages_after) == 0

            chunks_after = service.document_store.query_documents("chunks", {"source": "test-source"})
            assert len(chunks_after) == 0

            summaries_after = service.document_store.query_documents("summaries", {"source": "test-source"})
            assert len(summaries_after) == 0

    def test_delete_source_without_cascade(self, client, service):
        """Test deleting a source without cascade (default behavior)."""
        # Create a source
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }
        client.post("/api/sources", json=source_data)

        # Add some mock data to document store to simulate associated data
        if service.document_store:
            # Add an archive
            service.document_store.insert_document("archives", {
                "_id": "archive-456",
                "source": "test-source",
                "file_hash": "def456",
            })

        # Delete without cascade (default)
        response = client.delete("/api/sources/test-source")

        assert response.status_code == 200
        data = response.json()

        assert data["cascade"] is False
        assert "deleted successfully" in data["message"]

        # Verify associated data was NOT deleted
        if service.document_store:
            archives_after = service.document_store.query_documents("archives", {"source": "test-source"})
            assert len(archives_after) == 1  # Archive should still exist

    def test_delete_source_cascade_partial_failure(self, client, service):
        """Test cascade delete with partial failures - verifies non-blocking error handling."""
        # Create a source
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }
        client.post("/api/sources", json=source_data)

        # Add test data
        if service.document_store:
            service.document_store.insert_document("archives", {
                "_id": "archive-123",
                "source": "test-source",
                "file_hash": "abc123",
            })
            service.document_store.insert_document("threads", {
                "_id": "thread-123",
                "source": "test-source",
            })
            service.document_store.insert_document("threads", {
                "_id": "thread-456",
                "source": "test-source",
            })
            service.document_store.insert_document("messages", {
                "_id": "message-123",
                "source": "test-source",
            })

        # Mock delete_document to fail for one specific thread
        original_delete = service.document_store.delete_document
        def mock_delete(collection, doc_id):
            if collection == "threads" and doc_id == "thread-123":
                raise Exception("Simulated deletion failure")
            return original_delete(collection, doc_id)
        
        with patch.object(service.document_store, 'delete_document', side_effect=mock_delete):
            response = client.delete("/api/sources/test-source?cascade=true")

        assert response.status_code == 200
        data = response.json()
        
        # Should still succeed overall, with partial counts
        assert data["cascade"] is True
        assert "deletion_counts" in data
        # One thread should have been deleted, one failed
        assert data["deletion_counts"]["threads"] == 1

    def test_delete_source_cascade_with_archive_store(self, client, service):
        """Test cascade delete verifies archive_store deletions."""
        # Create a source
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }
        client.post("/api/sources", json=source_data)

        # Add archive to document store
        if service.document_store:
            service.document_store.insert_document("archives", {
                "_id": "archive-123",
                "source": "test-source",
                "file_hash": "abc123",
            })

        # Track archive_store delete calls
        delete_archive_calls = []
        
        def track_delete_archive(archive_id):
            delete_archive_calls.append(archive_id)
            return True
        
        # Use patch.object as context manager for clean teardown
        with patch.object(service.archive_store, 'delete_archive', side_effect=track_delete_archive):
            response = client.delete("/api/sources/test-source?cascade=true")

        assert response.status_code == 200
        data = response.json()
        
        # Verify archive_store.delete_archive was called
        assert len(delete_archive_calls) == 1
        assert "archive-123" in delete_archive_calls
        
        # Verify deletion count includes archive_store
        assert data["deletion_counts"]["archives_archivestore"] == 1


class TestSourceStatusEndpoint:
    """Tests for source status endpoint."""

    def test_get_source_status(self, client):
        """Test getting source status."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": True,
        }

        client.post("/api/sources", json=source_data)

        response = client.get("/api/sources/test-source/status")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "test-source"
        assert data["enabled"] is True
        assert "last_run_at" in data
        assert "last_run_status" in data

    def test_get_source_status_not_found(self, client):
        """Test getting status for non-existent source."""
        response = client.get("/api/sources/nonexistent/status")

        assert response.status_code == 404


class TestTriggerIngestionEndpoint:
    """Tests for trigger ingestion endpoint."""

    def test_trigger_ingestion_not_found(self, client):
        """Test triggering ingestion for non-existent source."""
        response = client.post("/api/sources/nonexistent/trigger")

        assert response.status_code == 400

    def test_trigger_ingestion_disabled_source(self, client):
        """Test triggering ingestion for disabled source."""
        source_data = {
            "name": "test-source",
            "source_type": "http",
            "url": "https://example.com/archive.mbox",
            "enabled": False,
        }

        client.post("/api/sources", json=source_data)

        response = client.post("/api/sources/test-source/trigger")

        assert response.status_code == 400
        assert "disabled" in response.json()["detail"]

    def test_trigger_ingestion_deletes_hash_for_reprocessing(self, client, service):
        """Test that triggering ingestion deletes archives from document store to allow reprocessing."""
        import os
        import tempfile

        # Create a test file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.mbox")
            with open(test_file, "w") as f:
                f.write("From: test@example.com\nSubject: Test\n\nBody")

            # Create a source with the test file
            source_data = {
                "name": "test-source",
                "source_type": "local",
                "url": test_file,
                "enabled": True,
            }
            client.post("/api/sources", json=source_data)

            # First trigger - should ingest the file
            response1 = client.post("/api/sources/test-source/trigger")
            assert response1.status_code == 200

            # Verify an archive was created in document store
            archives_before = service.document_store.query_documents("archives", {"source": "test-source"})
            assert len(archives_before) > 0

            # Second trigger - should delete the archives and re-ingest
            response2 = client.post("/api/sources/test-source/trigger")
            assert response2.status_code == 200

            # Verify archives still exist (re-ingested)
            archives_after = service.document_store.query_documents("archives", {"source": "test-source"})
            assert len(archives_after) > 0


class TestUploadEndpoint:
    """Tests for file upload endpoint."""

    def test_upload_mbox_file(self, client):
        """Test uploading a valid .mbox file."""
        file_content = b"From: test@example.com\nSubject: Test\n\nBody"
        files = {"file": ("test.mbox", file_content, "application/mbox")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 201
        data = response.json()

        assert "filename" in data
        assert "server_path" in data
        assert "size_bytes" in data
        assert data["size_bytes"] == len(file_content)
        assert data["suggested_source_type"] == "local"
        assert data["filename"].endswith(".mbox")

    def test_upload_zip_file(self, client):
        """Test uploading a .zip file."""
        # Minimal ZIP file (empty archive)
        zip_content = b"PK\x05\x06" + b"\x00" * 18
        files = {"file": ("archive.zip", zip_content, "application/zip")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"].endswith(".zip")

    def test_upload_invalid_extension(self, client):
        """Test uploading file with invalid extension."""
        file_content = b"test content"
        files = {"file": ("test.txt", file_content, "text/plain")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_empty_file(self, client):
        """Test uploading an empty file."""
        files = {"file": ("test.mbox", b"", "application/mbox")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_upload_sanitizes_filename(self, client):
        """Test that filenames are sanitized."""
        file_content = b"test content"
        # Filename with path traversal attempt
        files = {"file": ("../../etc/passwd.mbox", file_content, "application/mbox")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 201
        data = response.json()

        # Filename should be sanitized
        assert ".." not in data["filename"]
        assert "/" not in data["filename"]

    def test_upload_duplicate_filename(self, client):
        """Test uploading files with duplicate names."""
        file_content = b"test content"
        files = {"file": ("test.mbox", file_content, "application/mbox")}

        # Upload first file
        response1 = client.post("/api/uploads", files=files)
        assert response1.status_code == 201
        filename1 = response1.json()["filename"]

        # Upload second file with same name
        response2 = client.post("/api/uploads", files=files)
        assert response2.status_code == 201
        filename2 = response2.json()["filename"]

        # Filenames should be different (second should have counter)
        assert filename1 != filename2
        assert "test" in filename2
        assert ".mbox" in filename2

    def test_upload_file_too_large(self, client, monkeypatch):
        """Test uploading a file exceeding size limit."""
        # Mock MAX_UPLOAD_SIZE to avoid allocating 101MB in tests
        import app.api
        original_max = app.api.MAX_UPLOAD_SIZE
        monkeypatch.setattr(app.api, 'MAX_UPLOAD_SIZE', 1000)  # 1KB limit for testing

        try:
            # Create file content larger than mocked limit
            file_content = b"x" * 1500  # 1.5KB
            files = {"file": ("large.mbox", file_content, "application/mbox")}

            response = client.post("/api/uploads", files=files)

            assert response.status_code == 413
            assert "too large" in response.json()["detail"].lower()
        finally:
            # Restore original value
            monkeypatch.setattr(app.api, 'MAX_UPLOAD_SIZE', original_max)

    def test_upload_tar_gz_compound_extension(self, client):
        """Test uploading a file with compound extension (.tar.gz)."""
        file_content = b"test archive content"
        files = {"file": ("archive.tar.gz", file_content, "application/gzip")}

        response = client.post("/api/uploads", files=files)

        assert response.status_code == 201
        data = response.json()

        # Verify compound extension is preserved
        assert data["filename"].endswith(".tar.gz")
        assert "archive" in data["filename"]




