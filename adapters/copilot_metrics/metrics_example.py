#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example demonstrating metrics collection in a microservice.

This example shows how to integrate metrics collection into a service
for observability and monitoring.
"""

import logging
import random
import time
from typing import Any

from copilot_metrics import MetricsCollector, create_metrics_collector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExampleService:
    """Example service demonstrating metrics collection patterns."""

    def __init__(self, metrics: MetricsCollector = None):
        """Initialize the service with metrics collection.

        Args:
            metrics: MetricsCollector instance (auto-creates if None)
        """
        self.metrics = metrics or create_metrics_collector()
        logger.info(f"Service initialized with {type(self.metrics).__name__}")

        # Track service startup
        self.metrics.increment("service_starts_total")

        # Track active items count
        self._active_items = 0

    def process_item(self, item_id: str, item_type: str) -> dict[str, Any]:
        """Process an item and emit metrics.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item (e.g., "email", "document", "thread")

        Returns:
            Processing result dictionary
        """
        logger.info(f"Processing {item_type} item: {item_id}")

        # Track that we started processing
        self.metrics.increment("items_started_total", tags={
            "item_type": item_type
        })

        # Track active processing with a gauge - increment count
        self._active_items += 1
        self.metrics.gauge("active_items", float(self._active_items))

        try:
            # Measure processing time
            start_time = time.time()

            # Simulate processing (would be real work in production)
            result = self._simulate_processing(item_id, item_type)

            duration = time.time() - start_time

            # Record success metrics
            self.metrics.increment("items_processed_total", tags={
                "item_type": item_type,
                "status": "success"
            })

            self.metrics.observe("processing_duration_seconds", duration, tags={
                "item_type": item_type,
                "status": "success"
            })

            # Track output size if available
            if "size_bytes" in result:
                self.metrics.observe("item_size_bytes", result["size_bytes"], tags={
                    "item_type": item_type
                })

            logger.info(f"Successfully processed {item_id} in {duration:.3f}s")
            return result

        except Exception as e:
            duration = time.time() - start_time

            # Track failures
            self.metrics.increment("items_processed_total", tags={
                "item_type": item_type,
                "status": "error"
            })

            self.metrics.increment("processing_errors_total", tags={
                "item_type": item_type,
                "error_type": type(e).__name__
            })

            self.metrics.observe("processing_duration_seconds", duration, tags={
                "item_type": item_type,
                "status": "error"
            })

            logger.error(f"Failed to process {item_id}: {e}")
            raise

        finally:
            # Always decrement active items gauge
            self._active_items -= 1
            self.metrics.gauge("active_items", float(self._active_items))

    def _simulate_processing(self, item_id: str, item_type: str) -> dict[str, Any]:
        """Simulate processing work (replace with real logic in production).

        Args:
            item_id: Item identifier
            item_type: Type of item

        Returns:
            Processing result

        Raises:
            ValueError: Randomly to simulate errors
        """
        # Simulate variable processing time
        time.sleep(random.uniform(0.05, 0.2))

        # Simulate occasional failures (10% of the time)
        if random.random() < 0.1:
            raise ValueError(f"Simulated error processing {item_id}")

        return {
            "item_id": item_id,
            "item_type": item_type,
            "processed": True,
            "size_bytes": random.randint(1000, 10000),
            "timestamp": time.time()
        }

    def get_queue_depth(self) -> int:
        """Get current queue depth (simulated).

        Returns:
            Current queue depth
        """
        # In production, this would query a real queue
        depth = random.randint(0, 100)

        # Update gauge metric
        self.metrics.gauge("queue_depth", float(depth))

        return depth

    def handle_request(self, method: str, endpoint: str) -> dict[str, Any]:
        """Handle an HTTP request and track metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Request endpoint

        Returns:
            Response data
        """
        # Track request received
        self.metrics.increment("http_requests_total", tags={
            "method": method,
            "endpoint": endpoint
        })

        start_time = time.time()

        try:
            # Simulate request processing
            time.sleep(random.uniform(0.01, 0.1))

            # Simulate occasional errors
            if random.random() < 0.05:
                raise RuntimeError("Simulated server error")

            status_code = 200
            duration = time.time() - start_time

            # Track response metrics
            self.metrics.increment("http_responses_total", tags={
                "method": method,
                "endpoint": endpoint,
                "status": str(status_code)
            })

            self.metrics.observe("http_request_duration_seconds", duration, tags={
                "method": method,
                "endpoint": endpoint
            })

            return {
                "status": status_code,
                "duration": duration,
                "data": {"message": "Success"}
            }

        except Exception as e:
            duration = time.time() - start_time

            # Track error metrics
            self.metrics.increment("http_responses_total", tags={
                "method": method,
                "endpoint": endpoint,
                "status": "500"
            })

            self.metrics.observe("http_request_duration_seconds", duration, tags={
                "method": method,
                "endpoint": endpoint
            })

            logger.error(f"Request failed: {method} {endpoint}: {e}")
            return {
                "status": 500,
                "duration": duration,
                "error": str(e)
            }


def main():
    """Run example demonstrating metrics collection."""
    print("=" * 60)
    print("Metrics Collection Example")
    print("=" * 60)
    print()

    # Create service with NoOp metrics (for demonstration)
    print("Creating service with NoOp metrics collector...")
    service = ExampleService()
    print()

    # Process various items
    print("Processing items...")
    item_types = ["email", "document", "thread", "email", "document"]

    for i, item_type in enumerate(item_types, 1):
        try:
            result = service.process_item(f"item-{i}", item_type)
            print(f"  ✓ Processed {result['item_id']} ({result['size_bytes']} bytes)")
        except Exception as e:
            print(f"  ✗ Failed to process item-{i}: {e}")
    print()

    # Handle some HTTP requests
    print("Handling HTTP requests...")
    requests = [
        ("GET", "/api/status"),
        ("POST", "/api/items"),
        ("GET", "/api/items/123"),
        ("DELETE", "/api/items/456"),
        ("GET", "/api/status"),
    ]

    for method, endpoint in requests:
        response = service.handle_request(method, endpoint)
        status_emoji = "✓" if response["status"] == 200 else "✗"
        print(f"  {status_emoji} {method} {endpoint} -> {response['status']} ({response['duration']:.3f}s)")
    print()

    # Check queue depth
    print("Checking queue depth...")
    depth = service.get_queue_depth()
    print(f"  Current queue depth: {depth}")
    print()

    # Display collected metrics (only works with NoOpMetricsCollector)
    if hasattr(service.metrics, 'get_counter_total'):
        print("=" * 60)
        print("Collected Metrics Summary")
        print("=" * 60)
        print()

        print("Counters:")
        print(f"  Total items started: {service.metrics.get_counter_total('items_started_total')}")
        print(f"  Total items processed: {service.metrics.get_counter_total('items_processed_total')}")
        print(f"  Total HTTP requests: {service.metrics.get_counter_total('http_requests_total')}")
        print(f"  Total HTTP responses: {service.metrics.get_counter_total('http_responses_total')}")
        print()

        print("Observations:")
        durations = service.metrics.get_observations('processing_duration_seconds')
        if durations:
            print(f"  Processing durations: {len(durations)} samples")
            print(f"    Min: {min(durations):.3f}s")
            print(f"    Max: {max(durations):.3f}s")
            print(f"    Avg: {sum(durations)/len(durations):.3f}s")
        print()

        print("Gauges:")
        queue_depth = service.metrics.get_gauge_value('queue_depth')
        if queue_depth is not None:
            print(f"  Queue depth: {queue_depth}")
        print()

    print("=" * 60)
    print("Example completed!")
    print()
    print("To use Prometheus in production:")
    print("  1. Set METRICS_BACKEND=prometheus")
    print("  2. Install: pip install prometheus-client")
    print("  3. Start HTTP server: prometheus_client.start_http_server(8000)")
    print("  4. Scrape metrics at http://localhost:8000/metrics")
    print("=" * 60)


if __name__ == "__main__":
    main()
