# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event handler retry wrapper."""

from unittest.mock import Mock

import pytest
from copilot_event_retry import (
    DocumentNotFoundError,
    RetryableError,
    RetryConfig,
    handle_event_with_retry,
)
from copilot_event_retry.event_handler import RetryExhaustedError


class TestHandleEventWithRetry:
    """Tests for handle_event_with_retry function."""

    def test_success_on_first_attempt(self):
        """Test successful processing on first attempt."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        handle_event_with_retry(handler, event)

        # Handler should be called once
        handler.assert_called_once_with(event)

    def test_success_after_retries(self):
        """Test successful processing after retries."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        # Fail twice, then succeed
        handler.side_effect = [
            DocumentNotFoundError("Not found"),
            DocumentNotFoundError("Not found"),
            None,  # Success
        ]

        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=10,
            use_jitter=False,
        )

        handle_event_with_retry(handler, event, config=config)

        # Handler should be called 3 times
        assert handler.call_count == 3

    def test_retry_exhausted_max_attempts(self):
        """Test retry exhaustion due to max attempts."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        # Always fail with retryable error
        handler.side_effect = DocumentNotFoundError("Not found")

        config = RetryConfig(
            max_attempts=3,
            base_delay_ms=10,
            ttl_seconds=600,
            use_jitter=False,
        )

        with pytest.raises(RetryExhaustedError) as exc_info:
            handle_event_with_retry(handler, event, config=config)

        # Should have attempted 3 times
        assert handler.call_count == 3

        # Check DLQ info
        error = exc_info.value
        assert error.context.attempt_number == 3
        assert error.dlq_info["attempt_count"] == 3
        assert error.dlq_info["last_error_type"] == "DocumentNotFoundError"

    def test_retry_exhausted_ttl(self):
        """Test retry exhaustion due to TTL."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        # Always fail with retryable error
        handler.side_effect = DocumentNotFoundError("Not found")

        # Very short TTL
        config = RetryConfig(
            max_attempts=10,
            base_delay_ms=1,
            ttl_seconds=0,  # Immediate timeout
            use_jitter=False,
        )

        with pytest.raises(RetryExhaustedError):
            handle_event_with_retry(handler, event, config=config)

        # Should only attempt once (TTL expired before first retry)
        assert handler.call_count == 1

    def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        # Fail with non-retryable error
        handler.side_effect = ValueError("Invalid data")

        config = RetryConfig(max_attempts=5)

        with pytest.raises(ValueError, match="Invalid data"):
            handle_event_with_retry(handler, event, config=config)

        # Should only attempt once
        assert handler.call_count == 1

    def test_metrics_collection_success(self):
        """Test metrics are collected on success."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}
        metrics_collector = Mock()

        # Succeed after 2 attempts
        handler.side_effect = [
            DocumentNotFoundError("Not found"),
            None,  # Success
        ]

        config = RetryConfig(base_delay_ms=10, use_jitter=False)

        handle_event_with_retry(
            handler,
            event,
            config=config,
            metrics_collector=metrics_collector,
            service_name="test_service",
        )

        # Check metrics calls
        calls = metrics_collector.increment.call_args_list

        # Should have attempt metrics (2 attempts)
        attempt_calls = [c for c in calls if "attempts_total" in str(c)]
        assert len(attempt_calls) == 2

        # Should have retry count metric (1 retry)
        retry_calls = [c for c in calls if "retry_count_total" in str(c)]
        assert len(retry_calls) == 1

        # Should have success metric
        success_calls = [c for c in calls if "success_total" in str(c)]
        assert len(success_calls) == 1

        # Should have latency observation
        assert metrics_collector.observe.called

    def test_metrics_collection_dlq(self):
        """Test metrics are collected for DLQ cases."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}
        metrics_collector = Mock()

        # Always fail
        handler.side_effect = DocumentNotFoundError("Not found")

        config = RetryConfig(max_attempts=2, base_delay_ms=10, use_jitter=False)

        with pytest.raises(RetryExhaustedError):
            handle_event_with_retry(
                handler,
                event,
                config=config,
                metrics_collector=metrics_collector,
                service_name="test_service",
            )

        # Should have DLQ metric
        calls = metrics_collector.increment.call_args_list
        dlq_calls = [c for c in calls if "dlq_total" in str(c)]
        assert len(dlq_calls) == 1

    def test_error_reporter_called_on_dlq(self):
        """Test error reporter is called when retry is exhausted."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}
        error_reporter = Mock()

        # Always fail
        handler.side_effect = DocumentNotFoundError("Not found")

        config = RetryConfig(max_attempts=2, base_delay_ms=10, use_jitter=False)

        with pytest.raises(RetryExhaustedError):
            handle_event_with_retry(
                handler,
                event,
                config=config,
                error_reporter=error_reporter,
            )

        # Error reporter should be called with DLQ info
        assert error_reporter.report.called
        call_args = error_reporter.report.call_args
        assert "context" in call_args[1]
        dlq_info = call_args[1]["context"]
        assert "original_event" in dlq_info
        assert "attempt_count" in dlq_info

    def test_error_reporter_called_on_non_retryable(self):
        """Test error reporter is called for non-retryable errors."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}
        error_reporter = Mock()

        # Non-retryable error
        handler.side_effect = ValueError("Invalid")

        with pytest.raises(ValueError):
            handle_event_with_retry(
                handler,
                event,
                error_reporter=error_reporter,
            )

        # Error reporter should be called
        assert error_reporter.report.called

    def test_idempotency_key(self):
        """Test idempotency key is tracked in context."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}
        error_reporter = Mock()

        # Fail to trigger DLQ with idempotency key
        handler.side_effect = DocumentNotFoundError("Not found")

        config = RetryConfig(max_attempts=1)

        with pytest.raises(RetryExhaustedError) as exc_info:
            handle_event_with_retry(
                handler,
                event,
                config=config,
                idempotency_key="test-key-123",
                error_reporter=error_reporter,
            )

        # Check idempotency key in DLQ info
        error = exc_info.value
        assert error.context.idempotency_key == "test-key-123"
        assert error.dlq_info["idempotency_key"] == "test-key-123"

    def test_different_retryable_errors(self):
        """Test handling of different retryable error types."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        # Custom retryable error
        class CustomRetryableError(RetryableError):
            pass

        # Fail with custom error, then succeed
        handler.side_effect = [
            CustomRetryableError("Custom error"),
            None,
        ]

        config = RetryConfig(base_delay_ms=10, use_jitter=False)

        handle_event_with_retry(handler, event, config=config)

        # Should succeed after retry
        assert handler.call_count == 2


class TestDLQInfoBuilding:
    """Tests for dead letter queue info building."""

    def test_dlq_info_structure(self):
        """Test DLQ info contains all required fields."""
        handler = Mock()
        event = {"event_type": "TestEvent", "data": {"id": "123"}}

        handler.side_effect = DocumentNotFoundError("Not found")

        config = RetryConfig(max_attempts=2, base_delay_ms=10)

        with pytest.raises(RetryExhaustedError) as exc_info:
            handle_event_with_retry(
                handler,
                event,
                config=config,
                idempotency_key="key-123",
                service_name="test_service",
            )

        dlq_info = exc_info.value.dlq_info

        # Check required fields
        assert "original_event" in dlq_info
        assert dlq_info["original_event"] == event
        assert "attempt_count" in dlq_info
        assert dlq_info["attempt_count"] == 2
        assert "elapsed_seconds" in dlq_info
        assert "last_error_type" in dlq_info
        assert dlq_info["last_error_type"] == "DocumentNotFoundError"
        assert "last_error_message" in dlq_info
        assert "retry_config" in dlq_info
        assert "abandoned_at" in dlq_info
        assert "idempotency_key" in dlq_info
        assert dlq_info["idempotency_key"] == "key-123"
        assert "metadata" in dlq_info
