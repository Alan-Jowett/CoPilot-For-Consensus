# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Monitor logger implementation with Application Insights integration."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .logger import Logger


class AzureMonitorLogger(Logger):
    """Logger that sends structured logs to Azure Monitor / Application Insights.
    
    This logger integrates with Azure Monitor using the azure-monitor-opentelemetry-exporter
    SDK to provide cloud-native observability for production deployments.
    
    Features:
    - Structured logging with custom dimensions
    - Support for correlation IDs and trace context
    - Automatic fallback to console logging if Azure Monitor is unavailable
    - Configurable via environment variables
    
    Environment Variables:
    - AZURE_MONITOR_CONNECTION_STRING: Connection string for Azure Monitor
      (required for Azure Monitor logging, falls back to console if not set)
    - AZURE_MONITOR_INSTRUMENTATION_KEY: Legacy instrumentation key (deprecated, use connection string)
    - AZURE_MONITOR_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR)
    - AZURE_MONITOR_LOG_NAME: Logger name for identification
    
    Example:
        >>> # With Azure Monitor configured
        >>> os.environ['AZURE_MONITOR_CONNECTION_STRING'] = 'InstrumentationKey=xxx;...'
        >>> logger = AzureMonitorLogger(level="INFO", name="my-service")
        >>> logger.info("Service started", version="1.0.0")
        >>> 
        >>> # Fallback to console if not configured
        >>> logger = AzureMonitorLogger(level="INFO", name="my-service")
        >>> logger.info("Service started")  # Logs to console with warning
    """

    def __init__(self, level: str = "INFO", name: Optional[str] = None):
        """Initialize Azure Monitor logger.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            name: Optional logger name for identification
        """
        self.level = level.upper()
        self.name = name or "copilot"
        self._fallback_mode = False
        
        # Map string levels to Python logging levels
        self._level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        
        # Validate level
        if self.level not in self._level_map:
            raise ValueError(f"Invalid log level: {level}. Must be one of {list(self._level_map.keys())}")
        
        # Get connection string from environment
        connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
        instrumentation_key = os.getenv("AZURE_MONITOR_INSTRUMENTATION_KEY")
        
        # Configure Azure Monitor or fallback
        if connection_string or instrumentation_key:
            self._configure_azure_monitor(connection_string, instrumentation_key)
        else:
            self._configure_fallback()
    
    def _configure_azure_monitor(
        self, 
        connection_string: Optional[str], 
        instrumentation_key: Optional[str]
    ) -> None:
        """Configure Azure Monitor exporter.
        
        Args:
            connection_string: Azure Monitor connection string
            instrumentation_key: Azure Monitor instrumentation key (legacy)
        """
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            
            # Build connection string
            if connection_string:
                conn_str = connection_string
            elif instrumentation_key:
                # Legacy format - construct connection string from instrumentation key
                conn_str = f"InstrumentationKey={instrumentation_key}"
            else:
                raise ValueError("Either connection_string or instrumentation_key must be provided")
            
            # Configure Azure Monitor log exporter
            exporter = AzureMonitorLogExporter(connection_string=conn_str)
            
            # Set up OpenTelemetry logger provider
            logger_provider = LoggerProvider()
            set_logger_provider(logger_provider)
            
            # Add batch processor for efficient log transmission
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(exporter)
            )
            
            # Set up trace provider for distributed tracing
            trace.set_tracer_provider(TracerProvider())
            trace.get_tracer_provider().add_span_processor(  # type: ignore
                BatchSpanProcessor(
                    AzureMonitorLogExporter(connection_string=conn_str)
                )
            )
            
            # Create logging handler
            handler = LoggingHandler()
            
            # Configure Python logging to use Azure Monitor
            self._stdlib_logger = logging.getLogger(self.name)
            self._stdlib_logger.setLevel(self._level_map[self.level])
            self._stdlib_logger.addHandler(handler)
            
            # Add console handler for local debugging (optional)
            if os.getenv("AZURE_MONITOR_CONSOLE_LOG", "false").lower() == "true":
                console_handler = logging.StreamHandler()
                console_handler.setLevel(self._level_map[self.level])
                formatter = logging.Formatter(
                    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"logger": "%(name)s", "message": "%(message)s"}'
                )
                console_handler.setFormatter(formatter)
                self._stdlib_logger.addHandler(console_handler)
            
            self._fallback_mode = False
            
        except ImportError as e:
            # Azure Monitor SDK not available, fallback to console
            print(
                f"WARNING: Azure Monitor SDK not available ({e}). "
                "Install with: pip install azure-monitor-opentelemetry-exporter. "
                "Falling back to console logging.",
                flush=True
            )
            self._configure_fallback()
        except Exception as e:
            # Configuration failed, fallback to console
            print(
                f"WARNING: Failed to configure Azure Monitor ({e}). "
                "Falling back to console logging.",
                flush=True
            )
            self._configure_fallback()
    
    def _configure_fallback(self) -> None:
        """Configure fallback console logging when Azure Monitor is unavailable."""
        self._fallback_mode = True
        self._stdlib_logger = logging.getLogger(self.name)
        self._stdlib_logger.setLevel(self._level_map[self.level])
        
        # Add console handler with JSON formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._level_map[self.level])
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s", "fallback": true}'
        )
        console_handler.setFormatter(formatter)
        self._stdlib_logger.addHandler(console_handler)
        
        # Log warning about fallback mode
        self._stdlib_logger.warning(
            "Azure Monitor not configured - using console fallback. "
            "Set AZURE_MONITOR_CONNECTION_STRING environment variable for Azure Monitor logging."
        )
    
    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal method to format and send log message.
        
        Args:
            level: Log level
            message: The log message
            **kwargs: Additional structured data to log as custom dimensions
        """
        # Check if we should log at this level
        if self._level_map[level] < self._level_map[self.level]:
            return
        
        # Extract special fields
        exc_info = kwargs.pop("exc_info", None)
        correlation_id = kwargs.pop("correlation_id", None)
        trace_id = kwargs.pop("trace_id", None)
        
        # Build extra context for structured logging
        extra = {}
        if kwargs:
            # Azure Monitor supports custom dimensions
            extra["custom_dimensions"] = kwargs
        
        if correlation_id:
            extra["correlation_id"] = correlation_id
        
        if trace_id:
            extra["trace_id"] = trace_id
        
        # Add timestamp in ISO format
        extra["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Log via stdlib logger (which forwards to Azure Monitor or console)
        self._stdlib_logger.log(
            self._level_map[level],
            message,
            exc_info=exc_info,
            extra=extra
        )
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info-level message.
        
        Args:
            message: The log message
            **kwargs: Additional structured data to log
                - correlation_id: Optional correlation ID for distributed tracing
                - trace_id: Optional trace ID for distributed tracing
                - Any other fields will be logged as custom dimensions
        """
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning-level message.
        
        Args:
            message: The log message
            **kwargs: Additional structured data to log
                - correlation_id: Optional correlation ID for distributed tracing
                - trace_id: Optional trace ID for distributed tracing
                - Any other fields will be logged as custom dimensions
        """
        self._log("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message.
        
        Args:
            message: The log message
            **kwargs: Additional structured data to log
                - correlation_id: Optional correlation ID for distributed tracing
                - trace_id: Optional trace ID for distributed tracing
                - exc_info: Optional exception info (bool or tuple) for exception logging
                - Any other fields will be logged as custom dimensions
        """
        self._log("ERROR", message, **kwargs)
    
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message with exception context.
        
        Args:
            message: The log message
            **kwargs: Additional structured data to log
        """
        kwargs.setdefault("exc_info", True)
        self._log("ERROR", message, **kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message.
        
        Args:
            message: The log message
            **kwargs: Additional structured data to log
                - correlation_id: Optional correlation ID for distributed tracing
                - trace_id: Optional trace ID for distributed tracing
                - Any other fields will be logged as custom dimensions
        """
        self._log("DEBUG", message, **kwargs)
    
    def is_fallback_mode(self) -> bool:
        """Check if logger is in fallback mode (console logging).
        
        Returns:
            True if using fallback console logging, False if using Azure Monitor
        """
        return self._fallback_mode
