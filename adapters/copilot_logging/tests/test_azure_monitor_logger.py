# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Monitor logger implementation."""

from unittest.mock import MagicMock

import pytest
from copilot_logging import (
    AzureMonitorLogger,
    Logger,
    create_logger,
)


class TestAzureMonitorLoggerFactory:
    """Tests for creating Azure Monitor logger via factory."""

    def test_create_azuremonitor_logger_fallback(self, monkeypatch):
        """Test creating an Azure Monitor logger via factory (fallback mode)."""
        # No Azure Monitor config - should create logger in fallback mode
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        logger = create_logger(logger_type="azuremonitor", level="INFO")

        assert isinstance(logger, AzureMonitorLogger)
        assert isinstance(logger, Logger)
        assert logger.level == "INFO"
        assert logger.is_fallback_mode()

    def test_create_azuremonitor_logger_with_name(self, monkeypatch):
        """Test creating an Azure Monitor logger with a custom name."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = create_logger(logger_type="azuremonitor", level="INFO", name="test-service")

        assert isinstance(logger, AzureMonitorLogger)
        assert logger.name == "test-service"

    def test_factory_rejects_unknown_logger_type(self):
        """Test that factory rejects unknown logger types including azure_monitor (must be azuremonitor)."""
        with pytest.raises(ValueError, match="Unknown logger_type"):
            create_logger(logger_type="azure_monitor", level="INFO")


class TestAzureMonitorLoggerInitialization:
    """Tests for AzureMonitorLogger initialization."""

    def test_initialization_fallback_when_no_config(self, monkeypatch):
        """Test fallback to console when no Azure Monitor config is provided."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        logger = AzureMonitorLogger(level="INFO", name="test-service")

        assert logger.level == "INFO"
        assert logger.name == "test-service"
        assert logger.is_fallback_mode()

    def test_initialization_fallback_when_sdk_missing(self, monkeypatch):
        """Test fallback to console when Azure Monitor SDK is not installed."""
        monkeypatch.setenv("AZURE_MONITOR_CONNECTION_STRING", "InstrumentationKey=test-key")

        # Since SDK is not actually installed, should fallback
        logger = AzureMonitorLogger(level="INFO", name="test-service")

        # Will be in fallback mode since Azure Monitor SDK is not actually installed
        assert logger.is_fallback_mode()

    def test_default_values(self, monkeypatch):
        """Test default initialization values."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        logger = AzureMonitorLogger()

        assert logger.level == "INFO"
        assert logger.name == "copilot"
        assert logger.is_fallback_mode()

    def test_invalid_log_level(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            AzureMonitorLogger(level="INVALID")


class TestAzureMonitorLoggerLogging:
    """Tests for AzureMonitorLogger logging functionality."""

    @pytest.fixture
    def fallback_logger(self, monkeypatch):
        """Create a fallback logger for testing."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        logger = AzureMonitorLogger(level="INFO", name="test")
        # Mock the stdlib logger to capture calls
        logger._stdlib_logger = MagicMock()
        return logger

    def test_info_logging(self, fallback_logger):
        """Test logging info-level messages."""
        fallback_logger.info("Test info message")

        # Verify stdlib logger was called with correct level
        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args
        assert call_args[0][0] == 20  # INFO level
        assert call_args[0][1] == "Test info message"

    def test_warning_logging(self, fallback_logger):
        """Test logging warning-level messages."""
        fallback_logger.warning("Test warning message")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args
        assert call_args[0][0] == 30  # WARNING level
        assert call_args[0][1] == "Test warning message"

    def test_error_logging(self, fallback_logger):
        """Test logging error-level messages."""
        fallback_logger.error("Test error message")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args
        assert call_args[0][0] == 40  # ERROR level
        assert call_args[0][1] == "Test error message"

    def test_debug_logging(self, monkeypatch):
        """Test logging debug-level messages."""
        # Ensure we are in fallback mode (no Azure Monitor configuration).
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        # Create a dedicated logger instance configured for DEBUG level
        debug_logger = AzureMonitorLogger(level="DEBUG", name="test-debug")
        debug_logger._stdlib_logger = MagicMock()
        debug_logger.debug("Test debug message")

        debug_logger._stdlib_logger.log.assert_called_once()
        call_args = debug_logger._stdlib_logger.log.call_args
        assert call_args[0][0] == 10  # DEBUG level
        assert call_args[0][1] == "Test debug message"

    def test_logging_with_custom_dimensions(self, fallback_logger):
        """Test logging with custom dimensions (structured data)."""
        fallback_logger.info("User action", user_id=123, action="login", ip="192.168.1.1")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args

        # Check that custom dimensions are in extra
        extra = call_args[1]['extra']
        assert 'custom_dimensions' in extra
        assert extra['custom_dimensions']['user_id'] == 123
        assert extra['custom_dimensions']['action'] == "login"
        assert extra['custom_dimensions']['ip'] == "192.168.1.1"

    def test_logging_with_correlation_id(self, fallback_logger):
        """Test logging with correlation ID for distributed tracing."""
        fallback_logger.info("Request processed", correlation_id="corr-123", request_id="req-456")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args

        extra = call_args[1]['extra']
        assert extra['correlation_id'] == "corr-123"
        # request_id should be in custom_dimensions, not as a special field
        assert extra['custom_dimensions']['request_id'] == "req-456"

    def test_logging_with_trace_id(self, fallback_logger):
        """Test logging with trace ID for distributed tracing."""
        fallback_logger.info("Request started", trace_id="trace-789")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args

        extra = call_args[1]['extra']
        assert extra['trace_id'] == "trace-789"

    def test_exception_logging(self, fallback_logger):
        """Test logging with exception information."""
        fallback_logger.exception("An error occurred", error_code=500)

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args

        # Check exc_info is set
        assert call_args[1]['exc_info'] is True
        assert call_args[0][0] == 40  # ERROR level

    def test_log_level_filtering(self, monkeypatch):
        """Test that logs below the configured level are not sent."""
        # Ensure we are in fallback mode (no Azure Monitor configuration).
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        # Create a fresh logger configured at WARNING level so level filtering
        # is set up through the normal construction path.
        logger = create_logger(logger_type="azuremonitor", level="WARNING", name="test-filter-unique")

        # Attach a mock stdlib logger to observe which messages are emitted.
        logger._stdlib_logger = MagicMock()

        logger.debug("Debug message")  # Should not be logged
        logger.info("Info message")    # Should not be logged

        # No calls should have been made for below-threshold messages.
        logger._stdlib_logger.log.assert_not_called()

        logger.warning("Warning message")  # Should be logged

        # Now one call should have been made.
        logger._stdlib_logger.log.assert_called_once()

    def test_multiple_logs(self, fallback_logger):
        """Test multiple log messages."""
        fallback_logger.info("Message 1")
        fallback_logger.warning("Message 2")
        fallback_logger.error("Message 3")

        assert fallback_logger._stdlib_logger.log.call_count == 3

    def test_fallback_mode_logging(self, fallback_logger):
        """Test that fallback mode still logs messages."""
        fallback_logger.info("Fallback test message")

        fallback_logger._stdlib_logger.log.assert_called_once()
        call_args = fallback_logger._stdlib_logger.log.call_args
        assert call_args[0][1] == "Fallback test message"


