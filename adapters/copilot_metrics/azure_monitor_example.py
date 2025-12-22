#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Example demonstrating Azure Monitor metrics collector usage.

This example shows how to configure and use the Azure Monitor metrics
adapter to send metrics to Application Insights.

Prerequisites:
    pip install copilot-metrics[azure]

Environment variables:
    AZURE_MONITOR_CONNECTION_STRING or AZURE_MONITOR_INSTRUMENTATION_KEY
"""

import os
import sys
import time
import logging

# Add parent directory to path for local development
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from copilot_metrics import create_metrics_collector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Example demonstrating Azure Monitor metrics collection."""

    # Check if Azure credentials are configured
    connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
    instrumentation_key = os.getenv("AZURE_MONITOR_INSTRUMENTATION_KEY")

    if not connection_string and not instrumentation_key:
        logger.error(
            "Azure Monitor credentials not configured. "
            "Set AZURE_MONITOR_CONNECTION_STRING or AZURE_MONITOR_INSTRUMENTATION_KEY"
        )
        logger.info("For testing, use NoOp collector instead: METRICS_BACKEND=noop")
        sys.exit(1)

    try:
        # Create Azure Monitor metrics collector
        # This will use AZURE_MONITOR_CONNECTION_STRING from environment
        metrics = create_metrics_collector(backend="azure_monitor")
        logger.info("Azure Monitor metrics collector initialized")

        # Example 1: Counter metric
        logger.info("Recording counter metrics...")
        for i in range(5):
            metrics.increment(
                "example_requests_total",
                value=1.0,
                tags={
                    "service": "example",
                    "method": "GET",
                    "status": "200"
                }
            )
            time.sleep(0.1)

        # Example 2: Histogram/observation metric
        logger.info("Recording histogram metrics...")
        durations = [0.123, 0.456, 0.234, 0.567, 0.345]
        for duration in durations:
            metrics.observe(
                "example_request_duration_seconds",
                value=duration,
                tags={
                    "service": "example",
                    "endpoint": "/api/v1"
                }
            )
            time.sleep(0.1)

        # Example 3: Gauge metric
        logger.info("Recording gauge metrics...")
        queue_depths = [10, 15, 12, 8, 5]
        for depth in queue_depths:
            metrics.gauge(
                "example_queue_depth",
                value=float(depth)
                # Note: tags have limited support for gauges with OpenTelemetry
            )
            time.sleep(0.1)

        logger.info(
            "Metrics recorded successfully. "
            "They will be exported to Azure Monitor within 60 seconds (default export interval)."
        )

        # Graceful shutdown to flush remaining metrics
        logger.info("Shutting down metrics collector...")
        if hasattr(metrics, 'shutdown'):
            metrics.shutdown()

        logger.info(
            "Done! Check your Application Insights resource in Azure Portal to view metrics."
        )
        logger.info(
            "Navigate to: Application Insights -> Metrics -> Custom namespace"
        )

    except ImportError as e:
        logger.error("Azure Monitor packages not installed: %s", e)
        logger.info("Install with: pip install copilot-metrics[azure]")
        sys.exit(1)
    except Exception as e:
        logger.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
