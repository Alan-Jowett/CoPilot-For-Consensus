# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating metrics collectors."""

import logging
from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_AzureMonitor,
    DriverConfig_Metrics_Noop,
    DriverConfig_Metrics_Prometheus,
    DriverConfig_Metrics_Pushgateway,
)

from .base import MetricsCollector

logger = logging.getLogger(__name__)

_DriverConfig: TypeAlias = (
    DriverConfig_Metrics_Prometheus
    | DriverConfig_Metrics_Pushgateway
    | DriverConfig_Metrics_AzureMonitor
    | DriverConfig_Metrics_Noop
)


def _build_prometheus(config: _DriverConfig) -> MetricsCollector:
    from .prometheus_metrics import PrometheusMetricsCollector

    if not isinstance(config, DriverConfig_Metrics_Prometheus):
        raise TypeError("driver config must be DriverConfig_Metrics_Prometheus")
    return PrometheusMetricsCollector.from_config(config)


def _build_pushgateway(config: _DriverConfig) -> MetricsCollector:
    from .pushgateway_metrics import PrometheusPushGatewayMetricsCollector

    if not isinstance(config, DriverConfig_Metrics_Pushgateway):
        raise TypeError("driver config must be DriverConfig_Metrics_Pushgateway")
    return PrometheusPushGatewayMetricsCollector.from_config(config)


def _build_azure_monitor(config: _DriverConfig) -> MetricsCollector:
    from .azure_monitor_metrics import AzureMonitorMetricsCollector

    if not isinstance(config, DriverConfig_Metrics_AzureMonitor):
        raise TypeError("driver config must be DriverConfig_Metrics_AzureMonitor")
    return AzureMonitorMetricsCollector.from_config(config)


def _build_noop(config: _DriverConfig) -> MetricsCollector:
    from .noop_metrics import NoOpMetricsCollector

    if not isinstance(config, DriverConfig_Metrics_Noop):
        raise TypeError("driver config must be DriverConfig_Metrics_Noop")
    return NoOpMetricsCollector.from_config(config)


def create_metrics_collector(
    config: AdapterConfig_Metrics,
) -> MetricsCollector:
    """Create a metrics collector based on driver type.

    Factory function that creates the appropriate metrics collector implementation
    based on the discriminant in the typed adapter config.

    Supported drivers:
    - "prometheus": Prometheus metrics with registry-based collection
    - "pushgateway" or "prometheus_pushgateway": Prometheus with Pushgateway support
    - "azure_monitor" or "azuremonitor": Azure Monitor via OpenTelemetry
    - "noop": No-op collector for testing

    Args:
        config: Typed AdapterConfig_Metrics instance.

    Returns:
        MetricsCollector instance configured for the specified driver

    Raises:
        ValueError: If config is missing or driver type is unknown
        ImportError: If required packages for the driver are not installed

    Examples:
        >>> from copilot_config.generated.adapters.metrics import (
        ...     AdapterConfig_Metrics,
        ...     DriverConfig_Metrics_Noop,
        ... )
        >>> collector = create_metrics_collector(
        ...     AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop())
        ... )
    """
    return create_adapter(
        config,
        adapter_name="metrics",
        get_driver_type=lambda c: c.metrics_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "prometheus": _build_prometheus,
            "pushgateway": _build_pushgateway,
            "azure_monitor": _build_azure_monitor,
            "noop": _build_noop,
        },
    )
