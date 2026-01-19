# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the reporting service API."""

from unittest.mock import Mock

import pytest
from app.service import ReportingService
from fastapi.testclient import TestClient
from main import app


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

    # Verify the first call used the correct summaries filter
    first_call = mock_document_store.query_documents.call_args_list[0]
    assert first_call[0][0] == "summaries"
    assert first_call[1]["filter_dict"]["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_reports_with_pagination(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with pagination."""
    mock_document_store.query_documents.return_value = []

    response = client.get("/api/reports?limit=5&skip=10")

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 5
    assert data["skip"] == 10

    # First call fetches limit + skip + METADATA_FILTER_BUFFER_SIZE (100)
    first_call = mock_document_store.query_documents.call_args_list[0]
    assert first_call[1]["limit"] == 115


@pytest.mark.integration
def test_get_reports_sorting_by_thread_start_date(client, test_service, mock_document_store):
    """Test sorting reports by thread_start_date in descending order."""
    # Mock summaries with different thread start dates
    mock_document_store.query_documents.side_effect = [
        # First call: fetch summaries
        [
            {"_id": "rpt1", "thread_id": "thread1", "generated_at": "2025-01-15T10:00:00Z"},
            {"_id": "rpt2", "thread_id": "thread2", "generated_at": "2025-01-14T10:00:00Z"},
            {"_id": "rpt3", "thread_id": "thread3", "generated_at": "2025-01-13T10:00:00Z"},
        ],
        # Second call: fetch threads
        [
            {
                "thread_id": "thread1",
                "first_message_date": "2025-01-10T00:00:00Z",
                "participants": [],
                "message_count": 5,
            },
            {
                "thread_id": "thread2",
                "first_message_date": "2025-01-12T00:00:00Z",
                "participants": [],
                "message_count": 3,
            },
            {
                "thread_id": "thread3",
                "first_message_date": "2025-01-08T00:00:00Z",
                "participants": [],
                "message_count": 7,
            },
        ],
        # Third call: fetch archives (empty)
        [],
    ]

    response = client.get("/api/reports?sort_by=thread_start_date&sort_order=desc")

    assert response.status_code == 200
    data = response.json()

    # Verify reports are sorted by thread start date (newest first)
    assert len(data["reports"]) == 3
    assert data["reports"][0]["_id"] == "rpt2"  # thread2: 2025-01-12
    assert data["reports"][1]["_id"] == "rpt1"  # thread1: 2025-01-10
    assert data["reports"][2]["_id"] == "rpt3"  # thread3: 2025-01-08


@pytest.mark.integration
def test_get_reports_sorting_ascending(client, test_service, mock_document_store):
    """Test sorting reports in ascending order."""
    mock_document_store.query_documents.side_effect = [
        # First call: fetch summaries
        [
            {"_id": "rpt1", "thread_id": "thread1", "generated_at": "2025-01-15T10:00:00Z"},
            {"_id": "rpt2", "thread_id": "thread2", "generated_at": "2025-01-14T10:00:00Z"},
        ],
        # Second call: fetch threads
        [
            {
                "thread_id": "thread1",
                "first_message_date": "2025-01-10T00:00:00Z",
                "participants": [],
                "message_count": 5,
            },
            {
                "thread_id": "thread2",
                "first_message_date": "2025-01-12T00:00:00Z",
                "participants": [],
                "message_count": 3,
            },
        ],
        # Third call: fetch archives
        [],
    ]

    response = client.get("/api/reports?sort_by=thread_start_date&sort_order=asc")

    assert response.status_code == 200
    data = response.json()

    # Verify reports are sorted by thread start date (oldest first)
    assert len(data["reports"]) == 2
    assert data["reports"][0]["_id"] == "rpt1"  # thread1: 2025-01-10 (older)
    assert data["reports"][1]["_id"] == "rpt2"  # thread2: 2025-01-12 (newer)


@pytest.mark.integration
def test_get_reports_sorting_by_generated_at(client, test_service, mock_document_store):
    """Test sorting reports by generated_at date."""
    mock_document_store.query_documents.side_effect = [
        # First call: fetch summaries
        [
            {"_id": "rpt1", "thread_id": "thread1", "generated_at": "2025-01-15T10:00:00Z"},
            {"_id": "rpt2", "thread_id": "thread2", "generated_at": "2025-01-17T10:00:00Z"},
            {"_id": "rpt3", "thread_id": "thread3", "generated_at": "2025-01-13T10:00:00Z"},
        ],
        # Second call: fetch threads
        [
            {
                "thread_id": "thread1",
                "first_message_date": "2025-01-10T00:00:00Z",
                "participants": [],
                "message_count": 5,
            },
            {
                "thread_id": "thread2",
                "first_message_date": "2025-01-12T00:00:00Z",
                "participants": [],
                "message_count": 3,
            },
            {
                "thread_id": "thread3",
                "first_message_date": "2025-01-08T00:00:00Z",
                "participants": [],
                "message_count": 7,
            },
        ],
        # Third call: fetch archives
        [],
    ]

    response = client.get("/api/reports?sort_by=generated_at&sort_order=desc")

    assert response.status_code == 200
    data = response.json()

    # Verify reports are sorted by generated_at (newest first)
    assert len(data["reports"]) == 3
    assert data["reports"][0]["_id"] == "rpt2"  # 2025-01-17
    assert data["reports"][1]["_id"] == "rpt1"  # 2025-01-15
    assert data["reports"][2]["_id"] == "rpt3"  # 2025-01-13


@pytest.mark.integration
def test_get_reports_sorting_with_pagination(client, test_service, mock_document_store):
    """Test that sorting works correctly across paginated results."""
    mock_document_store.query_documents.side_effect = [
        # First call: fetch summaries (limit includes buffer)
        [
            {"_id": f"rpt{i}", "thread_id": f"thread{i}", "generated_at": f"2025-01-{10+i:02d}T10:00:00Z"}
            for i in range(5)
        ],
        # Second call: fetch threads
        [
            {
                "thread_id": f"thread{i}",
                "first_message_date": f"2025-01-{15-i:02d}T00:00:00Z",
                "participants": [],
                "message_count": 5,
            }
            for i in range(5)
        ],
        # Third call: fetch archives
        [],
    ]

    response = client.get("/api/reports?sort_by=thread_start_date&sort_order=desc&limit=2&skip=1")

    assert response.status_code == 200
    data = response.json()

    # Verify pagination applies after sorting
    assert data["limit"] == 2
    assert data["skip"] == 1
    assert len(data["reports"]) == 2


@pytest.mark.integration
def test_get_reports_invalid_sort_by(client, test_service, mock_document_store):
    """Test that invalid sort_by parameter is rejected."""
    response = client.get("/api/reports?sort_by=invalid_field")

    # FastAPI should return 422 for regex validation failure
    assert response.status_code == 422


@pytest.mark.integration
def test_get_reports_invalid_sort_order(client, test_service, mock_document_store):
    """Test that invalid sort_order parameter is rejected."""
    response = client.get("/api/reports?sort_order=invalid")

    # FastAPI should return 422 for regex validation failure
    assert response.status_code == 422


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
def test_get_reports_with_message_date_filters(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with message date filters."""

    # Setup mocks to return thread data
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{"summary_id": "rpt1", "thread_id": "thread1"}]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                }
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    response = client.get("/api/reports?message_start_date=2025-01-01T00:00:00Z&message_end_date=2025-01-31T23:59:59Z")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    assert data["reports"][0]["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_reports_with_message_date_filters_no_overlap(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint excludes threads with no date overlap."""

    # Setup mocks to return thread data
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{"summary_id": "rpt1", "thread_id": "thread1"}]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-20T00:00:00Z",
                    "last_message_date": "2025-01-25T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                }
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter range is 2025-01-01 to 2025-01-15, thread is 2025-01-20 to 2025-01-25
    response = client.get("/api/reports?message_start_date=2025-01-01T00:00:00Z&message_end_date=2025-01-15T23:59:59Z")

    assert response.status_code == 200
    data = response.json()

    # Should return 0 reports (no overlap)
    assert data["count"] == 0


@pytest.mark.integration
def test_get_reports_with_source_filter(client, test_service, mock_document_store):
    """Test the GET /api/reports endpoint with source filter."""

    # Setup mocks to return thread and archive data
    def mock_query(collection, filter_dict, limit):
        if collection == "summaries":
            return [{"summary_id": "rpt1", "thread_id": "thread1"}]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "archive_id": "archive1",
                    "participants": [],
                    "message_count": 5,
                }
            ]
        elif collection == "archives":
            return [
                {
                    "_id": "archive1",
                    "source": "test-source",
                }
            ]
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
            return [
                {
                    "thread_id": "thread1",
                    "participants": [{"email": "user1@example.com"}, {"email": "user2@example.com"}],
                    "message_count": 10,
                    "archive_id": "archive1",
                }
            ]
        elif collection == "archives":
            return [{"_id": "archive1", "source": "test"}]
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
            return [
                {
                    "summary_id": "rpt1",
                    "thread_id": "thread1",
                    "content_markdown": "Test",
                }
            ]
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
        {"_id": "arch1", "source": "source-a"},
        {"_id": "arch2", "source": "source-b"},
        {"_id": "arch3", "source": "source-a"},
    ]

    response = client.get("/api/sources")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 2
    assert "source-a" in data["sources"]
    assert "source-b" in data["sources"]


