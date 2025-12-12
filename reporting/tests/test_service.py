# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the reporting service."""

import pytest
from unittest.mock import Mock, patch

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
def mock_metrics():
    """Create a mock metrics collector."""
    metrics = Mock()
    metrics.increment = Mock()
    metrics.observe = Mock()
    return metrics


@pytest.fixture
def mock_error_reporter():
    """Create a mock error reporter."""
    reporter = Mock()
    reporter.report = Mock()
    return reporter


@pytest.fixture
def reporting_service(mock_document_store, mock_publisher, mock_subscriber):
    """Create a reporting service instance."""
    return ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
    )


@pytest.fixture
def reporting_service_with_metrics(
    mock_document_store, mock_publisher, mock_subscriber, mock_metrics, mock_error_reporter
):
    """Create a reporting service instance with metrics and error reporting."""
    return ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        metrics_collector=mock_metrics,
        error_reporter=mock_error_reporter,
    )


@pytest.fixture
def sample_summary_complete_event():
    """Create a sample SummaryComplete event."""
    return {
        "event_id": "evt_123",
        "event_type": "SummaryComplete",
        "timestamp": "2025-01-15T12:00:00Z",
        "version": "1.0",
        "data": {
            "thread_id": "<thread_123@example.com>",
            "summary_markdown": "# Summary\n\nThis is a test summary.",
            "citations": [
                {
                    "message_id": "<msg_1@example.com>",
                    "chunk_id": "chunk_1",
                    "offset": 0,
                },
                {
                    "message_id": "<msg_2@example.com>",
                    "chunk_id": "chunk_2",
                    "offset": 100,
                },
            ],
            "llm_backend": "ollama",
            "llm_model": "mistral",
            "tokens_prompt": 1000,
            "tokens_completion": 500,
            "latency_ms": 2000,
        },
    }


def test_service_initialization(reporting_service):
    """Test that the service initializes correctly."""
    assert reporting_service.document_store is not None
    assert reporting_service.publisher is not None
    assert reporting_service.subscriber is not None
    assert reporting_service.reports_stored == 0
    assert reporting_service.notifications_sent == 0
    assert reporting_service.notifications_failed == 0
    assert reporting_service.notify_enabled is False


def test_service_start_subscribes_to_events(reporting_service, mock_subscriber):
    """Test that service subscribes to summary.complete events on start."""
    reporting_service.start()
    
    mock_subscriber.subscribe.assert_called_once()
    call_args = mock_subscriber.subscribe.call_args
    
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "summary.complete"
    assert call_args[1]["callback"] is not None


def test_process_summary_stores_document(
    reporting_service, mock_document_store, sample_summary_complete_event
):
    """Test that process_summary stores the summary document."""
    report_id = reporting_service.process_summary(
        sample_summary_complete_event["data"],
        sample_summary_complete_event
    )
    
    assert report_id is not None
    assert reporting_service.reports_stored == 1
    
    # Verify document was inserted
    mock_document_store.insert_document.assert_called_once()
    call_args = mock_document_store.insert_document.call_args
    
    assert call_args[0][0] == "summaries"  # Collection name
    doc = call_args[0][1]
    
    assert doc["summary_id"] == report_id
    assert doc["thread_id"] == "<thread_123@example.com>"
    assert doc["summary_type"] == "thread"
    assert doc["content_markdown"] == "# Summary\n\nThis is a test summary."
    assert doc["generated_by"] == "ollama"
    assert len(doc["citations"]) == 2
    assert doc["metadata"]["llm_model"] == "mistral"
    assert doc["metadata"]["tokens_prompt"] == 1000


def test_process_summary_publishes_report_published_event(
    reporting_service, mock_publisher, sample_summary_complete_event
):
    """Test that process_summary publishes ReportPublished event."""
    report_id = reporting_service.process_summary(
        sample_summary_complete_event["data"],
        sample_summary_complete_event
    )
    
    # Should publish one event (ReportPublished)
    assert mock_publisher.publish.call_count == 1
    
    # Verify the event
    call_args = mock_publisher.publish.call_args
    assert call_args[1]["exchange"] == "copilot.events"
    assert call_args[1]["routing_key"] == "report.published"
    
    message = call_args[1]["message"]
    assert message["event_type"] == "ReportPublished"
    assert message["data"]["report_id"] == report_id
    assert message["data"]["thread_id"] == "<thread_123@example.com>"
    assert message["data"]["format"] == "markdown"
    assert message["data"]["notified"] is False
    assert message["data"]["delivery_channels"] == []


