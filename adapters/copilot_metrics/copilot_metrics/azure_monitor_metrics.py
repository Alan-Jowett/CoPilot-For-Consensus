# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Monitor metrics collector implementation using OpenTelemetry."""

import logging
from typing import Any

from copilot_config.generated.adapters.metrics import DriverConfig_Metrics_AzureMonitor

from .base import MetricsCollector

logger = logging.getLogger(__name__)

# Import Azure Monitor OpenTelemetry exporter with graceful fallback
try:
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    AZURE_MONITOR_AVAILABLE = True
except ImportError:
    AZURE_MONITOR_AVAILABLE = False
    otel_metrics = None  # type: ignore
    # Use debug level for optional dependency - error is raised if user tries to actually use it
    logger.debug(
        "Azure Monitor OpenTelemetry packages not installed. "
        "Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk"
    )


class AzureMonitorMetricsCollector(MetricsCollector):
    """Azure Monitor metrics collector for Azure-native observability.

    Uses OpenTelemetry SDK with Azure Monitor exporter to send metrics to
    Azure Monitor (Application Insights). Supports batching and asynchronous
    export for production workloads.

    Configuration via driver_config in from_config() method:
    - connection_string: Azure Monitor connection string (required)
    - namespace: Metric namespace prefix (default: "copilot")
    - export_interval_millis: Export interval in ms (default: 60000)
    - raise_on_error: Whether to raise on metric errors (default: False)

    Note: Requires azure-monitor-opentelemetry-exporter and opentelemetry-sdk packages.
    Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk
    """

    def __init__(
        self,
        connection_string: str,
        namespace: str = "copilot",
        export_interval_millis: int = 60000,
        raise_on_error: bool = False,
    ):
        """Initialize Azure Monitor metrics collector.

        Args:
            connection_string: Azure Monitor connection string (required).
                              Can be a full connection string or InstrumentationKey=<key> format.
            namespace: Namespace prefix for all metrics (default: "copilot")
            export_interval_millis: Export interval in milliseconds (default: 60000)
            raise_on_error: If True, raise exceptions on metric errors (useful for testing).
                           If False, log errors and continue (default, safer for production)

        Raises:
            ImportError: If required Azure Monitor packages are not installed
        """
        if not AZURE_MONITOR_AVAILABLE:
            raise ImportError(
                "Azure Monitor OpenTelemetry packages are required for AzureMonitorMetricsCollector. "
                "Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk"
            )

        self.connection_string = connection_string
        self.namespace = namespace
        self.raise_on_error = raise_on_error
        self._metrics_errors_count = 0

        # Initialize cache dictionaries first to ensure object is always in consistent state
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._gauge_values: dict[str, float] = {}

        # Create Azure Monitor exporter
        try:
            exporter = AzureMonitorMetricExporter(connection_string=self.connection_string)

            # Create periodic metric reader with configured interval
            reader = PeriodicExportingMetricReader(
                exporter=exporter,
                export_interval_millis=export_interval_millis,
            )

            # Create resource with service information
            resource = Resource.create(
                {
                    "service.name": self.namespace,
                    "service.namespace": "copilot-for-consensus",
                }
            )

            # Create meter provider (instance-local to avoid global state conflicts)
            self._provider = MeterProvider(resource=resource, metric_readers=[reader])

            # Get meter for creating instruments from the instance-local provider
            self._meter = self._provider.get_meter(
                name=f"{self.namespace}.metrics",
                version="0.1.0",
            )

            logger.info(
                f"AzureMonitorMetricsCollector initialized with namespace '{self.namespace}' "
                f"and export interval {export_interval_millis}ms"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Azure Monitor metrics collector: {e}")
            if self.raise_on_error:
                raise
            # In non-raising mode, continue but metrics won't work
            self._meter = None
            self._provider = None

    def _get_or_create_counter(self, name: str) -> Any | None:
        """Get or create an OpenTelemetry counter.

        Args:
            name: Metric name

        Returns:
            OpenTelemetry Counter object or None if meter not initialized
        """
        if self._meter is None:
            return None

        if name not in self._counters:
            self._counters[name] = self._meter.create_counter(
                name=f"{self.namespace}.{name}",
                description=f"Counter metric: {name}",
            )

        return self._counters[name]

    def _get_or_create_histogram(self, name: str) -> Any | None:
        """Get or create an OpenTelemetry histogram.

        Args:
            name: Metric name

        Returns:
            OpenTelemetry Histogram object or None if meter not initialized
        """
        if self._meter is None:
            return None

        if name not in self._histograms:
            self._histograms[name] = self._meter.create_histogram(
                name=f"{self.namespace}.{name}",
                description=f"Histogram metric: {name}",
            )

        return self._histograms[name]

    def _get_or_create_gauge(self, name: str) -> Any | None:
        """Get or create an OpenTelemetry observable gauge.

        Note: OpenTelemetry gauges are observable (callback-based), so we store
        the latest value in _gauge_values and register a callback to report it.

        Args:
            name: Metric name

        Returns:
            OpenTelemetry ObservableGauge object or None if meter not initialized
        """
        if self._meter is None:
            return None

        if name not in self._gauges:
            gauge_key = f"{self.namespace}.{name}"

            # Initialize gauge value
            self._gauge_values[gauge_key] = 0.0

            # Create callback that returns the current value
            # Capture gauge_key by value to avoid closure bug
            def gauge_callback(key: str = gauge_key) -> Any:
                return [(self._gauge_values[key], {})]

            self._gauges[name] = self._meter.create_observable_gauge(
                name=gauge_key,
                callbacks=[gauge_callback],
                description=f"Gauge metric: {name}",
            )

        return self._gauges[name]

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter in Azure Monitor.

        Args:
            name: Name of the counter metric
            value: Amount to increment by (default: 1.0)
            tags: Optional dictionary of tags/labels for the metric (dimensions in Azure Monitor)
        """
        try:
            counter = self._get_or_create_counter(name)
            if counter is not None:
                attributes = tags or {}
                counter.add(value, attributes=attributes)
                logger.debug(f"AzureMonitorMetricsCollector: increment {name} by {value} with tags {tags}")
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to increment counter {name}: {e}")
            if self.raise_on_error:
                raise

    def observe(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Observe a value in an Azure Monitor histogram.

        Args:
            name: Name of the histogram metric
            value: Value to observe
            tags: Optional dictionary of tags/labels for the metric (dimensions in Azure Monitor)
        """
        try:
            histogram = self._get_or_create_histogram(name)
            if histogram is not None:
                attributes = tags or {}
                histogram.record(value, attributes=attributes)
                logger.debug(f"AzureMonitorMetricsCollector: observe {name} value {value} with tags {tags}")
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to observe histogram {name}: {e}")
            if self.raise_on_error:
                raise

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set an Azure Monitor gauge to a specific value.

        Note: OpenTelemetry gauges are observable (callback-based), so this implementation
        stores the value internally and the gauge callback reports it periodically.
        Tags are not fully supported for gauges in the current implementation.

        Args:
            name: Name of the gauge metric
            value: Value to set the gauge to
            tags: Optional dictionary of tags/labels (note: limited support with observable gauges)
        """
        try:
            # Ensure gauge is created (registers callback)
            gauge = self._get_or_create_gauge(name)
            if gauge is not None:
                # Store the latest value for the callback to report
                gauge_key = f"{self.namespace}.{name}"
                self._gauge_values[gauge_key] = value
                logger.debug(f"AzureMonitorMetricsCollector: gauge {name} set to {value} with tags {tags}")

                if tags:
                    logger.warning(
                        f"Tags/dimensions are not fully supported for gauge '{name}' "
                        "with observable gauges in OpenTelemetry"
                    )
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error(f"Failed to set gauge {name}: {e}")
            if self.raise_on_error:
                raise

    def get_gauge_value(self, name: str, tags: dict[str, str] | None = None) -> float | None:
        """Get the most recent value of a gauge metric.

        Args:
            name: Name of the gauge metric
            tags: Optional tags to filter by (not used in Azure Monitor implementation)

        Returns:
            Most recent gauge value, or None if not found
        """
        gauge_key = f"{self.namespace}.{name}"
        return self._gauge_values.get(gauge_key)

    def get_errors_count(self) -> int:
        """Get the count of metrics collection errors.

        Returns:
            Number of errors that occurred during metrics collection
        """
        return self._metrics_errors_count

    def shutdown(self) -> None:
        """Shutdown the metrics collector and flush remaining metrics.

        This method should be called when shutting down the application to ensure
        all metrics are exported before termination.
        """
        if not AZURE_MONITOR_AVAILABLE or otel_metrics is None:
            logger.warning("Azure Monitor packages not available, skipping shutdown")
            return

        # Use instance-specific provider to avoid affecting global state
        provider = getattr(self, "_provider", None)
        if provider is None:
            logger.warning(
                "No instance-specific meter provider found; skipping shutdown"
            )
            return

        try:
            if hasattr(provider, 'shutdown'):
                provider.shutdown()
                logger.info("Azure Monitor metrics collector shut down successfully")
        except Exception as e:
            logger.error(f"Error during Azure Monitor metrics collector shutdown: {e}")

    @classmethod
    def from_config(
        cls,
        driver_config: DriverConfig_Metrics_AzureMonitor,
    ) -> "AzureMonitorMetricsCollector":
        """Create an AzureMonitorMetricsCollector from configuration.

        Args:
            driver_config: Typed driver config.

        Returns:
            Configured AzureMonitorMetricsCollector instance

        Raises:
            ImportError: If Azure Monitor packages are not installed
        """
        return cls(
            connection_string=driver_config.connection_string,
            namespace=driver_config.namespace,
            export_interval_millis=driver_config.export_interval_millis,
            raise_on_error=driver_config.raise_on_error
        )
