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


def test_publish_report_published_with_publisher_failure(mock_document_store, mock_subscriber):
    class FailingPublisher(Mock):
        def publish(self, exchange, routing_key, event):
            return False

    publisher = FailingPublisher()
    service = ReportingService(
        document_store=mock_document_store,
        publisher=publisher,
        subscriber=mock_subscriber,
    )

    with pytest.raises(Exception) as exc_info:
        service._publish_report_published(
            report_id="rep-1",
            thread_id="thread-1",
            notified=False,
            delivery_channels=[],
        )

    assert "Failed to publish ReportPublished event" in str(exc_info.value)


def test_publish_delivery_failed_with_publisher_failure(mock_document_store, mock_subscriber):
    class FailingPublisher(Mock):
        def publish(self, exchange, routing_key, event):
            return False

    publisher = FailingPublisher()
    service = ReportingService(
        document_store=mock_document_store,
        publisher=publisher,
        subscriber=mock_subscriber,
    )

    with pytest.raises(Exception) as exc_info:
        service._publish_delivery_failed(
            report_id="rep-1",
            thread_id="thread-1",
            channel="webhook",
            error_message="boom",
            error_type="ValueError",
        )

    assert "Failed to publish ReportDeliveryFailed event" in str(exc_info.value)


def test_process_summary_raises_when_publish_delivery_failed_fails(
    mock_document_store,
    mock_subscriber,
    mock_metrics,
    mock_error_reporter,
):
    class SelectiveFailPublisher(Mock):
        def publish(self, exchange, routing_key, event):
            if routing_key == "report.delivery.failed":
                return False
            return True

    publisher = SelectiveFailPublisher()
    service = ReportingService(
        document_store=mock_document_store,
        publisher=publisher,
        subscriber=mock_subscriber,
        metrics_collector=mock_metrics,
        error_reporter=mock_error_reporter,
        webhook_url="http://example.com",
        notify_enabled=True,
    )

    event_data = {
        "thread_id": "thread-1",
        "summary_markdown": "# Summary",
        "citations": [],
        "llm_backend": "test",
        "llm_model": "test-model",
        "tokens_prompt": 10,
        "tokens_completion": 5,
        "latency_ms": 1,
    }

    with patch.object(service, "_send_webhook_notification", side_effect=Exception("webhook fail")):
        with pytest.raises(Exception) as exc_info:
            service.process_summary(event_data, {"timestamp": "2025-01-01T00:00:00Z"})

    assert "webhook fail" in str(exc_info.value)


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
    
    event = call_args[1]["event"]
    assert event["event_type"] == "ReportPublished"
    assert event["data"]["report_id"] == report_id
    assert event["data"]["thread_id"] == "<thread_123@example.com>"
    assert event["data"]["format"] == "markdown"
    assert event["data"]["notified"] is False
    assert event["data"]["delivery_channels"] == []


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
        event = publish_call[1]["event"]
        assert event["data"]["notified"] is True
        assert "webhook" in event["data"]["delivery_channels"]


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
        event = delivery_failed_call[1]["event"]
        assert event["event_type"] == "ReportDeliveryFailed"
        assert event["data"]["report_id"] == report_id
        assert event["data"]["delivery_channel"] == "webhook"
        assert "Connection timeout" in event["data"]["error_message"]


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
    
    # Should raise the exception for message requeue
    with pytest.raises(Exception, match="DB Error"):
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


def test_publisher_uses_event_parameter_for_published(reporting_service, mock_publisher, sample_summary_complete_event):
    """Test that publisher.publish is called with event parameter, not message."""
    # Process a summary to trigger ReportPublished event
    reporting_service.process_summary(
        sample_summary_complete_event["data"],
        sample_summary_complete_event
    )
    
    # Verify publish was called with event parameter
    assert mock_publisher.publish.call_count == 1
    call_args = mock_publisher.publish.call_args
    
    # Check that event is in kwargs
    assert "event" in call_args[1], "publisher.publish must use 'event' parameter"
    assert "message" not in call_args[1], "publisher.publish should not use deprecated 'message' parameter"


def test_publisher_uses_event_parameter_for_delivery_failed(reporting_service, mock_publisher):
    """Test that _publish_delivery_failed uses event parameter, not message."""
    # Trigger a delivery failed event
    reporting_service._publish_delivery_failed(
        report_id="report-123",
        thread_id="<thread@example.com>",
        channel="webhook",
        error_message="Connection timeout",
        error_type="TimeoutError"
    )
    
    # Verify publish was called with event parameter
    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    
    # Check that event is in kwargs
    assert "event" in call_args[1], "publisher.publish must use 'event' parameter"
    assert "message" not in call_args[1], "publisher.publish should not use deprecated 'message' parameter"


def test_query_documents_uses_filter_dict_parameter(reporting_service, mock_document_store):
    """Test that query_documents is called with filter_dict parameter, not query."""
    # Setup mock
    mock_document_store.query_documents.return_value = []
    
    # Call get_reports which uses query_documents
    reporting_service.get_reports(thread_id="<thread@example.com>")
    
    # Verify query_documents was called with filter_dict parameter
    mock_document_store.query_documents.assert_called_once()
    call_args = mock_document_store.query_documents.call_args
    
    # Check that filter_dict is in kwargs
    assert "filter_dict" in call_args[1], "query_documents must use 'filter_dict' parameter"
    assert "query" not in call_args[1], "query_documents should not use deprecated 'query' parameter"
