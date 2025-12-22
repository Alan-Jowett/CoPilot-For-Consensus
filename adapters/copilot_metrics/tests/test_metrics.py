# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for metrics collectors."""

import sys
import pytest

from copilot_metrics import (
    create_metrics_collector,
    MetricsCollector,
    NoOpMetricsCollector,
    PrometheusMetricsCollector,
    PrometheusPushGatewayMetricsCollector,
)


@pytest.fixture
def mock_azure_exporter(monkeypatch):
    """Fixture to mock Azure Monitor exporter for tests."""
    # Only mock if Azure packages are available
    try:
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                self.connection_string = connection_string
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        return MockExporter
    except ImportError:
        return None


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
        reason="prometheus_client is installed; test requires it to be missing"
    )
    def test_requires_prometheus_client(self):
        """Test that PrometheusMetricsCollector raises ImportError when prometheus_client is missing.
        
        This test only runs in environments where prometheus_client is NOT installed.
        """
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


class TestPrometheusPushGatewayMetricsCollector:
    """Tests for PrometheusPushGatewayMetricsCollector."""

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_initialization_defaults(self, monkeypatch):
        """Collector should initialize with default gateway and job, normalizing URL."""
        # Ensure no env overrides
        monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY", raising=False)
        monkeypatch.delenv("METRICS_JOB_NAME", raising=False)

        collector = PrometheusPushGatewayMetricsCollector()
        assert collector.gateway.startswith("http://")
        assert collector.job == "ingestion"

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_initialization_with_env(self, monkeypatch):
        """Gateway and job can be configured via environment variables."""
        monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY", "monitoring:9091")
        monkeypatch.setenv("METRICS_JOB_NAME", "ingestion-test")

        collector = PrometheusPushGatewayMetricsCollector()
        assert collector.gateway == "http://monitoring:9091"
        assert collector.job == "ingestion-test"

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_push_calls_pushgateway(self, monkeypatch):
        """push() should call prometheus_client.push_to_gateway with expected args."""
        calls = {}

        def fake_push_to_gateway(gateway, job, registry, grouping_key=None):
            calls["gateway"] = gateway
            calls["job"] = job
            calls["registry"] = registry
            calls["grouping_key"] = grouping_key or {}

        # Patch push_to_gateway in module where it's imported
        import copilot_metrics.pushgateway_metrics as pgm
        monkeypatch.setattr(pgm, "push_to_gateway", fake_push_to_gateway)

        collector = PrometheusPushGatewayMetricsCollector(
            gateway="http://pushgateway:9091",
            job="ingestion",
            grouping_key={"instance": "test"},
        )

        # Add a metric so registry is non-empty
        collector.increment("unit_test_counter", value=1.0)
        collector.push()

        assert calls["gateway"] == "http://pushgateway:9091"
        assert calls["job"] == "ingestion"
        assert calls["grouping_key"] == {"instance": "test"}
        assert calls["registry"] is collector.registry

    @pytest.mark.skipif(
        sys.modules.get('prometheus_client') is None,
        reason="prometheus_client not installed"
    )
    def test_push_error_propagation(self, monkeypatch):
        """Collector should raise if push_to_gateway fails."""
        import copilot_metrics.pushgateway_metrics as pgm

        def fake_push_to_gateway(*args, **kwargs):
            raise RuntimeError("simulated push failure")

        monkeypatch.setattr(pgm, "push_to_gateway", fake_push_to_gateway)

        collector = PrometheusPushGatewayMetricsCollector(
            gateway="http://pushgateway:9091",
            job="ingestion",
        )
        collector.increment("unit_test_counter", value=1.0)

        with pytest.raises(RuntimeError, match="simulated push failure"):
            collector.push()


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


