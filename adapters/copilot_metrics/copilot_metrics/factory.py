# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating metrics collectors."""

import logging

from copilot_config import DriverConfig

from .base import MetricsCollector

logger = logging.getLogger(__name__)


def create_metrics_collector(
    driver_name: str,
    driver_config: DriverConfig
) -> MetricsCollector:
    """Create a metrics collector based on driver type.

    Factory function that creates the appropriate metrics collector implementation
    based on the driver name. Configuration is passed as a dictionary to support
    different backends with varying requirements.

    Supported drivers:
    - "prometheus": Prometheus metrics with registry-based collection
    - "pushgateway" or "prometheus_pushgateway": Prometheus with Pushgateway support
    - "azure_monitor" or "azuremonitor": Azure Monitor via OpenTelemetry
    - "noop": No-op collector for testing

    Args:
        driver_name: Name of the metrics driver ("prometheus", "pushgateway",
                    "azure_monitor", "noop")
        driver_config: DriverConfig instance with driver-specific configuration.
                      See individual collector classes for supported options.

    Returns:
        MetricsCollector instance configured for the specified driver

    Raises:
        ValueError: If driver_name is unknown
        ImportError: If required packages for the driver are not installed

    Examples:
        >>> from copilot_config import load_driver_config
        >>> # Create Prometheus collector
        >>> driver_config = load_driver_config(
        ...     None, "metrics", "prometheus",
        ...     fields={"namespace": "myapp", "raise_on_error": False}
        ... )
        >>> collector = create_metrics_collector(
        ...     driver_name="prometheus",
        ...     driver_config=driver_config
        ... )

        >>> # Create no-op collector
        >>> noop_config = load_driver_config(None, "metrics", "noop")
        >>> collector = create_metrics_collector(
        ...     driver_name="noop",
        ...     driver_config=noop_config
        ... )
    """
    driver_name_lower = driver_name.lower()

    if driver_name_lower == "prometheus":
        from .prometheus_metrics import PrometheusMetricsCollector
        return PrometheusMetricsCollector.from_config(driver_config)

    elif driver_name_lower in ("prometheus_pushgateway", "pushgateway"):
        from .pushgateway_metrics import PrometheusPushGatewayMetricsCollector
        return PrometheusPushGatewayMetricsCollector.from_config(driver_config)

    elif driver_name_lower in ("azure_monitor", "azuremonitor"):
        from .azure_monitor_metrics import AzureMonitorMetricsCollector
        return AzureMonitorMetricsCollector.from_config(driver_config)

    elif driver_name_lower == "noop":
        from .noop_metrics import NoOpMetricsCollector
        return NoOpMetricsCollector.from_config(driver_config)

    else:
        raise ValueError(
            f"Unknown metrics driver: {driver_name}. "
            f"Supported drivers: prometheus, pushgateway, azure_monitor, noop"
        )