def test_process_summary_with_webhook_enabled(
    mock_document_store, mock_publisher, mock_subscriber, sample_summary_complete_event
):
    """Test that process_summary sends webhook when enabled."""
    service = ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        webhook_url="http://example.com/webhook",
        notify_enabled=True,
    )
    
    with patch("app.service.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        
        report_id = service.process_summary(
            sample_summary_complete_event["data"],
            sample_summary_complete_event
        )
        
        # Verify webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        assert call_args[0][0] == "http://example.com/webhook"
        assert "report_id" in call_args[1]["json"]
        assert call_args[1]["json"]["report_id"] == report_id
        
        # Verify stats updated
        assert service.notifications_sent == 1
        assert service.notifications_failed == 0
        
        # Verify ReportPublished event shows notified=True
        publish_call = mock_publisher.publish.call_args
        message = publish_call[1]["message"]
        assert message["data"]["notified"] is True
        assert "webhook" in message["data"]["delivery_channels"]


def test_process_summary_webhook_failure_publishes_delivery_failed(
    mock_document_store, mock_publisher, mock_subscriber, sample_summary_complete_event
):
    """Test that webhook failure publishes ReportDeliveryFailed event."""
    service = ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        webhook_url="http://example.com/webhook",
        notify_enabled=True,
    )
    
    with patch("app.service.requests.post") as mock_post:
        mock_post.side_effect = Exception("Connection timeout")
        
        report_id = service.process_summary(
            sample_summary_complete_event["data"],
            sample_summary_complete_event
        )
        
        # Verify stats updated
        assert service.notifications_sent == 0
        assert service.notifications_failed == 1
        
        # Should publish two events: ReportPublished and ReportDeliveryFailed
        assert mock_publisher.publish.call_count == 2
        
        # Check ReportDeliveryFailed event
        delivery_failed_call = None
        for call_obj in mock_publisher.publish.call_args_list:
            if call_obj[1]["routing_key"] == "report.delivery.failed":
                delivery_failed_call = call_obj
                break
        
        assert delivery_failed_call is not None
        message = delivery_failed_call[1]["message"]
        assert message["event_type"] == "ReportDeliveryFailed"
        assert message["data"]["report_id"] == report_id
        assert message["data"]["delivery_channel"] == "webhook"
        assert "Connection timeout" in message["data"]["error_message"]


def test_get_reports_queries_document_store(reporting_service, mock_document_store):
    """Test that get_reports queries the document store."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1"},
        {"summary_id": "rpt2", "thread_id": "thread2"},
    ]
    
    reports = reporting_service.get_reports()
    
    assert len(reports) == 2
    mock_document_store.query_documents.assert_called_once_with(
        "summaries",
        filter_dict={},
        limit=10,
    )


def test_get_reports_with_thread_filter(reporting_service, mock_document_store):
    """Test that get_reports filters by thread_id."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1"},
    ]
    
    reports = reporting_service.get_reports(thread_id="thread1")
    
    assert len(reports) == 1
    mock_document_store.query_documents.assert_called_once_with(
        "summaries",
        filter_dict={"thread_id": "thread1"},
        limit=10,
    )


def test_get_report_by_id(reporting_service, mock_document_store):
    """Test that get_report_by_id retrieves a specific report."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1"},
    ]
    
    report = reporting_service.get_report_by_id("rpt1")
    
    assert report is not None
    assert report["summary_id"] == "rpt1"
    mock_document_store.query_documents.assert_called_once_with(
        "summaries",
        filter_dict={"summary_id": "rpt1"},
        limit=1,
    )


def test_get_report_by_id_not_found(reporting_service, mock_document_store):
    """Test that get_report_by_id returns None when not found."""
    mock_document_store.query_documents.return_value = []
    
    report = reporting_service.get_report_by_id("nonexistent")
    
    assert report is None


def test_get_thread_summary(reporting_service, mock_document_store):
    """Test that get_thread_summary retrieves latest summary for thread."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1"},
    ]
    
    summary = reporting_service.get_thread_summary("thread1")
    
    assert summary is not None
    assert summary["thread_id"] == "thread1"
    mock_document_store.query_documents.assert_called_once_with(
        "summaries",
        filter_dict={"thread_id": "thread1"},
        limit=1,
    )


def test_get_stats(reporting_service):
    """Test that get_stats returns service statistics."""
    reporting_service.reports_stored = 5
    reporting_service.notifications_sent = 3
    reporting_service.notifications_failed = 1
    reporting_service.last_processing_time = 1.5
    
    stats = reporting_service.get_stats()
    
    assert stats["reports_stored"] == 5
    assert stats["notifications_sent"] == 3
    assert stats["notifications_failed"] == 1
    assert stats["last_processing_time_seconds"] == 1.5


def test_handle_summary_complete_with_metrics(
    reporting_service_with_metrics, mock_metrics, sample_summary_complete_event
):
    """Test that _handle_summary_complete records metrics."""
    reporting_service_with_metrics._handle_summary_complete(sample_summary_complete_event)
    
    # Should increment success metric
    mock_metrics.increment.assert_any_call(
        "reporting_events_total",
        tags={"event_type": "summary_complete", "outcome": "success"}
    )
    
    # Should observe latency
    assert mock_metrics.observe.call_count >= 1
    latency_call = mock_metrics.observe.call_args_list[0]
    assert latency_call[0][0] == "reporting_latency_seconds"


def test_handle_summary_complete_error_handling(
    reporting_service_with_metrics,
    mock_metrics,
    mock_error_reporter,
    mock_document_store,
    sample_summary_complete_event
):
    """Test that _handle_summary_complete handles errors properly."""
    # Make insert_document raise an exception
    mock_document_store.insert_document.side_effect = Exception("DB Error")
    
    reporting_service_with_metrics._handle_summary_complete(sample_summary_complete_event)
    
    # Should increment error metric
    mock_metrics.increment.assert_any_call(
        "reporting_events_total",
        tags={"event_type": "summary_complete", "outcome": "error"}
    )
    
    # Should increment failure metric
    mock_metrics.increment.assert_any_call(
        "reporting_failures_total",
        tags={"error_type": "Exception"}
    )
    
    # Should report error
    mock_error_reporter.report.assert_called_once()
