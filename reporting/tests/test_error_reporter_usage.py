# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for error reporter usage in reporting service."""

from unittest.mock import Mock, patch

import pytest
from app.service import ReportingService


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.insert_document = Mock()
    store.query_documents = Mock(return_value=[])
    store.update_document = Mock()
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
def mock_error_reporter():
    """Create a mock error reporter with report method."""
    reporter = Mock()
    reporter.report = Mock()
    return reporter


@pytest.fixture
def sample_event_data():
    """Create sample event data for testing."""
    return {
        "summary_id": "test_summary_123",
        "thread_id": "<thread@example.com>",
        "summary_markdown": "# Test Summary",
        "citations": [],
        "llm_backend": "test",
        "llm_model": "test-model",
        "tokens_prompt": 10,
        "tokens_completion": 5,
        "latency_ms": 1,
    }


def test_error_reporter_called_on_publish_report_published_failure(
    mock_document_store, mock_subscriber, mock_error_reporter
):
    """Test that error_reporter.report() is called when publishing ReportPublished event fails."""
    # Create a publisher that raises an exception
    failing_publisher = Mock()
    failing_publisher.publish = Mock(side_effect=Exception("Publish failed"))

    service = ReportingService(
        document_store=mock_document_store,
        publisher=failing_publisher,
        subscriber=mock_subscriber,
        error_reporter=mock_error_reporter,
    )

    # Should raise the exception
    with pytest.raises(Exception, match="Publish failed"):
        service._publish_report_published(
            report_id="test_report",
            thread_id="<thread@example.com>",
            notified=False,
            delivery_channels=[],
        )

    # Verify error_reporter.report() was called with the exception
    mock_error_reporter.report.assert_called_once()
    call_args = mock_error_reporter.report.call_args

    # Check that the exception was passed
    assert isinstance(call_args[0][0], Exception)
    assert "Publish failed" in str(call_args[0][0])

    # Check that context was passed
    assert call_args[1]["context"]["report_id"] == "test_report"
    assert call_args[1]["context"]["event_type"] == "ReportPublished"


def test_error_reporter_called_on_publish_delivery_failed_failure(
    mock_document_store, mock_subscriber, mock_error_reporter
):
    """Test that error_reporter.report() is called when publishing ReportDeliveryFailed event fails."""
    # Create a publisher that raises an exception
    failing_publisher = Mock()
    failing_publisher.publish = Mock(side_effect=Exception("Delivery publish failed"))

    service = ReportingService(
        document_store=mock_document_store,
        publisher=failing_publisher,
        subscriber=mock_subscriber,
        error_reporter=mock_error_reporter,
    )

    # Should raise the exception
    with pytest.raises(Exception, match="Delivery publish failed"):
        service._publish_delivery_failed(
            report_id="test_report",
            thread_id="<thread@example.com>",
            channel="webhook",
            error_message="Webhook failed",
            error_type="ConnectionError",
        )

    # Verify error_reporter.report() was called with the exception
    mock_error_reporter.report.assert_called_once()
    call_args = mock_error_reporter.report.call_args

    # Check that the exception was passed
    assert isinstance(call_args[0][0], Exception)
    assert "Delivery publish failed" in str(call_args[0][0])

    # Check that context was passed
    assert call_args[1]["context"]["report_id"] == "test_report"
    assert call_args[1]["context"]["event_type"] == "ReportDeliveryFailed"


def test_error_reporter_called_on_nested_exception_in_process_summary(
    mock_document_store, mock_subscriber, mock_error_reporter, sample_event_data
):
    """Test that error_reporter.report() is called when publishing delivery failed event fails during process_summary."""
    # Create a publisher that fails only when publishing delivery failed events
    failing_publisher = Mock()
    failing_publisher.publish.side_effect = lambda exchange, routing_key, event: (
        (_ for _ in ()).throw(Exception("Failed to publish delivery failed event"))
        if routing_key == "report.delivery.failed" else None
    )

    service = ReportingService(
        document_store=mock_document_store,
        publisher=failing_publisher,
        subscriber=mock_subscriber,
        error_reporter=mock_error_reporter,
        webhook_url="http://example.com/webhook",
        notify_enabled=True,
    )

    # Mock webhook to fail
    with patch("app.service.requests.post") as mock_post:
        mock_post.side_effect = Exception("Webhook connection failed")

        # Should raise the original webhook exception (chained from publish error)
        with pytest.raises(Exception, match="Webhook connection failed"):
            service.process_summary(sample_event_data, {"timestamp": "2025-01-01T00:00:00Z"})

    # Verify error_reporter.report() was called twice (once in _publish_delivery_failed, once in process_summary nested handler)
    assert mock_error_reporter.report.call_count == 2

    # Check the first call (from _publish_delivery_failed)
    first_call = mock_error_reporter.report.call_args_list[0]
    assert isinstance(first_call[0][0], Exception)
    assert "Failed to publish delivery failed event" in str(first_call[0][0])
    assert first_call[1]["context"]["event_type"] == "ReportDeliveryFailed"

    # Check the second call (from nested exception handler in process_summary)
    second_call = mock_error_reporter.report.call_args_list[1]
    assert isinstance(second_call[0][0], Exception)
    assert "Failed to publish delivery failed event" in str(second_call[0][0])
    assert "original_error" in second_call[1]["context"]
    assert "Webhook connection failed" in second_call[1]["context"]["original_error"]


def test_error_reporter_not_called_when_no_exception(
    mock_document_store, mock_publisher, mock_subscriber, mock_error_reporter
):
    """Test that error_reporter.report() is not called when operations succeed."""
    service = ReportingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        error_reporter=mock_error_reporter,
    )

    # Publish ReportPublished event successfully
    service._publish_report_published(
        report_id="test_report",
        thread_id="<thread@example.com>",
        notified=False,
        delivery_channels=[],
    )

    # Verify error_reporter.report() was not called
    mock_error_reporter.report.assert_not_called()


def test_error_reporter_not_called_when_error_reporter_is_none(
    mock_document_store, mock_subscriber
):
    """Test that code handles None error_reporter gracefully."""
    # Create a publisher that raises an exception
    failing_publisher = Mock()
    failing_publisher.publish = Mock(side_effect=Exception("Publish failed"))

    service = ReportingService(
        document_store=mock_document_store,
        publisher=failing_publisher,
        subscriber=mock_subscriber,
        error_reporter=None,  # No error reporter
    )

    # Should raise the exception without calling error_reporter
    with pytest.raises(Exception, match="Publish failed"):
        service._publish_report_published(
            report_id="test_report",
            thread_id="<thread@example.com>",
            notified=False,
            delivery_channels=[],
        )

    # No assertion needed - if this doesn't crash, the test passes
