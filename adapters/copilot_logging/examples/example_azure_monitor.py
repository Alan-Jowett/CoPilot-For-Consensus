#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the Azure Monitor logger.

This script demonstrates how to use the Azure Monitor logger for
cloud-native observability with distributed tracing support.
"""

from copilot_logging import create_logger


def main():
    """Demonstrate Azure Monitor logging functionality."""
    
    print("=" * 60)
    print("Azure Monitor Logger Examples")
    print("=" * 60)
    print()
    
    # Example 1: Basic Azure Monitor logging (fallback mode)
    print("Example 1: Azure Monitor Logger (Fallback Mode)")
    print("-" * 60)
    print("Note: Since AZURE_MONITOR_CONNECTION_STRING is not set,")
    print("the logger will automatically fallback to console logging.")
    print()
    
    logger = create_logger(logger_type="azuremonitor", level="INFO", name="example-app")
    
    print(f"Logger type: {type(logger).__name__}")
    print(f"Fallback mode: {logger.is_fallback_mode()}")
    print()
    
    logger.info("Application started", version="1.0.0", environment="development")
    logger.info("Processing request", request_id="req-123", user_id=456)
    logger.warning("High memory usage detected", usage_percent=85, threshold=80)
    logger.error("Database connection failed", error="timeout", retry_count=3)
    print()
    
    # Example 2: Logging with correlation IDs for distributed tracing
    print("Example 2: Distributed Tracing with Correlation IDs")
    print("-" * 60)
    
    correlation_id = "corr-abc-123"
    trace_id = "trace-xyz-789"
    
    logger.info(
        "Request received",
        correlation_id=correlation_id,
        trace_id=trace_id,
        method="POST",
        path="/api/users"
    )
    
    logger.info(
        "Database query executed",
        correlation_id=correlation_id,
        trace_id=trace_id,
        query_type="INSERT",
        execution_time_ms=45.3
    )
    
    logger.info(
        "Request completed",
        correlation_id=correlation_id,
        trace_id=trace_id,
        status_code=201,
        total_duration_ms=123.45
    )
    print()
    
    # Example 3: Rich structured logging
    print("Example 3: Rich Structured Logging")
    print("-" * 60)
    
    logger.info(
        "User authentication successful",
        user_id=12345,
        username="alice",
        ip_address="192.168.1.100",
        authentication_method="oauth2",
        session_id="sess-abc-123",
        correlation_id="corr-def-456"
    )
    
    logger.info(
        "Payment processed",
        transaction_id="txn-123-456",
        amount=99.99,
        currency="USD",
        payment_method="credit_card",
        customer_id=789,
        correlation_id="corr-def-456"
    )
    print()
    
    # Example 4: Exception logging
    print("Example 4: Exception Logging")
    print("-" * 60)
    
    try:
        # Simulate an error
        1 / 0
    except ZeroDivisionError:
        logger.exception(
            "Division by zero error",
            operation="calculate_ratio",
            numerator=1,
            denominator=0
        )
    print()
    
    # Example 5: Configuration with Azure Monitor
    print("Example 5: Configuration for Azure Monitor")
    print("-" * 60)
    print("To use Azure Monitor in production, set these environment variables:")
    print()
    print("  export AZURE_MONITOR_CONNECTION_STRING='InstrumentationKey=xxx;IngestionEndpoint=https://...'")
    print("  export LOG_TYPE=azuremonitor")
    print("  export LOG_LEVEL=INFO")
    print("  export LOG_NAME=my-service")
    print()
    print("Then create logger as usual:")
    print("  logger = create_logger()")
    print()
    print("The logger will automatically detect Azure Monitor configuration")
    print("and send logs to Application Insights.")
    print()
    
    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print()
    print("Installation:")
    print("  pip install copilot-logging[azuremonitor]")
    print()
    print("See README.md for more details on Azure Monitor setup.")


if __name__ == "__main__":
    main()
