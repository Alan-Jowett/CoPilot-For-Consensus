# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for the reporting service."""

from unittest.mock import Mock, patch

import pytest
from app.service import ReportingService
from copilot_event_retry import RetryConfig


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
            "summary_id": "a1b2c3d4e5f6",
            "thread_id": "<thread_123@example.com>",
            "summary_markdown": "# Summary\n\nThis is a test summary.",
            "citations": [
                {
                    "message_id": "<msg_1@example.com>",
                    "chunk_id": "chunk_1",
                    "offset": 0,
                    "text": "This is the text from the first citation.",
                },
                {
                    "message_id": "<msg_2@example.com>",
                    "chunk_id": "chunk_2",
                    "offset": 100,
                    "text": "This is the text from the second citation.",
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
            raise Exception("Publish failed")

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

    assert "Publish failed" in str(exc_info.value)


def test_publish_delivery_failed_with_publisher_failure(mock_document_store, mock_subscriber):
    class FailingPublisher(Mock):
        def publish(self, exchange, routing_key, event):
            raise Exception("Publish failed")

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

    assert "Publish failed" in str(exc_info.value)


def test_process_summary_raises_when_publish_delivery_failed_fails(
    mock_document_store,
    mock_subscriber,
    mock_metrics,
    mock_error_reporter,
):
    class SelectiveFailPublisher(Mock):
        def publish(self, exchange, routing_key, event):
            if routing_key == "report.delivery.failed":
                raise Exception("Publish failed")
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
        with pytest.raises(Exception):
            service.process_summary(event_data, {"timestamp": "2025-01-01T00:00:00Z"})


def test_service_start_subscribes_to_events(reporting_service, mock_subscriber):
    """Test that service subscribes to summary.complete events on start."""
    reporting_service.start()

    from unittest.mock import call

    assert mock_subscriber.subscribe.call_count == 2
    mock_subscriber.subscribe.assert_has_calls(
        [
            call(
                event_type="SummaryComplete",
                exchange="copilot.events",
                routing_key="summary.complete",
                callback=reporting_service._handle_summary_complete,
            ),
            call(
                event_type="SourceDeletionRequested",
                exchange="copilot.events",
                routing_key="source.deletion.requested",
                callback=reporting_service._handle_source_deletion_requested,
            ),
        ],
        any_order=False,
    )


def test_process_summary_stores_document(reporting_service, mock_document_store, sample_summary_complete_event):
    """Test that process_summary stores the summary document."""
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    mock_document_store.query_documents.side_effect = query_documents_side_effect

    report_id = reporting_service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

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
    assert doc["citations"][0]["quote"] == "This is the text from the first citation."
    assert doc["citations"][1]["quote"] == "This is the text from the second citation."
    assert doc["metadata"]["llm_model"] == "mistral"
    assert doc["metadata"]["tokens_prompt"] == 1000


def test_process_summary_raises_if_thread_update_fails(
    reporting_service, mock_document_store, mock_publisher, sample_summary_complete_event
):
    """If the summary is stored but threads.summary_id cannot be updated, the event must requeue."""
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    mock_document_store.query_documents.side_effect = query_documents_side_effect
    mock_document_store.update_document.side_effect = Exception("db write failed")

    with pytest.raises(Exception, match="db write failed"):
        reporting_service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

    # Summary insert may have already happened; but we must not publish ReportPublished on failure.
    assert mock_publisher.publish.call_count == 0


def test_process_summary_publishes_report_published_event(
    reporting_service, mock_publisher, sample_summary_complete_event
):
    """Test that process_summary publishes ReportPublished event."""
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    reporting_service.document_store.query_documents.side_effect = query_documents_side_effect

    report_id = reporting_service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

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
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    mock_document_store.query_documents.side_effect = query_documents_side_effect

    service = ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        webhook_url="http://example.com/webhook",
        notify_enabled=True,
    )

    with patch("app.service.requests.post") as mock_post:
        mock_post.return_value.status_code = 200

        report_id = service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

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
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    mock_document_store.query_documents.side_effect = query_documents_side_effect

    service = ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        webhook_url="http://example.com/webhook",
        notify_enabled=True,
    )

    with patch("app.service.requests.post") as mock_post:
        mock_post.side_effect = Exception("Connection timeout")

        report_id = service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

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
    # First call should fetch summaries with limit + skip + METADATA_FILTER_BUFFER_SIZE (100)
    first_call = mock_document_store.query_documents.call_args_list[0]
    assert first_call[0][0] == "summaries"
    assert first_call[1]["filter_dict"] == {}
    assert first_call[1]["limit"] == 110

    # Subsequent enrichment calls for threads/archives are expected


