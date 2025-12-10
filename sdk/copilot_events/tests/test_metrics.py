# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for metrics collectors."""

import sys
import pytest

from copilot_events import (
    create_metrics_collector,
    MetricsCollector,
    NoOpMetricsCollector,
    PrometheusMetricsCollector,
)


class TestMetricsFactory:
    """Tests for create_metrics_collector factory function."""

    def test_create_noop_collector(self):
        """Test creating a no-op metrics collector."""
        collector = create_metrics_collector(backend="noop")
        
        assert isinstance(collector, NoOpMetricsCollector)
        assert isinstance(collector, MetricsCollector)

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is not None,
        reason="prometheus_client is installed"
    )
    def test_create_prometheus_collector_without_lib(self):
        """Test creating Prometheus collector when library is not available."""
        with pytest.raises(ImportError, match="prometheus_client is required"):
            create_metrics_collector(backend="prometheus")

    def test_create_unknown_backend_type(self):
        """Test that unknown backend type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown metrics backend"):
            create_metrics_collector(backend="invalid")

    def test_create_with_env_default(self, monkeypatch):
        """Test factory uses environment variable for default backend."""
        monkeypatch.setenv("METRICS_BACKEND", "noop")
        
        collector = create_metrics_collector()
        
        assert isinstance(collector, NoOpMetricsCollector)


class TestNoOpMetricsCollector:
    """Tests for NoOpMetricsCollector."""

    def test_increment_counter(self):
        """Test incrementing a counter."""
        collector = NoOpMetricsCollector()
        
        collector.increment("test_counter", value=1.0)
        collector.increment("test_counter", value=2.0)
        
        assert len(collector.counters) == 2
        assert collector.get_counter_total("test_counter") == 3.0

    def test_increment_counter_with_tags(self):
        """Test incrementing a counter with tags."""
        collector = NoOpMetricsCollector()
        
        collector.increment("http_requests", value=1.0, tags={"method": "GET", "status": "200"})
        collector.increment("http_requests", value=1.0, tags={"method": "POST", "status": "201"})
        collector.increment("http_requests", value=1.0, tags={"method": "GET", "status": "200"})
        
        assert len(collector.counters) == 3
        assert collector.get_counter_total("http_requests") == 3.0
        assert collector.get_counter_total(
            "http_requests", 
            tags={"method": "GET", "status": "200"}
        ) == 2.0

    def test_observe_histogram(self):
        """Test observing values for histogram."""
        collector = NoOpMetricsCollector()
        
        collector.observe("request_duration", 0.1)
        collector.observe("request_duration", 0.2)
        collector.observe("request_duration", 0.15)
        
        observations = collector.get_observations("request_duration")
        assert len(observations) == 3
        assert observations == [0.1, 0.2, 0.15]

    def test_observe_histogram_with_tags(self):
        """Test observing values with tags."""
        collector = NoOpMetricsCollector()
        
        collector.observe("request_duration", 0.1, tags={"endpoint": "/api"})
        collector.observe("request_duration", 0.2, tags={"endpoint": "/api"})
        collector.observe("request_duration", 0.5, tags={"endpoint": "/admin"})
        
        api_observations = collector.get_observations("request_duration", tags={"endpoint": "/api"})
        assert len(api_observations) == 2
        assert api_observations == [0.1, 0.2]

    def test_set_gauge(self):
        """Test setting a gauge value."""
        collector = NoOpMetricsCollector()
        
        collector.gauge("queue_depth", 10.0)
        collector.gauge("queue_depth", 15.0)
        collector.gauge("queue_depth", 5.0)
        
        assert collector.get_gauge_value("queue_depth") == 5.0

    def test_set_gauge_with_tags(self):
        """Test setting gauge with tags."""
        collector = NoOpMetricsCollector()
        
        collector.gauge("memory_usage", 100.0, tags={"service": "ingestion"})
        collector.gauge("memory_usage", 200.0, tags={"service": "parsing"})
        collector.gauge("memory_usage", 150.0, tags={"service": "ingestion"})
        
        assert collector.get_gauge_value("memory_usage", tags={"service": "ingestion"}) == 150.0
        assert collector.get_gauge_value("memory_usage", tags={"service": "parsing"}) == 200.0

    def test_clear_metrics(self):
        """Test clearing all metrics."""
        collector = NoOpMetricsCollector()
        
        collector.increment("counter", 1.0)
        collector.observe("histogram", 0.5)
        collector.gauge("gauge", 10.0)
        
        assert len(collector.counters) == 1
        assert len(collector.observations) == 1
        assert len(collector.gauges) == 1
        
        collector.clear_metrics()
        
        assert len(collector.counters) == 0
        assert len(collector.observations) == 0
        assert len(collector.gauges) == 0

    def test_gauge_value_not_found(self):
        """Test getting gauge value that doesn't exist."""
        collector = NoOpMetricsCollector()
        
        value = collector.get_gauge_value("nonexistent")
        
        assert value is None


