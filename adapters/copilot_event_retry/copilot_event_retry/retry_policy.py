# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Retry policy implementation with exponential backoff and full jitter."""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum number of retry attempts (default: 8)
        base_delay_ms: Base delay in milliseconds (default: 250)
        backoff_factor: Exponential backoff multiplier (default: 2.0)
        max_delay_ms: Maximum delay cap in milliseconds (default: 60000 = 60s)
        ttl_seconds: Time-to-live in seconds; abandon after this duration (default: 1800 = 30 minutes)
        use_jitter: Whether to apply full jitter to delays (default: True)
    """
    max_attempts: int = 8
    base_delay_ms: int = 250
    backoff_factor: float = 2.0
    max_delay_ms: int = 60000
    ttl_seconds: int = 1800
    use_jitter: bool = True


@dataclass
class RetryContext:
    """Context tracking retry state across attempts.
    
    Attributes:
        attempt_number: Current attempt number (1-indexed)
        start_time: Timestamp when first attempt started
        last_exception: Last exception encountered
        idempotency_key: Optional idempotency key for deduplication
        metadata: Additional context metadata
    """
    attempt_number: int = 1
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_exception: Exception | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time since first attempt."""
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()
    
    def should_abandon(self, config: RetryConfig) -> bool:
        """Check if retry should be abandoned based on TTL."""
        return self.elapsed_seconds() >= config.ttl_seconds


class RetryPolicy:
    """Retry policy with exponential backoff and full jitter.
    
    Implements the retry strategy described in the issue:
    - Exponential backoff with full jitter
    - Configurable max attempts, delays, and TTL
    - Idempotency key support
    """
    
    def __init__(self, config: RetryConfig | None = None):
        """Initialize retry policy.
        
        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()
    
    def calculate_delay_ms(self, attempt_number: int) -> int:
        """Calculate delay for the given attempt number with exponential backoff.
        
        Args:
            attempt_number: Current attempt number (1-indexed)
            
        Returns:
            Delay in milliseconds (with jitter if enabled)
        """
        if attempt_number <= 1:
            return 0  # No delay for first attempt
        
        # Calculate exponential backoff: base * factor^(attempt - 1)
        exponent = attempt_number - 1
        delay_ms = int(self.config.base_delay_ms * (self.config.backoff_factor ** exponent))
        
        # Apply max delay cap
        delay_ms = min(delay_ms, self.config.max_delay_ms)
        
        # Apply full jitter: random value between 0 and calculated delay
        if self.config.use_jitter:
            delay_ms = random.randint(0, delay_ms)
        
        return delay_ms
    
    def should_retry(self, context: RetryContext, exception: Exception) -> bool:
        """Determine if retry should be attempted.
        
        Args:
            context: Current retry context
            exception: Exception that triggered retry consideration
            
        Returns:
            True if retry should be attempted, False otherwise
        """
        # Check max attempts
        if context.attempt_number >= self.config.max_attempts:
            return False
        
        # Check TTL
        if context.should_abandon(self.config):
            return False
        
        # Only retry on retryable errors (checked by caller)
        return True
    
    def sleep(self, delay_ms: int) -> None:
        """Sleep for the specified delay.
        
        Args:
            delay_ms: Delay in milliseconds
        """
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
