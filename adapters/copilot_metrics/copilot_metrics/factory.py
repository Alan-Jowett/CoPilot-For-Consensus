# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating metrics collectors."""

import logging

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics

from .base import MetricsCollector

logger = logging.getLogger(__name__)


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
    from .azure_monitor_metrics import AzureMonitorMetricsCollector
    from .noop_metrics import NoOpMetricsCollector
    from .prometheus_metrics import PrometheusMetricsCollector
    from .pushgateway_metrics import PrometheusPushGatewayMetricsCollector

    return create_adapter(
        config,
        adapter_name="metrics",
        get_driver_type=lambda c: c.metrics_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "prometheus": PrometheusMetricsCollector.from_config,
            "pushgateway": PrometheusPushGatewayMetricsCollector.from_config,
            "azure_monitor": AzureMonitorMetricsCollector.from_config,
            "noop": NoOpMetricsCollector.from_config,
        },
    )