@pytest.mark.integration
def test_get_threads_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/threads endpoint."""
    mock_document_store.query_documents.return_value = [
        {"_id": "thread1", "subject": "Thread 1", "message_count": 5},
        {"_id": "thread2", "subject": "Thread 2", "message_count": 3},
    ]

    response = client.get("/api/threads")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 2
    assert len(data["threads"]) == 2
    assert data["threads"][0]["_id"] == "thread1"


@pytest.mark.integration
def test_get_threads_with_pagination(client, test_service, mock_document_store):
    """Test the GET /api/threads endpoint with pagination."""
    mock_document_store.query_documents.return_value = [
        {"_id": f"thread{i}", "subject": f"Thread {i}"} for i in range(5)
    ]

    response = client.get("/api/threads?limit=2&skip=1")

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 2
    assert data["skip"] == 1
    assert len(data["threads"]) == 2
    # Verify the correct subset is returned (threads at indices 1 and 2)
    assert data["threads"][0]["_id"] == "thread1"
    assert data["threads"][1]["_id"] == "thread2"


@pytest.mark.integration
def test_get_threads_with_archive_filter(client, test_service, mock_document_store):
    """Test the GET /api/threads endpoint with archive filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "thread1", "archive_id": "archive1"},
    ]

    response = client.get("/api/threads?archive_id=archive1")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    # Verify the service was called with correct filter
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["archive_id"] == "archive1"