def test_get_reports_with_thread_filter(reporting_service, mock_document_store):
    """Test that get_reports filters by thread_id."""
    mock_document_store.query_documents.return_value = [
        {"summary_id": "rpt1", "thread_id": "thread1"},
    ]

    reports = reporting_service.get_reports(thread_id="thread1")

    assert len(reports) == 1
    # First call should fetch summaries with limit + skip + METADATA_FILTER_BUFFER_SIZE (100)
    first_call = mock_document_store.query_documents.call_args_list[0]
    assert first_call[0][0] == "summaries"
    assert first_call[1]["filter_dict"] == {"thread_id": "thread1"}
    assert first_call[1]["limit"] == 110

    # Subsequent enrichment calls for threads/archives are expected


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
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    reporting_service_with_metrics.document_store.query_documents.side_effect = query_documents_side_effect
    reporting_service_with_metrics.retry_config = RetryConfig(
        max_attempts=1,
        base_delay_ms=0,
        max_delay_ms=0,
        ttl_seconds=0,
        use_jitter=False,
    )

    reporting_service_with_metrics._handle_summary_complete(sample_summary_complete_event)

    # Should increment success metric
    mock_metrics.increment.assert_any_call(
        "reporting_events_total", tags={"event_type": "summary_complete", "outcome": "success"}
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
    sample_summary_complete_event,
):
    """Test that _handle_summary_complete handles errors properly."""
    # Thread lookup must return a doc so the code proceeds to insert_document
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_side_effect(collection, filter_dict, limit=100, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [{"_id": thread_id, "first_message_date": "2025-01-01T00:00:00Z", "last_message_date": "2025-01-02T00:00:00Z"}]
        if collection == "summaries":
            return []
        return []

    mock_document_store.query_documents.side_effect = query_side_effect
    # Make insert_document raise an exception
    mock_document_store.insert_document.side_effect = Exception("DB Error")

    # Should raise the exception for message requeue
    with pytest.raises(Exception, match="DB Error"):
        reporting_service_with_metrics._handle_summary_complete(sample_summary_complete_event)

    # Should increment error metric
    mock_metrics.increment.assert_any_call(
        "reporting_events_total", tags={"event_type": "summary_complete", "outcome": "error"}
    )

    # Should increment failure metric
    mock_metrics.increment.assert_any_call("reporting_failures_total", tags={"error_type": "Exception"})

    # Should report error
    mock_error_reporter.report.assert_called_once()


def test_publisher_uses_event_parameter_for_published(reporting_service, mock_publisher, sample_summary_complete_event):
    """Test that publisher.publish is called with event parameter, not message."""
    # Process a summary to trigger ReportPublished event
    thread_id = sample_summary_complete_event["data"]["thread_id"]

    def query_documents_side_effect(collection: str, **kwargs):
        if collection == "summaries":
            return []
        if collection == "threads":
            return [{"_id": thread_id}]
        return []

    reporting_service.document_store.query_documents.side_effect = query_documents_side_effect

    reporting_service.process_summary(sample_summary_complete_event["data"], sample_summary_complete_event)

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
        error_type="TimeoutError",
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


def test_get_reports_passes_sort_by_to_query_documents(reporting_service, mock_document_store):
    """Test that sort_by=thread_start_date maps to first_message_date at DB level."""
    mock_document_store.query_documents.return_value = []

    # sort_by=thread_start_date should map to sort_by=first_message_date
    reporting_service.get_reports(sort_by="thread_start_date", sort_order="desc")
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["sort_by"] == "first_message_date"
    assert call_args[1]["sort_order"] == "desc"

    mock_document_store.query_documents.reset_mock()
    mock_document_store.query_documents.return_value = []

    # sort_by=generated_at should pass through as-is
    reporting_service.get_reports(sort_by="generated_at", sort_order="asc")
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["sort_by"] == "generated_at"
    assert call_args[1]["sort_order"] == "asc"

    mock_document_store.query_documents.reset_mock()
    mock_document_store.query_documents.return_value = []

    # No sort_by should pass None
    reporting_service.get_reports()
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["sort_by"] is None


def test_get_reports_with_message_date_filters_inclusive_overlap(reporting_service, mock_document_store):
    """Test that get_reports supports message date filtering with inclusive overlap."""

    # Setup mocks - need to return thread data
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1"},
                {"summary_id": "rpt2", "thread_id": "thread2"},
                {"summary_id": "rpt3", "thread_id": "thread3"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "last_message_date": "2025-01-10T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread2",
                    "first_message_date": "2025-01-15T00:00:00Z",
                    "last_message_date": "2025-01-20T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread3",
                    "first_message_date": "2025-01-25T00:00:00Z",
                    "last_message_date": "2025-01-30T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages between 2025-01-08 and 2025-01-17
    # Should include:
    # - thread1 (2025-01-05 to 2025-01-10) - overlaps at end
    # - thread2 (2025-01-15 to 2025-01-20) - overlaps at start
    # Should exclude:
    # - thread3 (2025-01-25 to 2025-01-30) - no overlap
    reports = reporting_service.get_reports(
        message_start_date="2025-01-08T00:00:00Z",
        message_end_date="2025-01-17T00:00:00Z",
    )

    # Should return 2 reports (thread1 and thread2)
    assert len(reports) == 2
    thread_ids = {r["thread_id"] for r in reports}
    assert "thread1" in thread_ids
    assert "thread2" in thread_ids
    assert "thread3" not in thread_ids


def test_get_reports_with_message_date_filters_no_overlap(reporting_service, mock_document_store):
    """Test that get_reports correctly excludes threads with no date overlap."""

    # Setup mocks
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1"},
                {"summary_id": "rpt2", "thread_id": "thread2"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-01T00:00:00Z",
                    "last_message_date": "2025-01-05T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread2",
                    "first_message_date": "2025-01-20T00:00:00Z",
                    "last_message_date": "2025-01-25T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages between 2025-01-10 and 2025-01-15
    # Should exclude both threads (no overlap)
    reports = reporting_service.get_reports(
        message_start_date="2025-01-10T00:00:00Z",
        message_end_date="2025-01-15T00:00:00Z",
    )

    # Should return 0 reports
    assert len(reports) == 0


def test_get_reports_with_message_date_filters_thread_without_dates(reporting_service, mock_document_store):
    """Test that get_reports skips threads without date information when using message date filters."""

    # Setup mocks
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1"},
                {"summary_id": "rpt2", "thread_id": "thread2"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread2",
                    # Missing date information
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages between 2025-01-08 and 2025-01-17
    reports = reporting_service.get_reports(
        message_start_date="2025-01-08T00:00:00Z",
        message_end_date="2025-01-17T00:00:00Z",
    )

    # Should only return thread1 (thread2 has no dates)
    assert len(reports) == 1
    assert reports[0]["thread_id"] == "thread1"


def test_get_reports_with_message_date_filters_start_only(reporting_service, mock_document_store):
    """Test that get_reports supports message_start_date without message_end_date."""

    # Setup mocks
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1"},
                {"summary_id": "rpt2", "thread_id": "thread2"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "last_message_date": "2025-01-10T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread2",
                    "first_message_date": "2025-01-15T00:00:00Z",
                    "last_message_date": "2025-01-20T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages starting from 2025-01-12 (no end date)
    # Should include thread2 only (thread1 ends before start date)
    reports = reporting_service.get_reports(
        message_start_date="2025-01-12T00:00:00Z",
    )

    # Should return 1 report (thread2)
    assert len(reports) == 1
    assert reports[0]["thread_id"] == "thread2"


def test_get_reports_with_message_date_filters_end_only(reporting_service, mock_document_store):
    """Test that get_reports supports message_end_date without message_start_date."""

    # Setup mocks
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1"},
                {"summary_id": "rpt2", "thread_id": "thread2"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "last_message_date": "2025-01-10T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "thread_id": "thread2",
                    "first_message_date": "2025-01-15T00:00:00Z",
                    "last_message_date": "2025-01-20T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages ending before 2025-01-12 (no start date)
    # Should include thread1 only (thread2 starts after end date)
    reports = reporting_service.get_reports(
        message_end_date="2025-01-12T00:00:00Z",
    )

    # Should return 1 report (thread1)
    assert len(reports) == 1
    assert reports[0]["thread_id"] == "thread1"


def test_get_reports_with_metadata_filters(reporting_service, mock_document_store):
    """Test that get_reports supports metadata filtering."""

    # Setup mocks - need to return thread and archive data
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries":
            return [
                {"summary_id": "rpt1", "thread_id": "thread1", "generated_at": "2025-01-15T12:00:00Z"},
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "archive_id": "archive1",
                    "subject": "Test thread",
                    "participants": [{"email": "user1@example.com"}, {"email": "user2@example.com"}],
                    "message_count": 10,
                }
            ]
        elif collection == "archives":
            return [
                {
                    "_id": "archive1",
                    "source": "test-source",
                    "source_url": "http://example.com",
                    "ingestion_date": "2025-01-01T00:00:00Z",
                }
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    reports = reporting_service.get_reports(
        min_participants=2,
        max_messages=15,
        source="test-source",
    )

    # Should return enriched report with metadata
    assert len(reports) == 1
    assert "thread_metadata" in reports[0]
    assert reports[0]["thread_metadata"]["participant_count"] == 2
    assert reports[0]["thread_metadata"]["message_count"] == 10
    assert "archive_metadata" in reports[0]
    assert reports[0]["archive_metadata"]["source"] == "test-source"


def test_get_available_sources(reporting_service, mock_document_store):
    """Test that get_available_sources returns unique source list."""
    mock_document_store.query_documents.return_value = [
        {"_id": "arch1", "source": "source-a"},
        {"_id": "arch2", "source": "source-b"},
        {"_id": "arch3", "source": "source-a"},  # Duplicate
    ]

    sources = reporting_service.get_available_sources()

    assert len(sources) == 2
    assert "source-a" in sources
    assert "source-b" in sources
    assert sources == sorted(sources)  # Should be sorted


def test_search_reports_by_topic_requires_vector_store(reporting_service):
    """Test that search_reports_by_topic raises error when vector store not configured."""
    # Service was created without vector_store and embedding_provider
    with pytest.raises(ValueError, match="Topic search requires vector store and embedding provider"):
        reporting_service.search_reports_by_topic("test topic")


def test_search_reports_by_topic_with_vector_store():
    """Test topic-based search with vector store and embedding provider."""
    # Create mocks
    mock_doc_store = Mock()
    mock_pub = Mock()
    mock_sub = Mock()
    mock_vector_store = Mock()
    mock_embedding_provider = Mock()

    # Setup embedding provider
    mock_embedding_provider.embed.return_value = [0.1] * 384

    # Setup vector store to return search results
    mock_search_result = Mock()
    mock_search_result.id = "chunk1"
    mock_search_result.score = 0.85
    mock_search_result.metadata = {"thread_id": "thread1"}
    mock_vector_store.query.return_value = [mock_search_result]

    # Setup document store to return thread summary
    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "summaries" and filter_dict.get("thread_id") == "thread1":
            return [
                {
                    "summary_id": "rpt1",
                    "thread_id": "thread1",
                    "content_markdown": "Test summary",
                    "generated_at": "2025-01-15T12:00:00Z",
                }
            ]
        elif collection == "threads":
            return [
                {
                    "thread_id": "thread1",
                    "subject": "Test",
                    "participants": [{"email": "user@example.com"}],
                    "message_count": 5,
                    "archive_id": "archive1",
                }
            ]
        elif collection == "archives":
            return [
                {
                    "_id": "archive1",
                    "source": "test-source",
                    "source_url": "http://example.com",
                    "ingestion_date": "2025-01-01T00:00:00Z",
                }
            ]
        return []

    mock_doc_store.query_documents.side_effect = mock_query

    # Create service with vector store
    service = ReportingService(
        document_store=mock_doc_store,
        publisher=mock_pub,
        subscriber=mock_sub,
        vector_store=mock_vector_store,
        embedding_provider=mock_embedding_provider,
    )

    # Search by topic
    reports = service.search_reports_by_topic("test topic", limit=10, min_score=0.5)

    # Verify embedding was generated
    mock_embedding_provider.embed.assert_called_once_with("test topic")

    # Verify vector store was queried
    mock_vector_store.query.assert_called_once()

    # Verify results are enriched with relevance score
    assert len(reports) == 1
    assert reports[0]["relevance_score"] == 0.85
    assert reports[0]["matching_chunks"] == 1
    assert "thread_metadata" in reports[0]
    assert "archive_metadata" in reports[0]


def test_get_threads(reporting_service, mock_document_store):
    """Test that get_threads retrieves threads with pagination."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "subject": "Thread 1", "participants": [], "message_count": 1},
                {"_id": "thread2", "subject": "Thread 2", "participants": [], "message_count": 1},
                {"_id": "thread3", "subject": "Thread 3", "participants": [], "message_count": 1},
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads(limit=2, skip=0)

    assert len(threads) == 2
    assert threads[0]["_id"] == "thread1"
    assert threads[1]["_id"] == "thread2"

    # Verify query_documents is called with correct parameters including sort
    call_args = mock_document_store.query_documents.call_args
    assert call_args[0][0] == "threads"
    assert call_args[1]["filter_dict"] == {}
    assert call_args[1]["limit"] == 2  # limit + skip = 2 + 0
    assert call_args[1]["sort_by"] is None
    assert call_args[1]["sort_order"] == "desc"


def test_get_threads_with_archive_filter(reporting_service, mock_document_store):
    """Test that get_threads supports archive_id filtering."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "archive_id": "archive1", "participants": [], "message_count": 1},
            ]
        elif collection == "archives":
            return []
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads(archive_id="archive1")

    assert len(threads) == 1
    # Verify the archive_id was passed in the filter to the threads query (first call)
    first_call = mock_document_store.query_documents.call_args_list[0]
    assert first_call[0][0] == "threads"
    assert first_call[1]["filter_dict"]["archive_id"] == "archive1"


def test_get_threads_with_skip(reporting_service, mock_document_store):
    """Test that get_threads pagination with non-zero skip returns correct subset."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread0", "subject": "Thread 0", "participants": [], "message_count": 1},
                {"_id": "thread1", "subject": "Thread 1", "participants": [], "message_count": 1},
                {"_id": "thread2", "subject": "Thread 2", "participants": [], "message_count": 1},
                {"_id": "thread3", "subject": "Thread 3", "participants": [], "message_count": 1},
                {"_id": "thread4", "subject": "Thread 4", "participants": [], "message_count": 1},
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads(limit=2, skip=2)

    # Should return threads[2:4] which are thread2 and thread3
    assert len(threads) == 2
    assert threads[0]["_id"] == "thread2"
    assert threads[1]["_id"] == "thread3"

    # Verify query_documents is called with limit + skip + buffer (if filtering)
    # Since no filters are applied, no buffer is added
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["limit"] == 4  # limit + skip = 2 + 2


def test_get_threads_skip_exceeds_results(reporting_service, mock_document_store):
    """Test that get_threads returns empty list when skip exceeds available results."""
    mock_document_store.query_documents.return_value = [
        {"_id": "thread1", "subject": "Thread 1"},
        {"_id": "thread2", "subject": "Thread 2"},
        {"_id": "thread3", "subject": "Thread 3"},
    ]

    threads = reporting_service.get_threads(limit=10, skip=5)

    # Should return empty list since skip=5 exceeds 3 results
    assert len(threads) == 0
    assert threads == []


def test_get_thread_by_id(reporting_service, mock_document_store):
    """Test that get_thread_by_id retrieves a specific thread."""
    mock_document_store.query_documents.return_value = [
        {"_id": "thread1", "subject": "Test Thread"},
    ]

    thread = reporting_service.get_thread_by_id("thread1")

    assert thread is not None
    assert thread["_id"] == "thread1"
    mock_document_store.query_documents.assert_called_once_with(
        "threads",
        filter_dict={"_id": "thread1"},
        limit=1,
    )


def test_get_thread_by_id_not_found(reporting_service, mock_document_store):
    """Test that get_thread_by_id returns None when not found."""
    mock_document_store.query_documents.return_value = []

    thread = reporting_service.get_thread_by_id("nonexistent")

    assert thread is None


def test_get_messages(reporting_service, mock_document_store):
    """Test that get_messages retrieves messages with pagination."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "message_id": "<msg1@example.com>"},
        {"_id": "msg2", "message_id": "<msg2@example.com>"},
    ]

    messages = reporting_service.get_messages(limit=10, skip=0)

    assert len(messages) == 2
    # Verify query_documents is called with limit + skip
    mock_document_store.query_documents.assert_called_once_with(
        "messages",
        filter_dict={},
        limit=10,  # limit + skip = 10 + 0
    )


def test_get_messages_with_thread_filter(reporting_service, mock_document_store):
    """Test that get_messages supports thread_id filtering."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "thread_id": "thread1"},
    ]

    messages = reporting_service.get_messages(thread_id="thread1")

    assert len(messages) == 1
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["thread_id"] == "thread1"


def test_get_messages_with_message_id_filter(reporting_service, mock_document_store):
    """Test that get_messages supports message_id filtering."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "message_id": "<msg1@example.com>"},
    ]

    messages = reporting_service.get_messages(message_id="<msg1@example.com>")

    assert len(messages) == 1
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["message_id"] == "<msg1@example.com>"


def test_get_messages_with_skip(reporting_service, mock_document_store):
    """Test that get_messages pagination with non-zero skip returns correct subset."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg0", "message_id": "<msg0@example.com>"},
        {"_id": "msg1", "message_id": "<msg1@example.com>"},
        {"_id": "msg2", "message_id": "<msg2@example.com>"},
        {"_id": "msg3", "message_id": "<msg3@example.com>"},
    ]

    messages = reporting_service.get_messages(limit=2, skip=1)

    # Should return messages[1:3] which are msg1 and msg2
    assert len(messages) == 2
    assert messages[0]["_id"] == "msg1"
    assert messages[1]["_id"] == "msg2"

    # Verify query_documents is called with limit + skip
    mock_document_store.query_documents.assert_called_once_with(
        "messages",
        filter_dict={},
        limit=3,  # limit + skip = 2 + 1
    )


def test_get_message_by_id(reporting_service, mock_document_store):
    """Test that get_message_by_id retrieves a specific message."""
    mock_document_store.query_documents.return_value = [
        {"_id": "msg1", "message_id": "<msg1@example.com>", "body_normalized": "Test"},
    ]

    message = reporting_service.get_message_by_id("msg1")

    assert message is not None
    assert message["_id"] == "msg1"
    mock_document_store.query_documents.assert_called_once_with(
        "messages",
        filter_dict={"_id": "msg1"},
        limit=1,
    )


def test_get_message_by_id_not_found(reporting_service, mock_document_store):
    """Test that get_message_by_id returns None when not found."""
    mock_document_store.query_documents.return_value = []

    message = reporting_service.get_message_by_id("nonexistent")

    assert message is None


def test_get_chunks(reporting_service, mock_document_store):
    """Test that get_chunks retrieves chunks with pagination."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "Chunk 1"},
        {"_id": "chunk2", "text": "Chunk 2"},
    ]

    chunks = reporting_service.get_chunks(limit=10, skip=0)

    assert len(chunks) == 2
    # Verify query_documents is called with limit + skip
    mock_document_store.query_documents.assert_called_once_with(
        "chunks",
        filter_dict={},
        limit=10,  # limit + skip = 10 + 0
    )


def test_get_chunks_with_message_id_filter(reporting_service, mock_document_store):
    """Test that get_chunks supports message_id filtering."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "message_id": "<msg1@example.com>"},
    ]

    chunks = reporting_service.get_chunks(message_id="<msg1@example.com>")

    assert len(chunks) == 1
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["message_id"] == "<msg1@example.com>"


def test_get_chunks_with_thread_filter(reporting_service, mock_document_store):
    """Test that get_chunks supports thread_id filtering."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "thread_id": "thread1"},
    ]

    chunks = reporting_service.get_chunks(thread_id="thread1")

    assert len(chunks) == 1
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["thread_id"] == "thread1"


def test_get_chunks_with_message_doc_id_filter(reporting_service, mock_document_store):
    """Test that get_chunks supports message_doc_id filtering."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "message_doc_id": "msg_doc_1"},
    ]

    chunks = reporting_service.get_chunks(message_doc_id="msg_doc_1")

    assert len(chunks) == 1
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["filter_dict"]["message_doc_id"] == "msg_doc_1"


def test_get_chunks_with_skip(reporting_service, mock_document_store):
    """Test that get_chunks pagination with non-zero skip returns correct subset."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk0", "text": "Chunk 0"},
        {"_id": "chunk1", "text": "Chunk 1"},
        {"_id": "chunk2", "text": "Chunk 2"},
        {"_id": "chunk3", "text": "Chunk 3"},
        {"_id": "chunk4", "text": "Chunk 4"},
    ]

    chunks = reporting_service.get_chunks(limit=3, skip=1)

    # Should return chunks[1:4] which are chunk1, chunk2, chunk3
    assert len(chunks) == 3
    assert chunks[0]["_id"] == "chunk1"
    assert chunks[1]["_id"] == "chunk2"
    assert chunks[2]["_id"] == "chunk3"

    # Verify query_documents is called with limit + skip
    mock_document_store.query_documents.assert_called_once_with(
        "chunks",
        filter_dict={},
        limit=4,  # limit + skip = 3 + 1
    )


