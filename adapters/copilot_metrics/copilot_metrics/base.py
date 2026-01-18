# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base abstraction for metrics collection."""

import logging
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class _Pushable(Protocol):
    """Protocol for collectors that support push."""

    def push(self) -> None: ...


class MetricsCollector(ABC):
    """Abstract base class for metrics collectors.

    Provides a pluggable interface for collecting metrics across different
    observability backends (Prometheus, OpenTelemetry, StatsD, etc.).
    """

    @abstractmethod
    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter metric.

        Args:
            name: Name of the counter metric
            value: Amount to increment by (default: 1.0)
            tags: Optional dictionary of tags/labels for the metric
        """
        pass

    @abstractmethod
    def observe(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Observe a value for histogram/summary metrics.

        Useful for measuring durations, sizes, or other distributions.

        Args:
            name: Name of the histogram/summary metric
            value: Value to observe
            tags: Optional dictionary of tags/labels for the metric
        """
        pass

    @abstractmethod
    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge metric to a specific value.

        Gauges represent values that can go up or down (e.g., queue depth, memory usage).

        Args:
            name: Name of the gauge metric
            value: Value to set the gauge to
            tags: Optional dictionary of tags/labels for the metric
        """
        pass

    def safe_push(self) -> None:
        """Safely push metrics to backend if supported.

        This is a helper method that checks if the collector supports pushing
        (e.g., PushGateway) and pushes metrics if available. If push fails,
        logs a warning but does not raise an exception.

        This method is designed to be called after collecting metrics to ensure
        they are sent to the monitoring backend without failing the service.
        """
        if isinstance(self, _Pushable):
            try:
                self.push()
            except Exception as e:
                logger.warning(f"Failed to push metrics: {e}")