class TestPrometheusMetricsCollector:
    """Tests for PrometheusMetricsCollector."""

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is not None,
        reason="prometheus_client is installed"
    )
    def test_requires_prometheus_client(self):
        """Test that PrometheusMetricsCollector requires prometheus_client."""
        with pytest.raises(ImportError, match="prometheus_client is required"):
            PrometheusMetricsCollector()

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_increment_counter_with_prometheus(self):
        """Test incrementing counter with Prometheus backend."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        collector = PrometheusMetricsCollector(registry=registry, namespace="test")
        
        collector.increment("requests_total", value=1.0)
        collector.increment("requests_total", value=2.0)
        
        # Verify metric was created
        assert ("requests_total", ()) in collector._counters

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_observe_histogram_with_prometheus(self):
        """Test observing histogram with Prometheus backend."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        collector = PrometheusMetricsCollector(registry=registry, namespace="test")
        
        collector.observe("request_duration", 0.1)
        collector.observe("request_duration", 0.2)
        
        # Verify metric was created
        assert ("request_duration", ()) in collector._histograms

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_set_gauge_with_prometheus(self):
        """Test setting gauge with Prometheus backend."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        collector = PrometheusMetricsCollector(registry=registry, namespace="test")
        
        collector.gauge("queue_depth", 10.0)
        collector.gauge("queue_depth", 15.0)
        
        # Verify metric was created
        assert ("queue_depth", ()) in collector._gauges

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_metrics_with_labels(self):
        """Test metrics with Prometheus labels."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        collector = PrometheusMetricsCollector(registry=registry, namespace="test")
        
        tags = {"method": "GET", "status": "200"}
        collector.increment("http_requests", value=1.0, tags=tags)
        
        # Verify metric was created with correct labels
        labelnames = tuple(sorted(tags.keys()))
        assert ("http_requests", labelnames) in collector._counters


class TestMetricsIntegration:
    """Integration tests for metrics collection."""

    def test_counter_workflow(self):
        """Test complete counter workflow."""
        collector = create_metrics_collector(backend="noop")
        
        # Simulate some events
        collector.increment("archives_ingested", tags={"source": "datatracker"})
        collector.increment("archives_ingested", tags={"source": "datatracker"})
        collector.increment("archives_ingested", tags={"source": "github"})
        
        # Verify counts
        assert collector.get_counter_total("archives_ingested") == 3.0
        assert collector.get_counter_total(
            "archives_ingested",
            tags={"source": "datatracker"}
        ) == 2.0

    def test_histogram_workflow(self):
        """Test complete histogram workflow."""
        collector = create_metrics_collector(backend="noop")
        
        # Simulate some measurements
        durations = [0.1, 0.2, 0.15, 0.3, 0.25]
        for duration in durations:
            collector.observe("processing_duration", duration, tags={"service": "ingestion"})
        
        # Verify observations
        observations = collector.get_observations("processing_duration", tags={"service": "ingestion"})
        assert observations == durations

    def test_gauge_workflow(self):
        """Test complete gauge workflow."""
        collector = create_metrics_collector(backend="noop")
        
        # Simulate changing values
        collector.gauge("active_threads", 5.0)
        collector.gauge("active_threads", 10.0)
        collector.gauge("active_threads", 7.0)
        
        # Verify latest value
        assert collector.get_gauge_value("active_threads") == 7.0
