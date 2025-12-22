# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Monitor metrics collector implementation using OpenTelemetry."""

import logging
import os
from typing import Dict, Optional, Any

from .metrics import MetricsCollector

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
    logger.warning(
        "Azure Monitor OpenTelemetry packages not installed. "
        "Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk"
    )


class AzureMonitorMetricsCollector(MetricsCollector):
    """Azure Monitor metrics collector for Azure-native observability.

    Uses OpenTelemetry SDK with Azure Monitor exporter to send metrics to
    Azure Monitor (Application Insights). Supports batching and asynchronous
    export for production workloads.

    Configuration via environment variables:
    - AZURE_MONITOR_CONNECTION_STRING: Azure Monitor connection string (required)
    - AZURE_MONITOR_INSTRUMENTATION_KEY: Alternative to connection string (legacy)
    - AZURE_MONITOR_METRIC_NAMESPACE: Metric namespace prefix (default: "copilot")
    - AZURE_MONITOR_EXPORT_INTERVAL_MILLIS: Export interval in ms (default: 60000)

    Note: Requires azure-monitor-opentelemetry-exporter and opentelemetry-sdk packages.
    Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        namespace: str = "copilot",
        export_interval_millis: int = 60000,
        raise_on_error: bool = False,
    ):
        """Initialize Azure Monitor metrics collector.

        Args:
            connection_string: Azure Monitor connection string (or use env var)
            namespace: Namespace prefix for all metrics (default: "copilot")
            export_interval_millis: Export interval in milliseconds (default: 60000)
            raise_on_error: If True, raise exceptions on metric errors (useful for testing).
                           If False, log errors and continue (default, safer for production)

        Raises:
            ImportError: If required Azure Monitor packages are not installed
            ValueError: If connection string is not provided
        """
        if not AZURE_MONITOR_AVAILABLE:
            raise ImportError(
                "Azure Monitor OpenTelemetry packages are required for AzureMonitorMetricsCollector. "
                "Install with: pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk"
            )

        # Get connection string from parameter or environment
        self.connection_string = connection_string or os.getenv("AZURE_MONITOR_CONNECTION_STRING")

        # Fallback to instrumentation key if connection string not provided
        if not self.connection_string:
            instrumentation_key = os.getenv("AZURE_MONITOR_INSTRUMENTATION_KEY")
            if instrumentation_key:
                self.connection_string = f"InstrumentationKey={instrumentation_key}"

        if not self.connection_string:
            raise ValueError(
                "Azure Monitor connection string is required. "
                "Set AZURE_MONITOR_CONNECTION_STRING or AZURE_MONITOR_INSTRUMENTATION_KEY environment variable, "
                "or pass connection_string parameter."
            )

        self.namespace = namespace or os.getenv("AZURE_MONITOR_METRIC_NAMESPACE", "copilot")
        self.raise_on_error = raise_on_error
        self._metrics_errors_count = 0

        # Configure export interval from parameter or environment
        export_interval_env = os.getenv("AZURE_MONITOR_EXPORT_INTERVAL_MILLIS")
        if export_interval_env:
            try:
                export_interval_millis = int(export_interval_env)
            except ValueError:
                logger.warning(
                    "Invalid AZURE_MONITOR_EXPORT_INTERVAL_MILLIS value: %s. Using default: %s",
                    export_interval_env,
                    export_interval_millis
                )

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

            # Create and set meter provider
            provider = MeterProvider(resource=resource, metric_readers=[reader])
            otel_metrics.set_meter_provider(provider)

            # Get meter for creating instruments
            self._meter = otel_metrics.get_meter(
                name=f"{self.namespace}.metrics",
                version="0.1.0",
            )

            # Cache for metric instruments
            self._counters: Dict[str, Any] = {}
            self._histograms: Dict[str, Any] = {}
            self._gauges: Dict[str, Any] = {}
            self._gauge_values: Dict[str, float] = {}

            logger.info(
                "AzureMonitorMetricsCollector initialized with namespace '%s' "
                "and export interval %sms",
                self.namespace,
                export_interval_millis
            )

        except Exception as e:
            logger.error("Failed to initialize Azure Monitor metrics collector: %s", e)
            if self.raise_on_error:
                raise
            # In non-raising mode, continue but metrics won't work
            self._meter = None

    def _get_or_create_counter(self, name: str) -> Optional[Any]:
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

    def _get_or_create_histogram(self, name: str) -> Optional[Any]:
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

    def _get_or_create_gauge(self, name: str) -> Optional[Any]:
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
            def gauge_callback() -> Any:
                return [(self._gauge_values[gauge_key], {})]

            self._gauges[name] = self._meter.create_observable_gauge(
                name=gauge_key,
                callbacks=[gauge_callback],
                description=f"Gauge metric: {name}",
            )

        return self._gauges[name]

    def increment(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
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
                logger.debug("AzureMonitorMetricsCollector: increment %s by %s with tags %s",
                            name, value, tags)
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error("Failed to increment counter %s: %s", name, e)
            if self.raise_on_error:
                raise

    def observe(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
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
                logger.debug("AzureMonitorMetricsCollector: observe %s value %s with tags %s",
                            name, value, tags)
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error("Failed to observe histogram %s: %s", name, e)
            if self.raise_on_error:
                raise

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
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
                logger.debug("AzureMonitorMetricsCollector: gauge %s set to %s with tags %s",
                            name, value, tags)

                if tags:
                    logger.warning(
                        "Tags/dimensions are not fully supported for gauge '%s' "
                        "with observable gauges in OpenTelemetry",
                        name
                    )
        except Exception as e:
            self._metrics_errors_count += 1
            logger.error("Failed to set gauge %s: %s", name, e)
            if self.raise_on_error:
                raise

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

        try:
            provider = otel_metrics.get_meter_provider()
            if hasattr(provider, 'shutdown'):
                provider.shutdown()
                logger.info("Azure Monitor metrics collector shut down successfully")
        except Exception as e:
            logger.error("Error during Azure Monitor metrics collector shutdown: %s", e)
