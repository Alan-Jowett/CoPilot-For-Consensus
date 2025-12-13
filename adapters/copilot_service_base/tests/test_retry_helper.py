# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for retry helper utilities."""

import pytest
import time
from unittest.mock import Mock

from copilot_service_base.retry_helper import retry_with_backoff


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""
    
    def test_successful_first_attempt(self):
        """Test that function succeeds on first attempt."""
        func = Mock(return_value="success")
        
        result = retry_with_backoff(func, max_attempts=3)
        
        assert result == "success"
        assert func.call_count == 1
    
    def test_retry_on_failure_then_success(self):
        """Test that function retries on failure then succeeds."""
        func = Mock(side_effect=[ValueError("error1"), ValueError("error2"), "success"])
        
        result = retry_with_backoff(func, max_attempts=3, backoff_seconds=0.01)
        
        assert result == "success"
        assert func.call_count == 3
    
    def test_max_retries_exhausted(self):
        """Test that exception is raised when max retries exhausted."""
        func = Mock(side_effect=ValueError("persistent error"))
        
        with pytest.raises(ValueError, match="persistent error"):
            retry_with_backoff(func, max_attempts=3, backoff_seconds=0.01)
        
        assert func.call_count == 3
    
    def test_exponential_backoff_calculation(self, monkeypatch):
        """Test that backoff times follow exponential pattern."""
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
        
        monkeypatch.setattr(time, 'sleep', mock_sleep)
        
        func = Mock(side_effect=[ValueError(), ValueError(), ValueError()])
        
        with pytest.raises(ValueError):
            retry_with_backoff(func, max_attempts=3, backoff_seconds=5, max_backoff_seconds=60)
        
        # Should have 2 sleeps (before attempt 2 and 3)
        assert len(sleep_times) == 2
        # First backoff: 5 * 2^0 = 5
        assert sleep_times[0] == 5
        # Second backoff: 5 * 2^1 = 10
        assert sleep_times[1] == 10
    
    def test_backoff_capped_at_max(self, monkeypatch):
        """Test that backoff is capped at max_backoff_seconds."""
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
        
        monkeypatch.setattr(time, 'sleep', mock_sleep)
        
        func = Mock(side_effect=[ValueError()] * 5)
        
        with pytest.raises(ValueError):
            retry_with_backoff(
                func,
                max_attempts=5,
                backoff_seconds=30,
                max_backoff_seconds=60
            )
        
        # All backoffs should be capped at 60
        # 30, 60, 60, 60
        assert sleep_times[0] == 30
        for backoff in sleep_times[1:]:
            assert backoff == 60
    
    def test_on_retry_callback(self):
        """Test that on_retry callback is called on each retry."""
        func = Mock(side_effect=[ValueError("error1"), ValueError("error2"), "success"])
        on_retry = Mock()
        
        result = retry_with_backoff(
            func,
            max_attempts=3,
            backoff_seconds=0.01,
            on_retry=on_retry
        )
        
        assert result == "success"
        assert on_retry.call_count == 2  # Called for first 2 failures
        
        # Check callback arguments
        calls = on_retry.call_args_list
        assert calls[0][0][1] == 1  # First retry, attempt number 1
        assert calls[1][0][1] == 2  # Second retry, attempt number 2
    
    def test_on_failure_callback(self):
        """Test that on_failure callback is called when retries exhausted."""
        func = Mock(side_effect=ValueError("persistent"))
        on_failure = Mock()
        
        with pytest.raises(ValueError):
            retry_with_backoff(
                func,
                max_attempts=3,
                backoff_seconds=0.01,
                on_failure=on_failure
            )
        
        assert on_failure.call_count == 1
        # Should be called with last exception and attempt number
        assert on_failure.call_args[0][1] == 3
    
    def test_no_sleep_on_last_attempt(self, monkeypatch):
        """Test that no sleep occurs after the last failed attempt."""
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
        
        monkeypatch.setattr(time, 'sleep', mock_sleep)
        
        func = Mock(side_effect=ValueError())
        
        with pytest.raises(ValueError):
            retry_with_backoff(func, max_attempts=3, backoff_seconds=5)
        
        # Should only sleep before attempt 2 and 3, not after attempt 3
        assert len(sleep_times) == 2