def test_get_chunk_by_id(reporting_service, mock_document_store):
    """Test that get_chunk_by_id retrieves a specific chunk."""
    mock_document_store.query_documents.return_value = [
        {"_id": "chunk1", "text": "Test chunk"},
    ]

    chunk = reporting_service.get_chunk_by_id("chunk1")

    assert chunk is not None
    assert chunk["_id"] == "chunk1"
    mock_document_store.query_documents.assert_called_once_with(
        "chunks",
        filter_dict={"_id": "chunk1"},
        limit=1,
    )


def test_get_chunk_by_id_not_found(reporting_service, mock_document_store):
    """Test that get_chunk_by_id returns None when not found."""
    mock_document_store.query_documents.return_value = []

    chunk = reporting_service.get_chunk_by_id("nonexistent")

    assert chunk is None


def test_cascade_cleanup_handler():
    """Test that reporting service handles SourceDeletionRequested events and deletes summaries."""
    from copilot_config.generated.adapters.document_store import (
        AdapterConfig_DocumentStore,
        DriverConfig_DocumentStore_Inmemory,
    )
    from copilot_storage import create_document_store
    from unittest.mock import Mock
    
    # Create test service
    document_store = create_document_store(
        AdapterConfig_DocumentStore(
            doc_store_type="inmemory",
            driver=DriverConfig_DocumentStore_Inmemory(),
        )
    )
    
    # Create a mock publisher that captures events
    class MockPublisher:
        def __init__(self):
            self.published_events = []
        
        def connect(self):
            pass
        
        def disconnect(self):
            pass
        
        def publish(self, event, routing_key, exchange):
            self.published_events.append({
                "event": event,
                "routing_key": routing_key,
                "exchange": exchange,
            })
    
    mock_publisher = MockPublisher()
    
    class MockSubscriber:
        def connect(self):
            pass
        
        def disconnect(self):
            pass
        
        def subscribe(self, event_type, exchange, routing_key, callback):
            pass
    
    from app.service import ReportingService
    service = ReportingService(
        document_store=document_store,
        publisher=mock_publisher,
        subscriber=MockSubscriber(),
        metrics_collector=Mock(),
    )
    
    # Add test data
    document_store.insert_document(
        "summaries",
        {
            "_id": "0123456789abcdef",
            "source": "test-source",
            "thread_id": "aaaaaaaaaaaaaaaa",
            "summary_type": "thread",
            "generated_at": "2025-01-18T00:00:00Z",
            "content_markdown": "Test summary 1",
        },
    )
    document_store.insert_document(
        "summaries",
        {
            "_id": "fedcba9876543210",
            "source": "test-source",
            "thread_id": "bbbbbbbbbbbbbbbb",
            "summary_type": "thread",
            "generated_at": "2025-01-18T00:00:00Z",
            "content_markdown": "Test summary 2",
        },
    )
    
    # Simulate SourceDeletionRequested event
    event = {
        "event_type": "SourceDeletionRequested",
        "event_id": "test-event-123",
        "timestamp": "2025-01-18T00:00:00Z",
        "version": "1.0",
        "data": {
            "source_name": "test-source",
            "correlation_id": "test-correlation-123",
            "requested_at": "2025-01-18T00:00:00Z",
            "archive_ids": ["archive-1"],
            "delete_mode": "hard"
        }
    }
    
    # Call the handler
    service._handle_source_deletion_requested(event)
    
    # Verify data was deleted
    summaries = document_store.query_documents("summaries", {"source": "test-source"})
    assert len(summaries) == 0, "Summaries should be deleted"
    
    # Verify SourceCleanupProgress event was published
    assert len(mock_publisher.published_events) == 1, "Should publish one progress event"
    
    progress_event = mock_publisher.published_events[0]
    assert progress_event["routing_key"] == "source.cleanup.progress"
    assert progress_event["event"]["event_type"] == "SourceCleanupProgress"
    assert progress_event["event"]["data"]["source_name"] == "test-source"
    assert progress_event["event"]["data"]["service_name"] == "reporting"
    assert progress_event["event"]["data"]["status"] == "completed"
    assert progress_event["event"]["data"]["correlation_id"] == "test-correlation-123"
    assert progress_event["event"]["data"]["deletion_counts"]["summaries"] == 2


