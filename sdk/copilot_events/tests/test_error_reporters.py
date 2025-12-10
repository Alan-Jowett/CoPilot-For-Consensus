# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for error reporters."""

import logging
import pytest

from copilot_events import (
    create_error_reporter,
    ErrorReporter,
    ConsoleErrorReporter,
    SilentErrorReporter,
    SentryErrorReporter,
)


class TestErrorReporterFactory:
    """Tests for create_error_reporter factory function."""

    def test_create_console_reporter(self):
        """Test creating a console error reporter."""
        reporter = create_error_reporter(reporter_type="console")
        
        assert isinstance(reporter, ConsoleErrorReporter)
        assert isinstance(reporter, ErrorReporter)

    def test_create_console_reporter_with_logger_name(self):
        """Test creating a console reporter with custom logger name."""
        reporter = create_error_reporter(
            reporter_type="console",
            logger_name="test.logger"
        )
        
        assert isinstance(reporter, ConsoleErrorReporter)
        assert reporter.logger.name == "test.logger"

    def test_create_silent_reporter(self):
        """Test creating a silent error reporter."""
        reporter = create_error_reporter(reporter_type="silent")
        
        assert isinstance(reporter, SilentErrorReporter)
        assert isinstance(reporter, ErrorReporter)

    def test_create_sentry_reporter(self):
        """Test creating a Sentry error reporter (without initializing)."""
        reporter = create_error_reporter(
            reporter_type="sentry",
            dsn=None,  # Don't actually initialize
        )
        
        assert isinstance(reporter, SentryErrorReporter)
        assert isinstance(reporter, ErrorReporter)

    def test_create_unknown_reporter_type(self):
        """Test that unknown reporter type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown reporter type"):
            create_error_reporter(reporter_type="invalid")


class TestConsoleErrorReporter:
    """Tests for ConsoleErrorReporter."""

    def test_initialization(self):
        """Test console reporter initialization."""
        reporter = ConsoleErrorReporter()
        
        assert reporter.logger is not None

    def test_initialization_with_logger_name(self):
        """Test initialization with custom logger name."""
        reporter = ConsoleErrorReporter(logger_name="custom.logger")
        
        assert reporter.logger.name == "custom.logger"

    def test_report_exception(self, caplog):
        """Test reporting an exception."""
        reporter = ConsoleErrorReporter()
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            with caplog.at_level(logging.ERROR):
                reporter.report(e)
            
            assert "Test error" in caplog.text
            assert "ValueError" in caplog.text

    def test_report_exception_with_context(self, caplog):
        """Test reporting an exception with context."""
        reporter = ConsoleErrorReporter()
        
        context = {"user_id": "123", "request_id": "abc"}
        
        try:
            raise RuntimeError("Context test")
        except RuntimeError as e:
            with caplog.at_level(logging.ERROR):
                reporter.report(e, context=context)
            
            assert "Context test" in caplog.text
            assert "user_id=123" in caplog.text
            assert "request_id=abc" in caplog.text

    def test_capture_message_default_level(self, caplog):
        """Test capturing a message with default error level."""
        reporter = ConsoleErrorReporter()
        
        with caplog.at_level(logging.ERROR):
            reporter.capture_message("Test message")
        
        assert "Test message" in caplog.text

    def test_capture_message_info_level(self, caplog):
        """Test capturing a message with info level."""
        reporter = ConsoleErrorReporter()
        
        with caplog.at_level(logging.INFO):
            reporter.capture_message("Info message", level="info")
        
        assert "Info message" in caplog.text

    def test_capture_message_warning_level(self, caplog):
        """Test capturing a message with warning level."""
        reporter = ConsoleErrorReporter()
        
        with caplog.at_level(logging.WARNING):
            reporter.capture_message("Warning message", level="warning")
        
        assert "Warning message" in caplog.text

    def test_capture_message_critical_level(self, caplog):
        """Test capturing a message with critical level."""
        reporter = ConsoleErrorReporter()
        
        with caplog.at_level(logging.CRITICAL):
            reporter.capture_message("Critical message", level="critical")
        
        assert "Critical message" in caplog.text

    def test_capture_message_with_context(self, caplog):
        """Test capturing a message with context."""
        reporter = ConsoleErrorReporter()
        
        context = {"component": "test", "action": "validate"}
        
        with caplog.at_level(logging.ERROR):
            reporter.capture_message("Message with context", context=context)
        
        assert "Message with context" in caplog.text
        assert "component=test" in caplog.text
        assert "action=validate" in caplog.text


class TestSilentErrorReporter:
    """Tests for SilentErrorReporter."""

    def test_initialization(self):
        """Test silent reporter initialization."""
        reporter = SilentErrorReporter()
        
        assert reporter.reported_errors == []
        assert reporter.captured_messages == []

    def test_report_exception(self):
        """Test reporting an exception."""
        reporter = SilentErrorReporter()
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            reporter.report(e)
        
        assert len(reporter.reported_errors) == 1
        assert reporter.reported_errors[0]["error_type"] == "ValueError"
        assert reporter.reported_errors[0]["error_message"] == "Test error"
        assert reporter.reported_errors[0]["context"] == {}

    def test_report_exception_with_context(self):
        """Test reporting an exception with context."""
        reporter = SilentErrorReporter()
        
        context = {"user_id": "456", "trace_id": "xyz"}
        
        try:
            raise RuntimeError("Context error")
        except RuntimeError as e:
            reporter.report(e, context=context)
        
        assert len(reporter.reported_errors) == 1
        assert reporter.reported_errors[0]["context"] == context

    def test_capture_message(self):
        """Test capturing a message."""
        reporter = SilentErrorReporter()
        
        reporter.capture_message("Test message")
        
        assert len(reporter.captured_messages) == 1
        assert reporter.captured_messages[0]["message"] == "Test message"
        assert reporter.captured_messages[0]["level"] == "error"
        assert reporter.captured_messages[0]["context"] == {}

    def test_capture_message_with_level_and_context(self):
        """Test capturing a message with level and context."""
        reporter = SilentErrorReporter()
        
        context = {"component": "api"}
        
        reporter.capture_message("Info message", level="info", context=context)
        
        assert len(reporter.captured_messages) == 1
        assert reporter.captured_messages[0]["level"] == "info"
        assert reporter.captured_messages[0]["context"] == context

    def test_get_errors_all(self):
        """Test getting all errors."""
        reporter = SilentErrorReporter()
        
        try:
            raise ValueError("Error 1")
        except ValueError as e:
            reporter.report(e)
        
        try:
            raise RuntimeError("Error 2")
        except RuntimeError as e:
            reporter.report(e)
        
        errors = reporter.get_errors()
        assert len(errors) == 2

    def test_get_errors_filtered(self):
        """Test getting filtered errors by type."""
        reporter = SilentErrorReporter()
        
        try:
            raise ValueError("Value error 1")
        except ValueError as e:
            reporter.report(e)
        
        try:
            raise RuntimeError("Runtime error")
        except RuntimeError as e:
            reporter.report(e)
        
        try:
            raise ValueError("Value error 2")
        except ValueError as e:
            reporter.report(e)
        
        value_errors = reporter.get_errors(error_type="ValueError")
        assert len(value_errors) == 2
        assert all(e["error_type"] == "ValueError" for e in value_errors)

    def test_get_messages_all(self):
        """Test getting all messages."""
        reporter = SilentErrorReporter()
        
        reporter.capture_message("Message 1", level="info")
        reporter.capture_message("Message 2", level="error")
        
        messages = reporter.get_messages()
        assert len(messages) == 2

    def test_get_messages_filtered(self):
        """Test getting filtered messages by level."""
        reporter = SilentErrorReporter()
        
        reporter.capture_message("Info 1", level="info")
        reporter.capture_message("Error 1", level="error")
        reporter.capture_message("Info 2", level="info")
        
        info_messages = reporter.get_messages(level="info")
        assert len(info_messages) == 2
        assert all(m["level"] == "info" for m in info_messages)

    def test_clear(self):
        """Test clearing stored errors and messages."""
        reporter = SilentErrorReporter()
        
        try:
            raise ValueError("Error")
        except ValueError as e:
            reporter.report(e)
        
        reporter.capture_message("Message")
        
        assert len(reporter.reported_errors) == 1
        assert len(reporter.captured_messages) == 1
        
        reporter.clear()
        
        assert len(reporter.reported_errors) == 0
        assert len(reporter.captured_messages) == 0

    def test_has_errors(self):
        """Test checking if errors have been reported."""
        reporter = SilentErrorReporter()
        
        assert not reporter.has_errors()
        
        try:
            raise ValueError("Error")
        except ValueError as e:
            reporter.report(e)
        
        assert reporter.has_errors()

    def test_has_messages(self):
        """Test checking if messages have been captured."""
        reporter = SilentErrorReporter()
        
        assert not reporter.has_messages()
        
        reporter.capture_message("Message")
        
        assert reporter.has_messages()

    def test_has_messages_with_level(self):
        """Test checking if messages of specific level exist."""
        reporter = SilentErrorReporter()
        
        reporter.capture_message("Info message", level="info")
        
        assert reporter.has_messages(level="info")
        assert not reporter.has_messages(level="error")


class TestSentryErrorReporter:
    """Tests for SentryErrorReporter."""

    def test_initialization_without_dsn(self):
        """Test initialization without DSN doesn't initialize Sentry."""
        reporter = SentryErrorReporter()
        
        assert reporter.dsn is None
        assert reporter.environment == "production"
        assert reporter._initialized is False

    def test_initialization_with_environment(self):
        """Test initialization with custom environment."""
        reporter = SentryErrorReporter(environment="staging")
        
        assert reporter.environment == "staging"

    def test_report_without_initialization_raises_error(self):
        """Test that reporting without initialization raises error."""
        reporter = SentryErrorReporter()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            reporter.report(ValueError("Test"))

    def test_capture_message_without_initialization_raises_error(self):
        """Test that capturing message without initialization raises error."""
        reporter = SentryErrorReporter()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            reporter.capture_message("Test message")

    # Note: Actual Sentry integration tests would require the sentry-sdk
    # package to be installed and a test DSN. These tests verify the
    # basic structure without requiring Sentry to be available.
