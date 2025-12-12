# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the reporting service API."""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi.testclient import TestClient

# Import main app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app, reporting_service
from app.service import ReportingService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.insert_document = Mock(return_value="report_123")
    store.query_documents = Mock(return_value=[])
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
def test_service(mock_document_store, mock_publisher, mock_subscriber):
    """Create a test reporting service instance."""
    return ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
    )


@pytest.fixture
def client(test_service, monkeypatch):
    """Create a test client with mocked service."""
    # Monkey patch the global service
    import main
    monkeypatch.setattr(main, "reporting_service", test_service)
    
    return TestClient(app)


@pytest.mark.integration
def test_health_endpoint(client, test_service):
    """Test the health endpoint."""
    test_service.reports_stored = 5
    test_service.notifications_sent = 3
    
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "reporting"
    assert data["reports_stored"] == 5
    assert data["notifications_sent"] == 3


@pytest.mark.integration
def test_stats_endpoint(client, test_service):
    """Test the stats endpoint."""
    test_service.reports_stored = 10
    test_service.notifications_sent = 8
    test_service.notifications_failed = 2
    test_service.last_processing_time = 1.5
    
    response = client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["reports_stored"] == 10
    assert data["notifications_sent"] == 8
    assert data["notifications_failed"] == 2
    assert data["last_processing_time_seconds"] == 1.5


@pytest.mark.integration
def test_get_reports_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "summary_id": "rpt1",
            "thread_id": "thread1",
            "content_markdown": "Summary 1",
        },
        {
            "summary_id": "rpt2",
            "thread_id": "thread2",
            "content_markdown": "Summary 2",
        },
    ]
    
    response = client.get("/api/reports")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["count"] == 2
    assert len(data["reports"]) == 2
    assert data["reports"][0]["summary_id"] == "rpt1"


@pytest.mark.integration
def test_get_reports_with_thread_filter(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with thread_id filter."""
    mock_document_store.query_documents.return_value = [
        {
            "summary_id": "rpt1",
            "thread_id": "thread1",
            "content_markdown": "Summary 1",
        },
    ]
    
    response = client.get("/api/reports?thread_id=thread1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["count"] == 1
    assert data["reports"][0]["thread_id"] == "thread1"
    
    # Verify the service was called with correct filter
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filters"]["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_reports_with_pagination(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with pagination."""
    mock_document_store.query_documents.return_value = []
    
    response = client.get("/api/reports?limit=5&skip=10")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["limit"] == 5
    assert data["skip"] == 10
    
    # Verify the service was called with correct pagination
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["limit"] == 5
    assert call_args[1]["skip"] == 10


@pytest.mark.integration
def test_get_report_by_id_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/reports/{report_id} endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "summary_id": "rpt1",
            "thread_id": "thread1",
            "content_markdown": "Test summary",
            "citations": [],
        },
    ]
    
    response = client.get("/api/reports/rpt1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["summary_id"] == "rpt1"
    assert data["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_report_by_id_not_found(client, test_service, mock_document_store):
    """Test the GET /api/reports/{report_id} endpoint when report not found."""
    mock_document_store.query_documents.return_value = []
    
    response = client.get("/api/reports/nonexistent")
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.integration
def test_get_thread_summary_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/threads/{thread_id}/summary endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "summary_id": "rpt1",
            "thread_id": "thread1",
            "content_markdown": "Latest summary for thread",
            "citations": [],
        },
    ]
    
    response = client.get("/api/threads/thread1/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["thread_id"] == "thread1"
    assert "Latest summary" in data["content_markdown"]


@pytest.mark.integration
def test_get_thread_summary_not_found(client, test_service, mock_document_store):
    """Test the GET /api/threads/{thread_id}/summary endpoint when not found."""
    mock_document_store.query_documents.return_value = []
    
    response = client.get("/api/threads/nonexistent/summary")
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.integration
def test_get_reports_service_not_initialized(monkeypatch):
    """Test endpoints when service is not initialized."""
    import main
    monkeypatch.setattr(main, "reporting_service", None)
    
    client = TestClient(app)
    
    response = client.get("/api/reports")
    assert response.status_code == 503
    
    response = client.get("/api/reports/rpt1")
    assert response.status_code == 503
    
    response = client.get("/api/threads/thread1/summary")
    assert response.status_code == 503