# Tests for get_threads() with enhanced filtering and sorting


def test_get_threads_with_date_filter_inclusive_overlap(reporting_service, mock_document_store):
    """Test that get_threads supports date filtering with inclusive overlap."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "last_message_date": "2025-01-10T00:00:00Z",
                    "participants": ["alice@example.com"],
                    "message_count": 5,
                    "archive_id": "archive1",
                },
                {
                    "_id": "thread2",
                    "first_message_date": "2025-01-15T00:00:00Z",
                    "last_message_date": "2025-01-20T00:00:00Z",
                    "participants": ["bob@example.com"],
                    "message_count": 3,
                    "archive_id": "archive1",
                },
                {
                    "_id": "thread3",
                    "first_message_date": "2025-01-25T00:00:00Z",
                    "last_message_date": "2025-01-30T00:00:00Z",
                    "participants": ["charlie@example.com"],
                    "message_count": 7,
                    "archive_id": "archive1",
                },
            ]
        elif collection == "archives":
            return [{"_id": "archive1", "source": "test-list"}]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for messages between 2025-01-08 and 2025-01-17
    # Should include:
    # - thread1 (2025-01-05 to 2025-01-10) - overlaps at end
    # - thread2 (2025-01-15 to 2025-01-20) - overlaps at start
    # Should exclude:
    # - thread3 (2025-01-25 to 2025-01-30) - no overlap
    threads = reporting_service.get_threads(
        message_start_date="2025-01-08T00:00:00Z",
        message_end_date="2025-01-17T00:00:00Z",
    )

    assert len(threads) == 2
    thread_ids = {t["_id"] for t in threads}
    assert "thread1" in thread_ids
    assert "thread2" in thread_ids
    assert "thread3" not in thread_ids


def test_get_threads_with_start_date_only(reporting_service, mock_document_store):
    """Test that get_threads filters threads ending before start date."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-01T00:00:00Z",
                    "last_message_date": "2025-01-05T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "_id": "thread2",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": [],
                    "message_count": 3,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for threads starting from 2025-01-08
    # Should include thread2, exclude thread1
    threads = reporting_service.get_threads(
        message_start_date="2025-01-08T00:00:00Z",
    )

    assert len(threads) == 1
    assert threads[0]["_id"] == "thread2"