class TestAzureMonitorLoggerIntegration:
    """Integration tests for Azure Monitor logger (without actual Azure SDK)."""

    def test_full_logging_flow_with_fallback(self, monkeypatch):
        """Test full logging flow with fallback to console."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        logger = AzureMonitorLogger(level="INFO", name="fallback-test")

        # Verify in fallback mode
        assert logger.is_fallback_mode()

        # Should still be able to log without errors
        logger.info("Service started")
        logger.warning("Warning message")
        logger.error("Error message")


class TestAzureMonitorLoggerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_message(self, monkeypatch):
        """Test logging with an empty message."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")

        # Should not raise an exception
        logger.info("")

    def test_none_in_custom_dimensions(self, monkeypatch):
        """Test that None values in custom dimensions are handled."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")
        logger._stdlib_logger = MagicMock()

        logger.info("Test message", value=None, user_id=123)

        # Should not raise an exception
        logger._stdlib_logger.log.assert_called_once()

    def test_complex_data_types_in_custom_dimensions(self, monkeypatch):
        """Test logging with complex data types (lists, dicts) in custom dimensions."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")
        logger._stdlib_logger = MagicMock()

        logger.info(
            "Complex data",
            items=[1, 2, 3],
            metadata={"key": "value", "count": 10},
            user={"id": 123, "name": "Alice"}
        )

        logger._stdlib_logger.log.assert_called_once()
        call_args = logger._stdlib_logger.log.call_args
        extra = call_args[1]['extra']
        assert extra['custom_dimensions']['items'] == [1, 2, 3]
        assert extra['custom_dimensions']['metadata'] == {"key": "value", "count": 10}

    def test_unicode_in_messages(self, monkeypatch):
        """Test logging with Unicode characters."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")
        logger._stdlib_logger = MagicMock()

        logger.info("Unicode message: 你好世界 🌍", emoji="✅")

        logger._stdlib_logger.log.assert_called_once()

    def test_very_long_message(self, monkeypatch):
        """Test logging with a very long message."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")
        logger._stdlib_logger = MagicMock()

        long_message = "A" * 10000  # 10k characters
        logger.info(long_message)

        logger._stdlib_logger.log.assert_called_once()

    def test_shutdown_method(self, monkeypatch):
        """Test that shutdown method works correctly."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        logger = AzureMonitorLogger(level="INFO")

        # Should not raise an exception
        logger.shutdown()

        # Shutdown should be idempotent
        logger.shutdown()

    def test_duplicate_handler_prevention(self, monkeypatch):
        """Test that creating multiple logger instances doesn't create duplicate handlers."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        # Create first logger
        logger1 = AzureMonitorLogger(level="INFO", name="test-dup")
        initial_handler_count = len(logger1._stdlib_logger.handlers)

        # Create second logger with same name
        logger2 = AzureMonitorLogger(level="INFO", name="test-dup")
        final_handler_count = len(logger2._stdlib_logger.handlers)

        # Should have same number of handlers (no duplicates)
        assert final_handler_count == initial_handler_count
