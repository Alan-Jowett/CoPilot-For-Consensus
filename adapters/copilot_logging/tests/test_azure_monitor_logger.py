# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Monitor logger implementation."""

from unittest.mock import MagicMock

import pytest
from copilot_config import load_driver_config

from copilot_logging.factory import create_logger
from copilot_logging.logger import Logger
from copilot_logging.azure_monitor_logger import AzureMonitorLogger


class TestAzureMonitorLoggerFactory:
    """Tests for creating Azure Monitor logger via factory."""

    def test_create_azuremonitor_logger_fallback(self, monkeypatch):
        """Test creating an Azure Monitor logger via factory (fallback mode)."""
        # No Azure Monitor config - should create logger in fallback mode
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_MONITOR_INSTRUMENTATION_KEY", raising=False)

        config = load_driver_config(None, "logger", "azuremonitor", fields={"level": "INFO"})
        logger = create_logger("azuremonitor", config)

        assert isinstance(logger, AzureMonitorLogger)
        assert isinstance(logger, Logger)
        assert logger.level == "INFO"
        assert logger.is_fallback_mode()

    def test_create_azuremonitor_logger_with_name(self, monkeypatch):
        """Test creating an Azure Monitor logger with a custom name."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)

        config = load_driver_config(None, "logger", "azuremonitor", fields={"level": "INFO", "name": "test-service"})
        logger = create_logger("azuremonitor", config)

        assert isinstance(logger, AzureMonitorLogger)
        assert logger.name == "test-service"

    def test_factory_rejects_unknown_logger_type(self):
        """Test that factory rejects unknown logger types including azure_monitor (must be azuremonitor)."""
        config = load_driver_config(None, "logger", "azuremonitor", fields={})
        with pytest.raises(ValueError, match="Unknown logger driver"):
            create_logger("azure_monitor", config)


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
        config = load_driver_config(None, "logger", "azuremonitor", fields={"level": "WARNING", "name": "test-filter-unique"})
        logger = create_logger("azuremonitor", config)

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


class TestAzureMonitorLoggerConfigurationPaths:
    """Tests for various configuration paths and Azure Monitor setup."""

    def test_instrumentation_key_builds_connection_string(self, monkeypatch):
        """Test that instrumentation_key parameter builds a connection string correctly."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporter that captures the connection string
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter) as mock_log_exporter_class:
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                logger = AzureMonitorLogger(level="INFO", instrumentation_key="test-key-12345")
                
                # Verify the connection string was built from instrumentation_key
                mock_log_exporter_class.assert_called_once()
                call_kwargs = mock_log_exporter_class.call_args[1]
                assert 'connection_string' in call_kwargs
                assert call_kwargs['connection_string'] == "InstrumentationKey=test-key-12345"
                assert not logger.is_fallback_mode()

    def test_configure_azure_monitor_value_error(self, monkeypatch):
        """Test fallback when Azure Monitor configuration raises ValueError."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Patch the AzureMonitor exporters so that the log exporter raises ValueError
        with patch(
            "azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter",
            side_effect=ValueError("Invalid connection string"),
        ):
            with patch(
                "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
                return_value=MagicMock(),
            ):
                logger = AzureMonitorLogger(level="INFO", instrumentation_key="bad-key")
                
                # Should fallback due to ValueError
                assert logger.is_fallback_mode()

    def test_configure_azure_monitor_generic_exception(self, monkeypatch):
        """Test fallback when Azure Monitor configuration raises generic Exception."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Patch the AzureMonitor exporters so that the log exporter raises a generic RuntimeError
        with patch(
            "azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter",
            side_effect=RuntimeError("Unexpected error"),
        ):
            with patch(
                "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter",
                return_value=MagicMock(),
            ):
                logger = AzureMonitorLogger(level="INFO", instrumentation_key="test-key")
                
                # Should fallback due to generic exception
                assert logger.is_fallback_mode()

    def test_configure_azure_monitor_success(self, monkeypatch):
        """Test successful Azure Monitor configuration with mocked exporters."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters that don't actually connect to Azure
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                
                # Should NOT be in fallback mode
                assert not logger.is_fallback_mode()
                assert logger._logger_provider is not None

    def test_configure_azure_monitor_with_console_log(self, monkeypatch):
        """Test Azure Monitor configuration with console logging enabled."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters that don't actually connect to Azure
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                logger = AzureMonitorLogger(
                    level="INFO",
                    instrumentation_key="valid-key",
                    console_log=True
                )
                
                # Should NOT be in fallback mode
                assert not logger.is_fallback_mode()
                # Console logging should be enabled
                assert logger.console_log is True

    def test_configure_azure_monitor_with_existing_real_provider(self, monkeypatch):
        """Test Azure Monitor configuration with existing real LoggerProvider."""
        from unittest.mock import patch, MagicMock
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry._logs import set_logger_provider, get_logger_provider
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Capture original provider for cleanup
        original_provider = get_logger_provider()
        
        try:
            # Set up an existing logger provider
            existing_provider = LoggerProvider()
            set_logger_provider(existing_provider)
            
            # Create mock exporters that don't actually connect to Azure
            mock_exporter = MagicMock()
            mock_trace_exporter = MagicMock()
            
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
                with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                    logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                    
                    # Should use existing provider
                    assert not logger.is_fallback_mode()
        finally:
            # Restore original provider to avoid affecting other tests
            set_logger_provider(original_provider)

    def test_configure_azure_monitor_trace_exporter_exception(self, monkeypatch):
        """Test Azure Monitor configuration when trace exporter fails."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporter
        mock_exporter = MagicMock()
        
        # Mock trace exporter to raise exception
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', side_effect=Exception("Trace exporter error")):
                logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                
                # Should still work (trace exporter is optional)
                assert not logger.is_fallback_mode()

    def test_configure_azure_monitor_no_tracer_provider(self, monkeypatch):
        """Test Azure Monitor configuration when no tracer provider exists."""
        from unittest.mock import patch, MagicMock
        from opentelemetry import trace
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        # Mock to return a tracer provider without add_span_processor
        mock_existing_tracer = MagicMock(spec=[])  # No add_span_processor method
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                with patch.object(trace, 'get_tracer_provider', return_value=mock_existing_tracer):
                    logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                    
                    # Should create new tracer provider
                    assert not logger.is_fallback_mode()

    def test_configure_azure_monitor_new_tracer_provider_exception(self, monkeypatch):
        """Test Azure Monitor when creating new tracer provider fails."""
        from unittest.mock import patch, MagicMock
        from opentelemetry import trace
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters
        mock_exporter = MagicMock()
        
        # Mock to return a tracer provider without add_span_processor
        mock_existing_tracer = MagicMock(spec=[])  # No add_span_processor method
        
        # Mock trace exporter to raise exception when creating new provider
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', side_effect=Exception("Trace error")):
                with patch.object(trace, 'get_tracer_provider', return_value=mock_existing_tracer):
                    logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                    
                    # Should still work (trace is optional)
                    assert not logger.is_fallback_mode()



    def test_configure_azure_monitor_get_logger_provider_exception(self, monkeypatch):
        """Test when get_logger_provider raises an exception."""
        from unittest.mock import patch, MagicMock
        from opentelemetry import _logs
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                with patch.object(_logs, 'get_logger_provider', side_effect=RuntimeError("Provider error")):
                    logger = AzureMonitorLogger(level="INFO", instrumentation_key="valid-key")
                    
                    # Should handle exception and create new provider
                    assert not logger.is_fallback_mode()

    def test_configure_azure_monitor_console_log_no_existing_handler(self, monkeypatch):
        """Test console_log=True when no existing console handler exists."""
        from unittest.mock import patch, MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Create mock exporters
        mock_exporter = MagicMock()
        mock_trace_exporter = MagicMock()
        
        with patch('azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter', return_value=mock_exporter):
            with patch('azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter', return_value=mock_trace_exporter):
                # Create logger with unique name to avoid handler reuse
                logger = AzureMonitorLogger(
                    level="INFO",
                    name="unique-console-test",
                    instrumentation_key="valid-key",
                    console_log=True
                )
                
                # Should create new console handler
                assert not logger.is_fallback_mode()
                assert logger.console_log is True
                # Check that console handler was added by counting handlers
                # Should have LoggingHandler (Azure) + StreamHandler (console)
                from opentelemetry.sdk._logs import LoggingHandler
                import logging
                stream_handlers = [
                    h for h in logger._stdlib_logger.handlers
                    if isinstance(h, logging.StreamHandler) and not isinstance(h, LoggingHandler)
                ]
                # Verify at least one console handler was added
                assert len(stream_handlers) >= 1


class TestAzureMonitorLoggerShutdown:
    """Tests for logger shutdown functionality."""

    def test_shutdown_with_provider(self, monkeypatch):
        """Test shutdown with a valid logger provider."""
        from unittest.mock import MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        logger = AzureMonitorLogger(level="INFO")
        
        # Mock the logger provider
        mock_provider = MagicMock()
        mock_provider.shutdown = MagicMock()
        logger._logger_provider = mock_provider
        
        # Call shutdown
        logger.shutdown()
        
        # Verify shutdown was called
        mock_provider.shutdown.assert_called_once()

    def test_shutdown_with_exception_in_provider(self, monkeypatch):
        """Test shutdown when provider.shutdown() raises an exception."""
        from unittest.mock import MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        logger = AzureMonitorLogger(level="INFO")
        
        # Mock the logger provider to raise exception on shutdown
        mock_provider = MagicMock()
        mock_provider.shutdown = MagicMock(side_effect=RuntimeError("Shutdown failed"))
        logger._logger_provider = mock_provider
        
        # Call shutdown - should not raise
        logger.shutdown()

    def test_shutdown_with_exception_in_error_logging(self, monkeypatch):
        """Test shutdown when both provider.shutdown() and error logging fail."""
        from unittest.mock import MagicMock, patch
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        logger = AzureMonitorLogger(level="INFO")
        
        # Mock the logger provider to raise exception on shutdown
        mock_provider = MagicMock()
        mock_provider.shutdown = MagicMock(side_effect=RuntimeError("Shutdown failed"))
        logger._logger_provider = mock_provider
        
        # Mock logging.getLogger in the correct namespace to also fail
        with patch('copilot_logging.azure_monitor_logger.logging.getLogger') as mock_get_logger:
            mock_error = MagicMock(side_effect=Exception("Logging failed"))
            mock_get_logger.return_value.error = mock_error
            
            # Call shutdown - should not raise
            logger.shutdown()

    def test_shutdown_without_provider(self, monkeypatch):
        """Test shutdown when no logger provider exists."""
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        logger = AzureMonitorLogger(level="INFO")
        logger._logger_provider = None
        
        # Call shutdown - should not raise
        logger.shutdown()

    def test_shutdown_with_provider_without_shutdown_method(self, monkeypatch):
        """Test shutdown when provider doesn't have shutdown method."""
        from unittest.mock import MagicMock
        
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        logger = AzureMonitorLogger(level="INFO")
        
        # Mock provider without shutdown method
        mock_provider = MagicMock(spec=[])  # No methods
        logger._logger_provider = mock_provider
        
        # Call shutdown - should not raise
        logger.shutdown()


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
