# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Metrics collection abstraction for observability.

This package provides a unified interface for collecting metrics across different
observability backends (Prometheus, Azure Monitor, etc.).

Public API:
    - MetricsCollector: Abstract interface for metrics collection
    - create_metrics_collector: Factory function to create collectors

Example:
    >>> from copilot_metrics import create_metrics_collector
    >>> from copilot_config.generated.adapters.metrics import (
    ...     AdapterConfig_Metrics,
    ...     DriverConfig_Metrics_Prometheus,
    ... )
    >>> collector = create_metrics_collector(
    ...     AdapterConfig_Metrics(
    ...         metrics_type="prometheus",
    ...         driver=DriverConfig_Metrics_Prometheus(namespace="myapp"),
    ...     )
    ... )
    >>> collector.increment("requests", value=1.0, tags={"method": "GET"})
"""

__version__ = "0.1.0"

# Core public API - always available
from .base import MetricsCollector
from .factory import create_metrics_collector

# Public exports
__all__ = [
    "__version__",
    "MetricsCollector",
    "create_metrics_collector",
]
