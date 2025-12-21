# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Metrics Adapter.

A shared library for metrics collection across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .metrics import MetricsCollector, create_metrics_collector
from .noop_metrics import NoOpMetricsCollector

# Lazy import for PrometheusMetricsCollector to avoid ImportError when prometheus_client is not installed
try:
    from .prometheus_metrics import PrometheusMetricsCollector
    _prometheus_available = True
except ImportError:
    _prometheus_available = False
    # PrometheusMetricsCollector will be available through factory but not as direct import

# Lazy import for PrometheusPushGatewayMetricsCollector
try:
    from .pushgateway_metrics import PrometheusPushGatewayMetricsCollector
    _pushgateway_available = True
except ImportError:
    _pushgateway_available = False
    # Available through factory when prometheus_client is installed

# Lazy import for AzureMonitorMetricsCollector
try:
    from .azure_monitor_metrics import AzureMonitorMetricsCollector
    _azure_monitor_available = True
except ImportError:
    _azure_monitor_available = False
    # Available through factory when azure-monitor packages are installed

__all__ = [
    # Version
    "__version__",
    # Metrics
    "MetricsCollector",
    "NoOpMetricsCollector",
    "create_metrics_collector",
]

# Only export PrometheusMetricsCollector if it's available
if _prometheus_available:
    __all__.append("PrometheusMetricsCollector")

if _pushgateway_available:
    __all__.append("PrometheusPushGatewayMetricsCollector")

if _azure_monitor_available:
    __all__.append("AzureMonitorMetricsCollector")