def test_get_threads_with_end_date_only(reporting_service, mock_document_store):
    """Test that get_threads filters threads starting after end date."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-01T00:00:00Z",
                    "last_message_date": "2025-01-05T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "_id": "thread2",
                    "first_message_date": "2025-01-20T00:00:00Z",
                    "last_message_date": "2025-01-25T00:00:00Z",
                    "participants": [],
                    "message_count": 3,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for threads ending by 2025-01-10
    # Should include thread1, exclude thread2
    threads = reporting_service.get_threads(
        message_end_date="2025-01-10T00:00:00Z",
    )

    assert len(threads) == 1
    assert threads[0]["_id"] == "thread1"


def test_get_threads_with_source_filter(reporting_service, mock_document_store):
    """Test that get_threads filters by archive source."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "participants": [], "message_count": 5, "archive_id": "archive1"},
                {"_id": "thread2", "participants": [], "message_count": 3, "archive_id": "archive2"},
                {"_id": "thread3", "participants": [], "message_count": 7, "archive_id": "archive1"},
            ]
        elif collection == "archives":
            return [
                {"_id": "archive1", "source": "test-list-a"},
                {"_id": "archive2", "source": "test-list-b"},
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for source test-list-a
    threads = reporting_service.get_threads(source="test-list-a")

    assert len(threads) == 2
    thread_ids = {t["_id"] for t in threads}
    assert "thread1" in thread_ids
    assert "thread3" in thread_ids
    assert "thread2" not in thread_ids


def test_get_threads_with_participant_filters(reporting_service, mock_document_store):
    """Test that get_threads filters by min/max participant count."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "participants": ["a@example.com"], "message_count": 5},
                {"_id": "thread2", "participants": ["a@example.com", "b@example.com"], "message_count": 3},
                {
                    "_id": "thread3",
                    "participants": ["a@example.com", "b@example.com", "c@example.com"],
                    "message_count": 7,
                },
                {
                    "_id": "thread4",
                    "participants": ["a@example.com", "b@example.com", "c@example.com", "d@example.com"],
                    "message_count": 10,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for 2-3 participants
    threads = reporting_service.get_threads(min_participants=2, max_participants=3)

    assert len(threads) == 2
    thread_ids = {t["_id"] for t in threads}
    assert "thread2" in thread_ids
    assert "thread3" in thread_ids
    assert "thread1" not in thread_ids  # Too few
    assert "thread4" not in thread_ids  # Too many


def test_get_threads_with_message_count_filters(reporting_service, mock_document_store):
    """Test that get_threads filters by min/max message count."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "participants": [], "message_count": 2},
                {"_id": "thread2", "participants": [], "message_count": 5},
                {"_id": "thread3", "participants": [], "message_count": 8},
                {"_id": "thread4", "participants": [], "message_count": 15},
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Filter for 5-10 messages
    threads = reporting_service.get_threads(min_messages=5, max_messages=10)

    assert len(threads) == 2
    thread_ids = {t["_id"] for t in threads}
    assert "thread2" in thread_ids
    assert "thread3" in thread_ids
    assert "thread1" not in thread_ids  # Too few
    assert "thread4" not in thread_ids  # Too many


def test_get_threads_with_combined_filters(reporting_service, mock_document_store):
    """Test that get_threads applies multiple filters simultaneously."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": ["a@example.com", "b@example.com"],
                    "message_count": 5,
                    "archive_id": "archive1",
                },
                {
                    "_id": "thread2",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": ["a@example.com"],
                    "message_count": 5,
                    "archive_id": "archive1",
                },
                {
                    "_id": "thread3",
                    "first_message_date": "2025-01-20T00:00:00Z",
                    "last_message_date": "2025-01-25T00:00:00Z",
                    "participants": ["a@example.com", "b@example.com"],
                    "message_count": 5,
                    "archive_id": "archive1",
                },
            ]
        elif collection == "archives":
            return [{"_id": "archive1", "source": "test-list"}]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Apply date filter + participant filter
    threads = reporting_service.get_threads(
        message_start_date="2025-01-08T00:00:00Z",
        message_end_date="2025-01-17T00:00:00Z",
        min_participants=2,
    )

    # Only thread1 matches both filters
    assert len(threads) == 1
    assert threads[0]["_id"] == "thread1"


def test_get_threads_sort_by_first_message_date_asc(reporting_service, mock_document_store):
    """Test that get_threads sorts by first_message_date ascending."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            # Return threads in a specific order that we'll verify was sorted
            return [
                {
                    "_id": "thread3",
                    "first_message_date": "2025-01-20T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "_id": "thread2",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads(sort_by="first_message_date", sort_order="asc")

    # Verify that query_documents was called with correct sort parameters
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["sort_by"] == "first_message_date"
    assert call_args[1]["sort_order"] == "asc"


def test_get_threads_sort_by_first_message_date_desc(reporting_service, mock_document_store):
    """Test that get_threads sorts by first_message_date descending (default)."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-05T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads(sort_by="first_message_date", sort_order="desc")

    # Verify that query_documents was called with correct sort parameters
    call_args = mock_document_store.query_documents.call_args
    assert call_args[1]["sort_by"] == "first_message_date"
    assert call_args[1]["sort_order"] == "desc"


def test_get_threads_enriches_archive_source(reporting_service, mock_document_store):
    """Test that get_threads enriches threads with archive_source field."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "participants": [], "message_count": 5, "archive_id": "archive1"},
                {"_id": "thread2", "participants": [], "message_count": 3, "archive_id": "archive2"},
            ]
        elif collection == "archives":
            return [
                {"_id": "archive1", "source": "ietf-httpbis"},
                {"_id": "archive2", "source": "w3c-public"},
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads()

    assert len(threads) == 2
    assert threads[0]["archive_source"] == "ietf-httpbis"
    assert threads[1]["archive_source"] == "w3c-public"


def test_get_threads_missing_archive_graceful(reporting_service, mock_document_store):
    """Test that threads with unknown archive_id still returned with null source."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {"_id": "thread1", "participants": [], "message_count": 5, "archive_id": "archive1"},
                {"_id": "thread2", "participants": [], "message_count": 3, "archive_id": "archive_missing"},
            ]
        elif collection == "archives":
            # Only archive1 exists, archive_missing does not
            return [{"_id": "archive1", "source": "test-list"}]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    threads = reporting_service.get_threads()

    assert len(threads) == 2
    assert threads[0]["archive_source"] == "test-list"
    assert threads[1]["archive_source"] is None  # Missing archive should have null source


def test_get_threads_skips_threads_without_dates_on_date_filter(reporting_service, mock_document_store):
    """Test that threads missing date fields are excluded when date filter is active."""

    def mock_query(collection, filter_dict, limit, sort_by=None, sort_order="desc"):
        if collection == "threads":
            return [
                {
                    "_id": "thread1",
                    "first_message_date": "2025-01-10T00:00:00Z",
                    "last_message_date": "2025-01-15T00:00:00Z",
                    "participants": [],
                    "message_count": 5,
                },
                {
                    "_id": "thread2",
                    # Missing date fields
                    "participants": [],
                    "message_count": 3,
                },
                {
                    "_id": "thread3",
                    "first_message_date": "2025-01-12T00:00:00Z",
                    # Missing last_message_date
                    "participants": [],
                    "message_count": 7,
                },
            ]
        return []

    mock_document_store.query_documents.side_effect = mock_query

    # Apply date filter
    threads = reporting_service.get_threads(
        message_start_date="2025-01-08T00:00:00Z",
        message_end_date="2025-01-17T00:00:00Z",
    )

    # Only thread1 has complete date info
    assert len(threads) == 1
    assert threads[0]["_id"] == "thread1"
