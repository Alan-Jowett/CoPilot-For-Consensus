# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event handler decorator."""

from unittest.mock import Mock

from copilot_service_base.event_handler import safe_event_handler


class TestSafeEventHandler:
    """Tests for safe_event_handler decorator."""
    
    def test_successful_event_handling(self):
        """Test that decorator allows successful event handling."""
        error_reporter = Mock()
        
        class TestService:
            def __init__(self):
                self.error_reporter = error_reporter
                self.processed = []
            
            @safe_event_handler("TestEvent")
            def handle_event(self, event):
                self.processed.append(event)
                return "success"
        
        service = TestService()
        result = service.handle_event({"data": "test"})
        
        assert result == "success"
        assert service.processed == [{"data": "test"}]
        assert error_reporter.report.call_count == 0
    
    def test_error_handling_with_reporter(self):
        """Test that errors are caught, reported, and re-raised by default."""
        import pytest
        error_reporter = Mock()
        
        class TestService:
            def __init__(self):
                self.error_reporter = error_reporter
            
            @safe_event_handler("TestEvent")
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with pytest.raises(ValueError, match="test error"):
            service.handle_event({"data": "test"})
        
        assert error_reporter.report.call_count == 1
        
        # Check error was reported with correct context
        call_args = error_reporter.report.call_args
        assert isinstance(call_args[0][0], ValueError)
        assert call_args[1]["context"]["event"] == {"data": "test"}
        assert call_args[1]["context"]["event_name"] == "TestEvent"
    
    def test_error_handling_with_explicit_reporter(self):
        """Test that explicit error reporter parameter works."""
        import pytest
        error_reporter = Mock()
        
        class TestService:
            @safe_event_handler("TestEvent", error_reporter=error_reporter)
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with pytest.raises(ValueError):
            service.handle_event({"data": "test"})
        
        assert error_reporter.report.call_count == 1
    
    def test_error_handling_without_reporter(self):
        """Test that errors are caught and re-raised even without error reporter."""
        import pytest
        
        class TestService:
            @safe_event_handler("TestEvent")
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with pytest.raises(ValueError, match="test error"):
            service.handle_event({"data": "test"})
    
    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""
        class TestService:
            @safe_event_handler("TestEvent")
            def handle_event(self, event):
                """Handle a test event."""
                pass
        
        service = TestService()
        assert service.handle_event.__name__ == "handle_event"
        assert service.handle_event.__doc__ == "Handle a test event."
    
    def test_custom_event_name_in_logs(self, caplog):
        """Test that custom event name appears in error logs."""
        import logging
        import pytest
        
        class TestService:
            @safe_event_handler("CustomEvent")
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):  # Default behavior is to re-raise
                service.handle_event({"data": "test"})
        
        # Check that event name appears in log
        assert "CustomEvent" in caplog.text
        assert "test error" in caplog.text
    
    def test_reraise_default_behavior(self):
        """Test that exceptions are re-raised by default."""
        import pytest
        
        class TestService:
            @safe_event_handler("TestEvent")
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with pytest.raises(ValueError, match="test error"):
            service.handle_event({"data": "test"})
    
    def test_reraise_disabled(self):
        """Test that exceptions can be swallowed with reraise=False."""
        class TestService:
            @safe_event_handler("TestEvent", reraise=False)
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        # Should not raise
        result = service.handle_event({"data": "test"})
        assert result is None
    
    def test_on_error_callback(self):
        """Test that on_error callback is called when error occurs."""
        import pytest
        error_callback = Mock()
        
        class TestService:
            @safe_event_handler("TestEvent", on_error=error_callback)
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        
        with pytest.raises(ValueError):  # Still re-raises by default
            service.handle_event({"data": "test"})
        
        # Check that callback was called
        assert error_callback.call_count == 1
        
        # Check callback arguments (self, error, event)
        call_args = error_callback.call_args[0]
        assert call_args[0] is service
        assert isinstance(call_args[1], ValueError)
        assert call_args[2] == {"data": "test"}
    
    def test_on_error_with_state_modification(self):
        """Test that on_error callback can modify service state."""
        import pytest
        
        class TestService:
            def __init__(self):
                self.failure_count = 0
            
            @safe_event_handler(
                "TestEvent",
                on_error=lambda self, e, evt: setattr(self, 'failure_count', self.failure_count + 1)
            )
            def handle_event(self, event):
                raise ValueError("test error")
        
        service = TestService()
        assert service.failure_count == 0
        
        with pytest.raises(ValueError):
            service.handle_event({"data": "test"})
        assert service.failure_count == 1
        
        with pytest.raises(ValueError):
            service.handle_event({"data": "test"})
        assert service.failure_count == 2
