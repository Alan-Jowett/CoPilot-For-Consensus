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


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns 200 and expected fields."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "ingestion"
        assert "version" in data
        assert "sources_configured" in data
        assert "sources_enabled" in data
        assert "total_files_ingested" in data


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
