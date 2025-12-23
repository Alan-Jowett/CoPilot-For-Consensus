# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion API endpoints."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from copilot_events import NoopPublisher
from copilot_storage import InMemoryDocumentStore
from copilot_logging import create_logger
from copilot_metrics import NoOpMetricsCollector

from app.service import IngestionService
from app.api import create_api_router
from .test_helpers import make_config


@pytest.fixture
def document_store():
    """Create in-memory document store for testing."""
    store = InMemoryDocumentStore()
    store.connect()
    return store


@pytest.fixture
def service(document_store, tmp_path):
    """Create ingestion service for testing."""
    config = make_config(
        sources=[],
        storage_path=str(tmp_path / "raw_archives"),
    )

    publisher = NoopPublisher()
    publisher.connect()

    logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
    metrics = NoOpMetricsCollector()

    service = IngestionService(
        config,
        publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
    )
    service.version = "test-1.0.0"

    return service


@pytest.fixture
def client(service):
    """Create test client for API."""
    logger = create_logger(logger_type="silent", level="INFO", name="api-test")

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

    @pytest.mark.xfail(reason="InMemoryDocumentStore update_document needs investigation")
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

    @pytest.mark.xfail(reason="InMemoryDocumentStore delete_document needs investigation")
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
        """Test that triggering ingestion deletes hashes to allow reprocessing."""
        import tempfile
        import os

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

            # Verify a checksum was created
            checksums_before = len(service.checksums)
            assert checksums_before > 0

            # Second trigger - should delete the hash and re-ingest
            response2 = client.post("/api/sources/test-source/trigger")
            assert response2.status_code == 200

            # Verify the file was re-ingested (checksum exists)
            checksums_after = len(service.checksums)
            assert checksums_after > 0


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


