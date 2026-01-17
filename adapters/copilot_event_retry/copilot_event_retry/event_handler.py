# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Event handler wrapper with retry logic for transient failures."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .retry_policy import RetryConfig, RetryContext, RetryPolicy

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass


class DocumentNotFoundError(RetryableError):
    """Error raised when expected document is not found in datastore.
    
    This is the primary error handled by the retry logic, as it indicates
    a race condition where the event arrived before the document became queryable.
    """
    pass


class RetryExhaustedError(Exception):
    """Error raised when all retry attempts have been exhausted."""
    
    def __init__(self, message: str, context: RetryContext, dlq_info: dict[str, Any]):
        """Initialize retry exhausted error.
        
        Args:
            message: Error message
            context: Final retry context
            dlq_info: Dead letter queue diagnostic information
        """
        super().__init__(message)
        self.context = context
        self.dlq_info = dlq_info


def handle_event_with_retry(
    handler: Callable[[dict[str, Any]], None],
    event: dict[str, Any],
    config: RetryConfig | None = None,
    idempotency_key: str | None = None,
    metrics_collector: Any = None,
    error_reporter: Any = None,
    service_name: str = "unknown",
) -> None:
    """Handle event with retry logic for transient failures.
    
    Wraps an event handler with retry logic that handles race conditions where
    documents are not yet queryable. Implements exponential backoff with jitter,
    TTL enforcement, and dead letter queue integration.
    
    Args:
        handler: Event handler function to call
        event: Event data dictionary
        config: Retry configuration (uses defaults if None)
        idempotency_key: Optional idempotency key for deduplication
        metrics_collector: Optional metrics collector for observability
        error_reporter: Optional error reporter for failure tracking
        service_name: Service name for logging and metrics
        
    Raises:
        RetryExhaustedError: When all retry attempts are exhausted
        Exception: Non-retryable errors are re-raised immediately
    """
    policy = RetryPolicy(config or RetryConfig())
    context = RetryContext(
        attempt_number=1,
        idempotency_key=idempotency_key,
        metadata={"service": service_name, "event_type": event.get("event_type")},
    )
    
    while True:
        try:
            # Track attempt in metrics
            if metrics_collector:
                metrics_collector.increment(
                    f"{service_name}_event_retry_attempts_total",
                    tags={
                        "attempt": str(context.attempt_number),
                        "event_type": event.get("event_type", "unknown"),
                    }
                )
            
            # Call the actual handler
            handler(event)
            
            # Success - record metrics and return
            if metrics_collector:
                metrics_collector.increment(
                    f"{service_name}_event_retry_success_total",
                    tags={
                        "attempts": str(context.attempt_number),
                        "event_type": event.get("event_type", "unknown"),
                    }
                )
                
                # Record success latency
                elapsed_ms = context.elapsed_seconds() * 1000
                metrics_collector.observe(
                    f"{service_name}_event_retry_latency_ms",
                    elapsed_ms,
                    tags={"event_type": event.get("event_type", "unknown")}
                )
            
            if context.attempt_number > 1:
                logger.info(
                    f"Event processed successfully after {context.attempt_number} attempts "
                    f"({context.elapsed_seconds():.2f}s elapsed)"
                )
            
            return
            
        except RetryableError as e:
            context.last_exception = e
            
            # Check if we should retry
            if not policy.should_retry(context, e):
                # Retry exhausted - prepare for dead letter queue
                dlq_info = _build_dlq_info(event, context, policy.config)
                
                logger.error(
                    f"Retry exhausted for event after {context.attempt_number} attempts "
                    f"({context.elapsed_seconds():.2f}s): {e}",
                    extra={"dlq_info": dlq_info}
                )
                
                # Report to dead letter queue via metrics
                if metrics_collector:
                    metrics_collector.increment(
                        f"{service_name}_event_dlq_total",
                        tags={
                            "reason": type(e).__name__,
                            "event_type": event.get("event_type", "unknown"),
                        }
                    )
                
                # Report error with context
                if error_reporter:
                    error_reporter.report(e, context=dlq_info)
                
                raise RetryExhaustedError(
                    f"Retry exhausted after {context.attempt_number} attempts",
                    context,
                    dlq_info
                ) from e
            
            # Calculate delay and sleep
            delay_ms = policy.calculate_delay_ms(context.attempt_number + 1)
            
            logger.warning(
                f"Retryable error on attempt {context.attempt_number}, "
                f"retrying in {delay_ms}ms: {e}"
            )
            
            # Record retry in metrics
            if metrics_collector:
                metrics_collector.increment(
                    f"{service_name}_event_retry_count_total",
                    tags={
                        "reason": type(e).__name__,
                        "event_type": event.get("event_type", "unknown"),
                    }
                )
            
            # Sleep before next attempt
            policy.sleep(delay_ms)
            
            # Increment attempt counter
            context.attempt_number += 1
            
        except Exception as e:
            # Non-retryable error - fail immediately
            logger.error(
                f"Non-retryable error on attempt {context.attempt_number}: {e}",
                exc_info=True
            )
            
            if metrics_collector:
                metrics_collector.increment(
                    f"{service_name}_event_non_retryable_errors_total",
                    tags={
                        "error_type": type(e).__name__,
                        "event_type": event.get("event_type", "unknown"),
                    }
                )
            
            if error_reporter:
                error_reporter.report(e, context={
                    "service": service_name,
                    "event": event,
                    "attempt": context.attempt_number,
                })
            
            # Re-raise non-retryable errors
            raise


def _build_dlq_info(event: dict[str, Any], context: RetryContext, config: RetryConfig) -> dict[str, Any]:
    """Build diagnostic payload for dead letter queue.
    
    Args:
        event: Original event data
        context: Final retry context
        config: Retry configuration used
        
    Returns:
        Dictionary with DLQ diagnostic information
    """
    return {
        "original_event": event,
        "attempt_count": context.attempt_number,
        "elapsed_seconds": context.elapsed_seconds(),
        "last_error_type": type(context.last_exception).__name__ if context.last_exception else None,
        "last_error_message": str(context.last_exception) if context.last_exception else None,
        "retry_config": {
            "max_attempts": config.max_attempts,
            "base_delay_ms": config.base_delay_ms,
            "max_delay_ms": config.max_delay_ms,
            "ttl_seconds": config.ttl_seconds,
        },
        "abandoned_at": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": context.idempotency_key,
        "metadata": context.metadata,
    }