@pytest.mark.integration
def test_get_thread_by_id_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/threads/{thread_id} endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "_id": "thread1",
            "subject": "Test Thread",
            "message_count": 10,
            "participants": [{"email": "user@example.com"}],
        },
    ]

    response = client.get("/api/threads/thread1")

    assert response.status_code == 200
    data = response.json()

    assert data["_id"] == "thread1"
    assert data["subject"] == "Test Thread"


@pytest.mark.integration
def test_get_thread_by_id_not_found(client, test_service, mock_document_store):
    """Test the GET /api/threads/{thread_id} endpoint when thread not found."""
    mock_document_store.query_documents.return_value = []

    response = client.get("/api/threads/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.integration
def test_get_messages_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/messages endpoint."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "message_id": "<msg1@example.com>", "subject": "Message 1"},
        {"_id": "msg2", "message_id": "<msg2@example.com>", "subject": "Message 2"},
    ]

    response = client.get("/api/messages")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 2
    assert len(data["messages"]) == 2
    assert data["messages"][0]["_id"] == "msg1"


@pytest.mark.integration
def test_get_messages_with_thread_filter(client, test_service, mock_document_store):
    """Test the GET /api/messages endpoint with thread_id filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "thread_id": "thread1"},
    ]

    response = client.get("/api/messages?thread_id=thread1")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    # Verify the service was called with correct filter
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["thread_id"] == "thread1"


@pytest.mark.integration
def test_get_messages_with_message_id_filter(client, test_service, mock_document_store):
    """Test the GET /api/messages endpoint with message_id filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "message_id": "<msg1@example.com>"},
    ]

    response = client.get("/api/messages?message_id=%3Cmsg1%40example.com%3E")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1


