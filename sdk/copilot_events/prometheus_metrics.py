# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Prometheus metrics collector implementation."""

import logging
from typing import Dict, Optional

from .metrics import MetricsCollector

logger = logging.getLogger(__name__)

# Import prometheus_client with graceful fallback
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed. Install with: pip install prometheus-client")


class PrometheusMetricsCollector(MetricsCollector):
    """Prometheus metrics collector for production observability.
    
    Uses prometheus_client library to expose metrics in Prometheus format.
    Metrics can be scraped by Prometheus server at the /metrics endpoint.
    
    Note: Requires prometheus_client to be installed.
    Install with: pip install prometheus-client
    """

    def __init__(self, registry: Optional['CollectorRegistry'] = None, namespace: str = "copilot"):
        """Initialize Prometheus metrics collector.
        
        Args:
            registry: Optional Prometheus registry (uses default if None)
            namespace: Namespace prefix for all metrics (default: "copilot")
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus_client is required for PrometheusMetricsCollector. "
                "Install with: pip install prometheus-client"
            )
        
        self.registry = registry
        self.namespace = namespace
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}

    def _get_or_create_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> 'Counter':
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

    def _get_or_create_histogram(self, name: str, tags: Optional[Dict[str, str]] = None) -> 'Histogram':
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

    def _get_or_create_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> 'Gauge':
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

    def increment(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
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
            logger.error(f"Failed to increment counter {name}: {e}")

    def observe(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
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
            logger.error(f"Failed to observe histogram {name}: {e}")

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
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
            logger.error(f"Failed to set gauge {name}: {e}")
