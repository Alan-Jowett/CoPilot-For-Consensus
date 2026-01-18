# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for retry policy implementation."""

import time
from datetime import datetime, timedelta, timezone

from copilot_event_retry import RetryConfig, RetryContext, RetryPolicy


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 8
        assert config.base_delay_ms == 250
        assert config.backoff_factor == 2.0
        assert config.max_delay_ms == 60000
        assert config.ttl_seconds == 1800
        assert config.use_jitter is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=100,
            backoff_factor=1.5,
            max_delay_ms=30000,
            ttl_seconds=600,
            use_jitter=False,
        )
        assert config.max_attempts == 5
        assert config.base_delay_ms == 100
        assert config.backoff_factor == 1.5
        assert config.max_delay_ms == 30000
        assert config.ttl_seconds == 600
        assert config.use_jitter is False


class TestRetryContext:
    """Tests for RetryContext."""

    def test_initial_state(self):
        """Test initial context state."""
        context = RetryContext()
        assert context.attempt_number == 1
        assert context.last_exception is None
        assert context.idempotency_key is None
        assert context.metadata == {}

    def test_elapsed_seconds(self):
        """Test elapsed time calculation."""
        past_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        context = RetryContext(start_time=past_time)
        elapsed = context.elapsed_seconds()
        assert 4.5 <= elapsed <= 5.5  # Allow for test execution time

    def test_should_abandon_ttl_not_exceeded(self):
        """Test TTL check when time has not exceeded."""
        config = RetryConfig(ttl_seconds=10)
        context = RetryContext()
        assert not context.should_abandon(config)

    def test_should_abandon_ttl_exceeded(self):
        """Test TTL check when time has exceeded."""
        config = RetryConfig(ttl_seconds=1)
        past_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        context = RetryContext(start_time=past_time)
        assert context.should_abandon(config)


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_calculate_delay_first_attempt(self):
        """Test delay calculation for first attempt (should be 0)."""
        policy = RetryPolicy(RetryConfig(use_jitter=False))
        delay = policy.calculate_delay_ms(1)
        assert delay == 0

    def test_calculate_delay_exponential_backoff(self):
        """Test exponential backoff without jitter."""
        config = RetryConfig(
            base_delay_ms=100,
            backoff_factor=2.0,
            max_delay_ms=10000,
            use_jitter=False,
        )
        policy = RetryPolicy(config)

        # Attempt 2: 100 * 2^(2-1) = 100 * 2 = 200
        assert policy.calculate_delay_ms(2) == 200

        # Attempt 3: 100 * 2^(3-1) = 100 * 4 = 400
        assert policy.calculate_delay_ms(3) == 400

        # Attempt 4: 100 * 2^(4-1) = 100 * 8 = 800
        assert policy.calculate_delay_ms(4) == 800

    def test_calculate_delay_max_cap(self):
        """Test that delay is capped at max_delay_ms."""
        config = RetryConfig(
            base_delay_ms=1000,
            backoff_factor=2.0,
            max_delay_ms=5000,
            use_jitter=False,
        )
        policy = RetryPolicy(config)

        # Attempt 10 would be very large, but should be capped
        delay = policy.calculate_delay_ms(10)
        assert delay == 5000

    def test_calculate_delay_with_jitter(self):
        """Test that jitter produces random values in expected range."""
        config = RetryConfig(
            base_delay_ms=100,
            backoff_factor=2.0,
            max_delay_ms=10000,
            use_jitter=True,
        )
        policy = RetryPolicy(config)

        # Run multiple times to verify randomness
        delays = [policy.calculate_delay_ms(3) for _ in range(10)]

        # Expected base: 100 * 2^2 = 400
        # Jitter should produce values in [0, 400]
        assert all(0 <= d <= 400 for d in delays)

        # Should have some variety (not all the same)
        assert len(set(delays)) > 1

    def test_should_retry_max_attempts_not_exceeded(self):
        """Test retry decision when max attempts not exceeded."""
        config = RetryConfig(max_attempts=5, ttl_seconds=1800)
        policy = RetryPolicy(config)
        context = RetryContext(attempt_number=3)

        assert policy.should_retry(context, Exception("test"))

    def test_should_retry_max_attempts_exceeded(self):
        """Test retry decision when max attempts exceeded."""
        config = RetryConfig(max_attempts=5, ttl_seconds=1800)
        policy = RetryPolicy(config)
        context = RetryContext(attempt_number=5)

        assert not policy.should_retry(context, Exception("test"))

    def test_should_retry_ttl_not_exceeded(self):
        """Test retry decision when TTL not exceeded."""
        config = RetryConfig(max_attempts=10, ttl_seconds=10)
        policy = RetryPolicy(config)
        context = RetryContext(attempt_number=2)

        assert policy.should_retry(context, Exception("test"))

    def test_should_retry_ttl_exceeded(self):
        """Test retry decision when TTL exceeded."""
        config = RetryConfig(max_attempts=10, ttl_seconds=1)
        policy = RetryPolicy(config)
        past_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        context = RetryContext(attempt_number=2, start_time=past_time)

        assert not policy.should_retry(context, Exception("test"))

    def test_sleep(self):
        """Test sleep functionality."""
        policy = RetryPolicy()
        start = time.time()
        policy.sleep(100)  # 100ms
        elapsed = time.time() - start

        # Should sleep approximately 100ms (allow for variance)
        assert 0.08 <= elapsed <= 0.15


class TestRetryPolicyIntegration:
    """Integration tests for full retry scenarios."""

    def test_full_retry_sequence(self):
        """Test a complete retry sequence with backoff."""
        config = RetryConfig(
            max_attempts=4,
            base_delay_ms=50,
            backoff_factor=2.0,
            max_delay_ms=1000,
            ttl_seconds=60,
            use_jitter=False,
        )
        policy = RetryPolicy(config)
        context = RetryContext()

        # Track delays
        delays = []

        while context.attempt_number < config.max_attempts:
            context.attempt_number += 1
            if context.attempt_number > 1:
                delay = policy.calculate_delay_ms(context.attempt_number)
                delays.append(delay)

        # Verify exponential progression: 50, 100, 200
        # Attempt 2: 50 * 2^(2-1) = 50 * 2 = 100
        # Attempt 3: 50 * 2^(3-1) = 50 * 4 = 200
        # Attempt 4: 50 * 2^(4-1) = 50 * 8 = 400
        assert delays == [100, 200, 400]