@pytest.mark.integration
def test_get_message_by_id_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/messages/{message_doc_id} endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "_id": "msg1",
            "message_id": "<msg1@example.com>",
            "subject": "Test Message",
            "body_normalized": "Test content",
        },
    ]

    response = client.get("/api/messages/msg1")

    assert response.status_code == 200
    data = response.json()

    assert data["_id"] == "msg1"
    assert data["subject"] == "Test Message"


@pytest.mark.integration
def test_get_message_by_id_not_found(client, test_service, mock_document_store):
    """Test the GET /api/messages/{message_doc_id} endpoint when message not found."""
    mock_document_store.query_documents.return_value = []

    response = client.get("/api/messages/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.integration
def test_get_chunks_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/chunks endpoint."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "Chunk 1", "chunk_index": 0},
        {"_id": "chunk2", "text": "Chunk 2", "chunk_index": 1},
    ]

    response = client.get("/api/chunks")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 2
    assert len(data["chunks"]) == 2
    assert data["chunks"][0]["_id"] == "chunk1"


@pytest.mark.integration
def test_get_chunks_with_message_id_filter(client, test_service, mock_document_store):
    """Test the GET /api/chunks endpoint with message_id filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "message_id": "<msg1@example.com>"},
    ]

    response = client.get("/api/chunks?message_id=%3Cmsg1%40example.com%3E")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1


@pytest.mark.integration
def test_get_chunks_with_thread_filter(client, test_service, mock_document_store):
    """Test the GET /api/chunks endpoint with thread_id filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "thread_id": "thread1"},
    ]

    response = client.get("/api/chunks?thread_id=thread1")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1


@pytest.mark.integration
def test_get_chunks_with_message_doc_id_filter(client, test_service, mock_document_store):
    """Test the GET /api/chunks endpoint with message_doc_id filter."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "message_doc_id": "msg_doc_1"},
    ]

    response = client.get("/api/chunks?message_doc_id=msg_doc_1")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1


@pytest.mark.integration
def test_get_chunk_by_id_endpoint(client, test_service, mock_document_store):
    """Test the GET /api/chunks/{chunk_id} endpoint."""
    mock_document_store.query_documents.return_value = [
        {
            "_id": "chunk1",
            "text": "Test chunk content",
            "chunk_index": 0,
        },
    ]

    response = client.get("/api/chunks/chunk1")

    assert response.status_code == 200
    data = response.json()

    assert data["_id"] == "chunk1"
    assert data["text"] == "Test chunk content"


@pytest.mark.integration
def test_get_chunk_by_id_not_found(client, test_service, mock_document_store):
    """Test the GET /api/chunks/{chunk_id} endpoint when chunk not found."""
    mock_document_store.query_documents.return_value = []

    response = client.get("/api/chunks/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.integration
def test_new_endpoints_service_not_initialized(monkeypatch):
    """Test new endpoints when service is not initialized."""
    import main

    monkeypatch.setattr(main, "reporting_service", None)

    client = TestClient(app)

    # Test threads endpoints
    response = client.get("/api/threads")
    assert response.status_code == 503

    response = client.get("/api/threads/thread1")
    assert response.status_code == 503

    # Test messages endpoints
    response = client.get("/api/messages")
    assert response.status_code == 503

    response = client.get("/api/messages/msg1")
    assert response.status_code == 503

    # Test chunks endpoints
    response = client.get("/api/chunks")
    assert response.status_code == 503

    response = client.get("/api/chunks/chunk1")
    assert response.status_code == 503
