# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the reporting service API."""

import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient

from main import app
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
def test_root_endpoint(client, test_service):
    """Test the root endpoint."""
    test_service.reports_stored = 5
    test_service.notifications_sent = 3
    
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "reporting"
    assert data["reports_stored"] == 5
    assert data["notifications_sent"] == 3


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
    assert call_args[1]["filter_dict"]["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_reports_with_pagination(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with pagination."""
    mock_document_store.query_documents.return_value = []
    
    response = client.get("/api/reports?limit=5&skip=10")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["limit"] == 5
    assert data["skip"] == 10
    
    # New implementation fetches limit + skip + 100 for filtering buffer
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["limit"] == 115  # 5 (limit) + 10 (skip) + 100 (buffer)


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


@pytest.mark.integration
def test_get_reports_with_date_filters(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with date filters."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1", "generated_at": "2025-01-15T12:00:00Z"},
    ]
    
    response = client.get("/api/reports?start_date=2025-01-01T00:00:00Z&end_date=2025-01-31T23:59:59Z")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["count"] == 1
    
    # Verify the service was called with date filters
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    filter_dict = call_args[1]["filter_dict"]
    assert "generated_at" in filter_dict


@pytest.mark.integration
def test_get_reports_with_source_filter(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with source filter."""
    # Setup mocks to return thread and archive data
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{"summary_id": "rpt1", "thread_id": "thread1"}]
        elif collection == "threads":
            return [{
                "thread_id": "thread1",
                "archive_id": "archive1",
                "participants": [],
                "message_count": 5,
            }]
        elif collection == "archives":
            return [{
                "archive_id": "archive1",
                "source": "test-source",
            }]
        return []
    
    mock_document_store.query_documents.side_effect = mock_query
    
    response = client.get("/api/reports?source=test-source")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return enriched report with archive metadata
    assert len(data["reports"]) == 1


@pytest.mark.integration
def test_get_reports_with_metadata_filters(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with metadata filters."""
    # Setup mocks
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{"summary_id": "rpt1", "thread_id": "thread1"}]
        elif collection == "threads":
            return [{
                "thread_id": "thread1",
                "participants": [{"email": "user1@example.com"}, {"email": "user2@example.com"}],
                "message_count": 10,
                "archive_id": "archive1",
            }]
        elif collection == "archives":
            return [{"archive_id": "archive1", "source": "test"}]
        return []
    
    mock_document_store.query_documents.side_effect = mock_query
    
    response = client.get("/api/reports?min_participants=2&min_messages=5&max_messages=15")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return enriched report
    assert len(data["reports"]) == 1
    assert "thread_metadata" in data["reports"][0]


@pytest.mark.integration
def test_search_reports_by_topic_endpoint(client, test_service):
    """Test the GET /api/reports/search endpoint."""
    # Setup mocks for vector store and embedding provider
    test_service.vector_store = Mock()
    test_service.embedding_provider = Mock()
    
    test_service.embedding_provider.embed.return_value = [0.1] * 384
    
    mock_result = Mock()
    mock_result.id = "chunk1"
    mock_result.score = 0.85
    mock_result.metadata = {"thread_id": "thread1"}
    test_service.vector_store.query.return_value = [mock_result]
    
    # Mock document store
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{
                "summary_id": "rpt1",
                "thread_id": "thread1",
                "content_markdown": "Test",
            }]
        return []
    
    test_service.document_store.query_documents.side_effect = mock_query
    
    response = client.get("/api/reports/search?topic=test%20topic")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["topic"] == "test topic"
    assert len(data["reports"]) == 1
    assert data["reports"][0]["relevance_score"] == 0.85


@pytest.mark.integration
def test_search_reports_by_topic_not_configured(client, test_service):
    """Test the GET /api/reports/search endpoint when topic search not configured."""
    # Service doesn't have vector_store or embedding_provider
    response = client.get("/api/reports/search?topic=test")
    
    assert response.status_code == 400
    data = response.json()
    assert "vector store" in data["detail"].lower()


@pytest.mark.integration
def test_get_available_sources_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/sources endpoint."""
    mock_document_store.query_documents.return_value = [
        {"archive_id": "arch1", "source": "source-a"},
        {"archive_id": "arch2", "source": "source-b"},
        {"archive_id": "arch3", "source": "source-a"},
    ]
    
    response = client.get("/api/sources")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["count"] == 2
    assert "source-a" in data["sources"]
    assert "source-b" in data["sources"]
