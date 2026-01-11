# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Prometheus metrics collector implementation."""

import logging
from typing import Optional

from copilot_config import DriverConfig

from .base import MetricsCollector

logger = logging.getLogger(__name__)

# Import prometheus_client with graceful fallback
try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed. Install with: pip install prometheus-client")


class PrometheusMetricsCollector(MetricsCollector):
    """Prometheus metrics collector for production observability.

    Uses prometheus_client library to expose metrics in Prometheus format.
    Metrics can be scraped by Prometheus server at the /metrics endpoint.

    Important: All calls to the same metric name must use consistent label keys.
    For example, if you call increment("requests", tags={"method": "GET"}),
    all subsequent calls to increment("requests", ...) must use the same
    label key "method". Using different label keys (e.g., {"endpoint": "/api"})
    will raise a ValueError from Prometheus.

    Note: Requires prometheus_client to be installed.
    Install with: pip install prometheus-client
    """

    def __init__(self, registry: Optional['CollectorRegistry'] = None, namespace: str = "copilot",
                 raise_on_error: bool = False):
        """Initialize Prometheus metrics collector.

        Args:
            registry: Optional Prometheus registry (uses default if None)
            namespace: Namespace prefix for all metrics (default: "copilot")
            raise_on_error: If True, raise exceptions on metric errors (useful for testing).
                           If False, log errors and continue (default, safer for production)
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus_client is required for PrometheusMetricsCollector. "
                "Install with: pip install prometheus-client"
            )

        self.registry = registry
        self.namespace = namespace
        self.raise_on_error = raise_on_error
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._gauges: dict[str, Gauge] = {}
        self._metrics_errors_count = 0

    def _get_or_create_counter(self, name: str, tags: dict[str, str] | None = None) -> 'Counter':
        """Get or create a Prometheus counter.

        Args:
            name: Metric name
            tags: Optional tags to use as labels

        Returns:
            Prometheus Counter object
        """
        labelnames = tuple(sorted(tags.keys())) if tags else ()
        cache_key = (name, labelnames)

        if cache_key not in self._counters:
            self._counters[cache_key] = Counter(
                name=name,
                documentation=f"Counter metric: {name}",
                labelnames=labelnames,
                namespace=self.namespace,
                registry=self.registry
            )

        return self._counters[cache_key]

    def _get_or_create_histogram(self, name: str, tags: dict[str, str] | None = None) -> 'Histogram':
        """Get or create a Prometheus histogram.

        Args:
            name: Metric name
            tags: Optional tags to use as labels

        Returns:
            Prometheus Histogram object
        """
        labelnames = tuple(sorted(tags.keys())) if tags else ()
        cache_key = (name, labelnames)

        if cache_key not in self._histograms:
            self._histograms[cache_key] = Histogram(
                name=name,
                documentation=f"Histogram metric: {name}",
                labelnames=labelnames,
                namespace=self.namespace,
                registry=self.registry
            )

        return self._histograms[cache_key]

    def _get_or_create_gauge(self, name: str, tags: dict[str, str] | None = None) -> 'Gauge':
        """Get or create a Prometheus gauge.

        Args:
            name: Metric name
            tags: Optional tags to use as labels

        Returns:
            Prometheus Gauge object
        """
        labelnames = tuple(sorted(tags.keys())) if tags else ()
        cache_key = (name, labelnames)

        if cache_key not in self._gauges:
            self._gauges[cache_key] = Gauge(
                name=name,
                documentation=f"Gauge metric: {name}",
                labelnames=labelnames,
                namespace=self.namespace,
                registry=self.registry
            )

        return self._gauges[cache_key]

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a Prometheus counter.

        Args:
            name: Name of the counter metric
            value: Amount to increment by (default: 1.0)
            tags: Optional dictionary of tags/labels for the metric
        """
        try:
            counter = self._get_or_create_counter(name, tags)
            if tags:
                counter.labels(**tags).inc(value)
            else:
                counter.inc(value)
            logger.debug(f"PrometheusMetricsCollector: increment {name} by {value} with tags {tags}")
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to increment counter {name}: {e}")
            if self.raise_on_error:
                raise

    def observe(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Observe a value in a Prometheus histogram.

        Args:
            name: Name of the histogram metric
            value: Value to observe
            tags: Optional dictionary of tags/labels for the metric
        """
        try:
            histogram = self._get_or_create_histogram(name, tags)
            if tags:
                histogram.labels(**tags).observe(value)
            else:
                histogram.observe(value)
            logger.debug(f"PrometheusMetricsCollector: observe {name} value {value} with tags {tags}")
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to observe histogram {name}: {e}")
            if self.raise_on_error:
                raise

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a Prometheus gauge to a specific value.

        Args:
            name: Name of the gauge metric
            value: Value to set the gauge to
            tags: Optional dictionary of tags/labels for the metric
        """
        try:
            gauge = self._get_or_create_gauge(name, tags)
            if tags:
                gauge.labels(**tags).set(value)
            else:
                gauge.set(value)
            logger.debug(f"PrometheusMetricsCollector: gauge {name} set to {value} with tags {tags}")
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to set gauge {name}: {e}")
            if self.raise_on_error:
                raise

    def get_errors_count(self) -> int:
        """Get the count of metrics collection errors.

        Returns:
            Number of errors that occurred during metrics collection
        """
        return self._metrics_errors_count

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "PrometheusMetricsCollector":
        """Create a PrometheusMetricsCollector from configuration.

        Args:
            driver_config: DriverConfig instance with optional attributes:
                - registry: Optional Prometheus registry (default: None)
                - namespace: Namespace prefix (default: "copilot")
                - raise_on_error: Whether to raise on metric errors (default: False)

        Returns:
            Configured PrometheusMetricsCollector instance

        Raises:
            ImportError: If prometheus_client is not installed
        """
        return cls(
            registry=driver_config.registry,
            namespace=driver_config.namespace,
            raise_on_error=driver_config.raise_on_error
        )
