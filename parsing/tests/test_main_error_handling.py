# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for parsing service main.py subscriber thread error handling."""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import start_subscriber_thread


class MockParsingService:
    """Mock parsing service for testing."""
    
    def __init__(self):
        self.subscriber = MagicMock()
        
    def start(self):
        """Mock start method."""
        pass


class TestStartSubscriberThread:
    """Tests for start_subscriber_thread error handling."""
    
    def test_handles_transport_assertion_error_gracefully(self, caplog):
        """Test that transport assertion errors are handled gracefully."""
        import logging
        caplog.set_level(logging.WARNING)
        
        service = MockParsingService()
        
        # Simulate pika transport state assertion error
        # Note: pika has a typo in the error message - "_initate" instead of "_initiate"
        # This is the actual error message from pika, reproduced exactly
        transport_error = AssertionError(
            "_AsyncTransportBase._initate_abort() expected non-_STATE_COMPLETED", 4
        )
        service.subscriber.start_consuming.side_effect = transport_error
        
        # Should not raise - should handle gracefully
        start_subscriber_thread(service)
        
        # Verify warning was logged instead of error
        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_logs) > 0
        assert any("Pika transport state assertion" in r.message for r in warning_logs)
        assert any("can be safely ignored" in r.message for r in warning_logs)
    
    def test_reraises_other_assertion_errors(self):
        """Test that non-transport assertion errors are re-raised."""
        service = MockParsingService()
        
        # Simulate a different assertion error (not transport-related)
        other_error = AssertionError("Some other assertion failed")
        service.subscriber.start_consuming.side_effect = other_error
        
        # Should re-raise this error
        with pytest.raises(AssertionError, match="Some other assertion failed"):
            start_subscriber_thread(service)
    
    def test_reraises_other_exceptions(self):
        """Test that non-assertion exceptions are re-raised for fail-fast."""
        service = MockParsingService()
        
        # Simulate a different exception
        other_error = RuntimeError("Connection failed")
        service.subscriber.start_consuming.side_effect = other_error
        
        # Should re-raise this error
        with pytest.raises(RuntimeError, match="Connection failed"):
            start_subscriber_thread(service)
    
    def test_handles_keyboard_interrupt(self, caplog):
        """Test that keyboard interrupt is handled gracefully."""
        import logging
        caplog.set_level(logging.INFO)
        
        service = MockParsingService()
        service.subscriber.start_consuming.side_effect = KeyboardInterrupt()
        
        # Should not raise
        start_subscriber_thread(service)
        
        # Verify info log
        info_logs = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("Subscriber interrupted" in r.message for r in info_logs)
    
    def test_handles_state_completed_in_error_string(self, caplog):
        """Test handling of various transport state error formats."""
        import logging
        caplog.set_level(logging.WARNING)
        
        service = MockParsingService()
        
        # Test with _STATE_COMPLETED in error string
        error = AssertionError("Transport error with _STATE_COMPLETED", 4)
        service.subscriber.start_consuming.side_effect = error
        
        # Should not raise
        start_subscriber_thread(service)
        
        # Verify warning was logged
        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_logs) > 0
        assert any("Pika transport state assertion" in r.message for r in warning_logs)