class TestAzureMonitorMetricsCollector:
    """Tests for AzureMonitorMetricsCollector."""

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages are installed; test requires them to be missing"
    )
    def test_requires_azure_monitor_packages(self):
        """Test that AzureMonitorMetricsCollector raises ImportError when packages are missing.

        This test only runs in environments where Azure Monitor packages are NOT installed.
        """
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector

        with pytest.raises(ImportError, match="Azure Monitor OpenTelemetry packages are required"):
            AzureMonitorMetricsCollector(connection_string="InstrumentationKey=test-key")

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_initialization_requires_connection_string(self):
        """Test that initialization fails without connection string."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        with pytest.raises(ValueError, match="Azure Monitor connection string is required"):
            AzureMonitorMetricsCollector()

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_initialization_with_connection_string(self, mock_azure_exporter):
        """Test successful initialization with connection string."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test"
        )
        
        assert collector.connection_string == "InstrumentationKey=test-key"
        assert collector.namespace == "test"

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_initialization_from_env_connection_string(self, monkeypatch):
        """Test initialization from AZURE_MONITOR_CONNECTION_STRING environment variable."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        monkeypatch.setenv("AZURE_MONITOR_CONNECTION_STRING", "InstrumentationKey=env-key")
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                self.connection_string = connection_string
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector()
        
        assert collector.connection_string == "InstrumentationKey=env-key"

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_initialization_from_instrumentation_key(self, monkeypatch):
        """Test initialization from AZURE_MONITOR_INSTRUMENTATION_KEY (legacy)."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        monkeypatch.setenv("AZURE_MONITOR_INSTRUMENTATION_KEY", "legacy-key")
        monkeypatch.delenv("AZURE_MONITOR_CONNECTION_STRING", raising=False)
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                self.connection_string = connection_string
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector()
        
        assert collector.connection_string == "InstrumentationKey=legacy-key"

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_increment_counter_with_azure_monitor(self, monkeypatch):
        """Test incrementing counter with Azure Monitor backend."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        # Mock the exporter and OpenTelemetry components
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                pass
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test"
        )
        
        # These should not raise exceptions
        collector.increment("requests_total", value=1.0)
        collector.increment("requests_total", value=2.0, tags={"method": "GET"})
        
        # Verify metrics are tracked
        assert "requests_total" in collector._counters

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_observe_histogram_with_azure_monitor(self, monkeypatch):
        """Test observing histogram with Azure Monitor backend."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                pass
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test"
        )
        
        collector.observe("request_duration", 0.1)
        collector.observe("request_duration", 0.2, tags={"endpoint": "/api"})
        
        # Verify metrics are tracked
        assert "request_duration" in collector._histograms

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_set_gauge_with_azure_monitor(self, monkeypatch):
        """Test setting gauge with Azure Monitor backend."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                pass
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test"
        )
        
        collector.gauge("queue_depth", 10.0)
        collector.gauge("queue_depth", 15.0)
        
        # Verify gauge is tracked
        assert "queue_depth" in collector._gauges
        assert "test.queue_depth" in collector._gauge_values
        assert collector._gauge_values["test.queue_depth"] == 15.0

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_graceful_handling_with_none_meter(self, mock_azure_exporter):
        """Test graceful handling when meter is None (no raise_on_error)."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                pass
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test",
            raise_on_error=True
        )
        
        # Force an error by making _meter None
        collector._meter = None
        
        # This should not raise since we handle None meter gracefully
        collector.increment("test_counter", 1.0)
        assert collector.get_errors_count() == 0  # No error recorded for None meter

    @pytest.mark.skipif(
        sys.modules.get('azure.monitor.opentelemetry.exporter') is None
        or sys.modules.get('opentelemetry') is None,
        reason="Azure Monitor packages not installed"
    )
    def test_shutdown(self, monkeypatch):
        """Test collector shutdown."""
        from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
        
        # Mock the exporter
        import azure.monitor.opentelemetry.exporter as am_exporter
        
        class MockExporter:
            def __init__(self, connection_string):
                pass
        
        monkeypatch.setattr(am_exporter, "AzureMonitorMetricExporter", MockExporter)
        
        collector = AzureMonitorMetricsCollector(
            connection_string="InstrumentationKey=test-key",
            namespace="test"
        )
        
        # Should not raise
        collector.shutdown()

    def test_factory_creates_azure_monitor_collector(self, monkeypatch):
        """Test that factory can create Azure Monitor collector."""
        monkeypatch.setenv("AZURE_MONITOR_CONNECTION_STRING", "InstrumentationKey=test-key")
        
        # Test with backend parameter
        try:
            collector = create_metrics_collector(backend="azure_monitor")
            # If Azure packages are installed, verify it's the right type
            from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
            assert isinstance(collector, AzureMonitorMetricsCollector)
            assert collector.connection_string == "InstrumentationKey=test-key"
        except ImportError:
            # Expected if Azure packages not installed - test passes
            pass
        
        # Test with alternative backend name
        try:
            collector = create_metrics_collector(backend="azuremonitor")
            from copilot_metrics.azure_monitor_metrics import AzureMonitorMetricsCollector
            assert isinstance(collector, AzureMonitorMetricsCollector)
        except ImportError:
            # Expected if Azure packages not installed - test passes
            pass
