# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Metrics SDK.

A shared library for metrics collection across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .metrics import MetricsCollector, create_metrics_collector
from .noop_metrics import NoOpMetricsCollector
from .prometheus_metrics import PrometheusMetricsCollector

__all__ = [
    # Version
    "__version__",
    # Metrics
    "MetricsCollector",
    "NoOpMetricsCollector",
    "PrometheusMetricsCollector",
    "create_metrics_collector",
]
