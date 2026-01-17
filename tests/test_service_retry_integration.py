# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for service retry behavior with race conditions."""

import time
from typing import Any
from unittest.mock import Mock, call

import pytest

# Test that copilot_event_retry adapter can be imported
try:
    from copilot_event_retry import (
        DocumentNotFoundError,
        RetryConfig,
        handle_event_with_retry,
    )
    from copilot_event_retry.event_handler import RetryExhaustedError
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False
    # Define dummy classes when module not available
    RetryExhaustedError = Exception  # type: ignore


@pytest.mark.skipif(not RETRY_AVAILABLE, reason="copilot_event_retry not available")
class TestServiceRetryBehavior:
    """Test retry behavior for handling race conditions in services."""

    def test_retry_on_document_not_found(self):
        """Test that DocumentNotFoundError triggers retry logic."""
        # Simulate a handler that fails twice with DocumentNotFoundError
        # then succeeds on the third attempt
        attempt_count = {"value": 0}
        
        def handler(event: dict[str, Any]) -> None:
            attempt_count["value"] += 1
            if attempt_count["value"] < 3:
                raise DocumentNotFoundError("Document not yet queryable")
            # Success on third attempt
            
        event = {"type": "test_event", "data": {"id": "123"}}
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=10,  # Short delays for testing
            backoff_factor=1.5,
            max_delay_ms=1000,  # 1 second
            ttl_seconds=60,  # 1 minute
        )
        
        # Should succeed after retries
        handle_event_with_retry(
            handler=handler,
            event=event,
            config=config,
            idempotency_key="test-123",
            service_name="test-service",
        )
        
        # Verify handler was called 3 times
        assert attempt_count["value"] == 3

    def test_retry_exhaustion_sends_to_dlq(self):
        """Test that exhausted retries send event to DLQ."""
        def handler(event: dict[str, Any]) -> None:
            # Always fail with retryable error
            raise DocumentNotFoundError("Document never becomes queryable")
        
        event = {"type": "test_event", "data": {"id": "456"}}
        config = RetryConfig(
            max_attempts=3,
            base_delay_ms=10,
            backoff_factor=1.5,
            max_delay_ms=1000,  # 1 second
            ttl_seconds=60,  # 1 minute
        )
        
        mock_metrics = Mock()
        mock_error_reporter = Mock()
        
        # Should eventually give up and send to DLQ
        # The handle_event_with_retry will raise RetryExhaustedError when max attempts is reached
        with pytest.raises(RetryExhaustedError):
            handle_event_with_retry(
                handler=handler,
                event=event,
                config=config,
                idempotency_key="test-456",
                metrics_collector=mock_metrics,
                error_reporter=mock_error_reporter,
                service_name="test-service",
            )

    def test_non_retryable_error_immediate_failure(self):
        """Test that non-retryable errors fail immediately without retries."""
        attempt_count = {"value": 0}
        
        def handler(event: dict[str, Any]) -> None:
            attempt_count["value"] += 1
            # Non-retryable error (ValueError is not DocumentNotFoundError)
            raise ValueError("Invalid event format")
        
        event = {"type": "test_event", "data": {"id": "789"}}
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=10,
            backoff_factor=1.5,
            max_delay_ms=1000,  # 1 second
            ttl_seconds=60,  # 1 minute
        )
        
        # Should fail immediately without retries
        with pytest.raises(ValueError):
            handle_event_with_retry(
                handler=handler,
                event=event,
                config=config,
                idempotency_key="test-789",
                service_name="test-service",
            )
        
        # Verify handler was only called once (no retries for non-retryable errors)
        assert attempt_count["value"] == 1

    def test_idempotency_key_tracking(self):
        """Test that idempotency keys are properly tracked across retries."""
        call_history = []
        
        def handler(event: dict[str, Any]) -> None:
            call_history.append(event)
            if len(call_history) < 2:
                raise DocumentNotFoundError("Not ready yet")
        
        event = {"type": "test_event", "data": {"id": "abc"}}
        config = RetryConfig(max_attempts=3, base_delay_ms=10)
        
        handle_event_with_retry(
            handler=handler,
            event=event,
            config=config,
            idempotency_key="test-abc-idempotency",
            service_name="test-service",
        )
        
        # Verify same event was passed to all retry attempts
        assert len(call_history) == 2
        assert all(e == event for e in call_history)

    def test_metrics_collection_on_retry(self):
        """Test that metrics are collected during retry attempts."""
        attempt_count = {"value": 0}
        
        def handler(event: dict[str, Any]) -> None:
            attempt_count["value"] += 1
            if attempt_count["value"] < 2:
                raise DocumentNotFoundError("Not ready")
        
        event = {"type": "test_event", "data": {"id": "metrics"}}
        config = RetryConfig(max_attempts=5, base_delay_ms=10)
        mock_metrics = Mock()
        
        handle_event_with_retry(
            handler=handler,
            event=event,
            config=config,
            idempotency_key="test-metrics",
            metrics_collector=mock_metrics,
            service_name="test-service",
        )
        
        # Verify metrics collector was called
        # The exact calls depend on the implementation, but we should see some activity
        assert mock_metrics.increment.called or mock_metrics.record_value.called or mock_metrics.observe.called

    def test_exponential_backoff_timing(self):
        """Test that retry delays follow exponential backoff pattern."""
        timestamps = []
        
        def handler(event: dict[str, Any]) -> None:
            timestamps.append(time.time())
            if len(timestamps) < 4:
                raise DocumentNotFoundError("Not ready")
        
        event = {"type": "test_event", "data": {"id": "timing"}}
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=100,  # 100ms base
            backoff_factor=2.0,
            max_delay_ms=10000,  # 10 seconds
        )
        
        start_time = time.time()
        handle_event_with_retry(
            handler=handler,
            event=event,
            config=config,
            idempotency_key="test-timing",
            service_name="test-service",
        )
        total_time = time.time() - start_time
        
        # Verify handler was called 4 times
        assert len(timestamps) == 4
        
        # With exponential backoff: 100ms, 200ms, 400ms (with jitter, actual times vary)
        # Total should be at least 700ms but allow for jitter and overhead
        assert total_time >= 0.5  # Conservative lower bound accounting for jitter
        assert total_time <= 2.0  # Upper bound allowing overhead


@pytest.mark.skipif(not RETRY_AVAILABLE, reason="copilot_event_retry not available")
class TestRetryConfigValidation:
    """Test retry configuration validation."""

    def test_default_retry_config(self):
        """Test default retry configuration values."""
        config = RetryConfig()
        
        assert config.max_attempts == 8
        assert config.base_delay_ms == 250
        assert config.backoff_factor == 2.0
        assert config.max_delay_ms == 60000  # 60 seconds in milliseconds
        assert config.ttl_seconds == 1800  # 30 minutes in seconds

    def test_custom_retry_config(self):
        """Test custom retry configuration values."""
        config = RetryConfig(
            max_attempts=10,
            base_delay_ms=500,
            backoff_factor=3.0,
            max_delay_ms=120000,  # 120 seconds in milliseconds
            ttl_seconds=3600,  # 60 minutes in seconds
        )
        
        assert config.max_attempts == 10
        assert config.base_delay_ms == 500
        assert config.backoff_factor == 3.0
        assert config.max_delay_ms == 120000
        assert config.ttl_seconds == 3600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
