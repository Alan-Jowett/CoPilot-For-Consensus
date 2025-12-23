#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the copilot_logging module.

This script demonstrates how to use the logging abstraction layer
for structured logging across microservices.
"""

import os
from copilot_logging import create_logger


def main():
    """Demonstrate logging functionality."""

    print("=" * 60)
    print("Copilot Logging Examples")
    print("=" * 60)
    print()

    # Example 1: Basic stdout logging
    print("Example 1: Basic StdoutLogger with INFO level")
    print("-" * 60)
    logger = create_logger(logger_type="stdout", level="INFO", name="example-service")

    logger.info("Service started successfully")
    logger.info("Processing request", request_id="req-123", user_id=456)
    logger.warning("Rate limit approaching", current=95, limit=100)
    logger.error("Failed to connect", error="Connection timeout", host="localhost")
    logger.debug("This debug message won't appear (below INFO level)")
    print()

    # Example 2: Debug level logging
    print("Example 2: StdoutLogger with DEBUG level")
    print("-" * 60)
    debug_logger = create_logger(logger_type="stdout", level="DEBUG", name="debug-service")

    debug_logger.debug("Now debug messages are visible")
    debug_logger.info("Processing item", item_id=789, status="active")
    print()

    # Example 3: Silent logger for testing
    print("Example 3: SilentLogger for testing")
    print("-" * 60)
    test_logger = create_logger(logger_type="silent", level="INFO", name="test-service")

    test_logger.info("Test message 1")
    test_logger.warning("Test warning")
    test_logger.error("Test error", code=500)

    print(f"Total logs captured: {len(test_logger.logs)}")
    print(f"Has 'Test message 1': {test_logger.has_log('Test message 1')}")
    print(f"Warning logs: {len(test_logger.get_logs(level='WARNING'))}")

    print("\nLogged messages:")
    for log in test_logger.logs:
        extra = f" ({log.get('extra', {})})" if 'extra' in log else ""
        print(f"  [{log['level']}] {log['message']}{extra}")
    print()

    # Example 4: Explicit configuration (no environment variables)
    print("Example 4: Explicitly configured logger")
    print("-" * 60)

    explicit_logger = create_logger(logger_type="stdout", level="WARNING", name="explicit-service")
    print(f"Logger configured explicitly: type={type(explicit_logger).__name__}, "
          f"level={explicit_logger.level}, name={explicit_logger.name}")

    explicit_logger.info("This INFO message won't appear (below WARNING)")
    explicit_logger.warning("This WARNING appears", reason="configured for WARNING level")
    explicit_logger.error("This ERROR also appears")
    print()

    # Example 5: Structured logging with rich context
    print("Example 5: Rich structured logging")
    print("-" * 60)
    app_logger = create_logger(logger_type="stdout", level="INFO", name="app")

    app_logger.info(
        "User authentication successful",
        user_id=12345,
        username="alice",
        ip_address="192.168.1.100",
        authentication_method="oauth2",
        session_id="sess-abc-123",
        timestamp="2025-12-10T15:30:00Z"
    )

    app_logger.info(
        "Database query executed",
        query_type="SELECT",
        table="users",
        execution_time_ms=45.3,
        rows_returned=10,
        cache_hit=False
    )
    print()

    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
