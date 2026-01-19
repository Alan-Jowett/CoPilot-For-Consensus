# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""No-op metrics collector for testing and local development."""

import logging

from copilot_config.generated.adapters.metrics import DriverConfig_Metrics_Noop

from .base import MetricsCollector

logger = logging.getLogger(__name__)


class NoOpMetricsCollector(MetricsCollector):
    """No-op metrics collector that stores metrics in memory without external dependencies.

    Useful for:
    - Testing and local development
    - Environments where metrics collection is not needed
    - Debugging metrics instrumentation

    Stores all metrics calls in memory for testing/inspection purposes.
    """

    def __init__(self, **kwargs):
        """Initialize no-op metrics collector.

        Args:
            **kwargs: Ignored (for compatibility with factory method)
        """
        del kwargs
        self.counters: list[tuple[str, float, dict[str, str] | None]] = []
        self.observations: list[tuple[str, float, dict[str, str] | None]] = []
        self.gauges: list[tuple[str, float, dict[str, str] | None]] = []

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Store counter increment in memory.

        Args:
            name: Name of the counter metric
            value: Amount to increment by (default: 1.0)
            tags: Optional dictionary of tags/labels for the metric
        """
        self.counters.append((name, value, tags))
        logger.debug(f"NoOpMetricsCollector: increment {name} by {value} with tags {tags}")

    def observe(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Store observation in memory.

        Args:
            name: Name of the histogram/summary metric
            value: Value to observe
            tags: Optional dictionary of tags/labels for the metric
        """
        self.observations.append((name, value, tags))
        logger.debug(f"NoOpMetricsCollector: observe {name} value {value} with tags {tags}")

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Store gauge value in memory.

        Args:
            name: Name of the gauge metric
            value: Value to set the gauge to
            tags: Optional dictionary of tags/labels for the metric
        """
        self.gauges.append((name, value, tags))
        logger.debug(f"NoOpMetricsCollector: gauge {name} set to {value} with tags {tags}")

    def clear_metrics(self) -> None:
        """Clear all stored metrics (useful for testing)."""
        self.counters.clear()
        self.observations.clear()
        self.gauges.clear()

    def get_counter_total(self, name: str, tags: dict[str, str] | None = None) -> float:
        """Get total value of a counter metric.

        Args:
            name: Name of the counter metric
            tags: Optional tags to filter by (if None, sums all matching names)

        Returns:
            Total counter value
        """
        total = 0.0
        for counter_name, value, counter_tags in self.counters:
            if counter_name == name:
                if tags is None or counter_tags == tags:
                    total += value
        return total

    def get_observations(self, name: str, tags: dict[str, str] | None = None) -> list[float]:
        """Get all observed values for a metric.

        Args:
            name: Name of the histogram/summary metric
            tags: Optional tags to filter by

        Returns:
            List of observed values
        """
        return [
            value
            for obs_name, value, obs_tags in self.observations
            if obs_name == name and (tags is None or obs_tags == tags)
        ]

    def get_gauge_value(self, name: str, tags: dict[str, str] | None = None) -> float | None:
        """Get the most recent value of a gauge metric.

        Args:
            name: Name of the gauge metric
            tags: Optional tags to filter by

        Returns:
            Most recent gauge value, or None if not found
        """
        matching_gauges = [
            value
            for gauge_name, value, gauge_tags in self.gauges
            if gauge_name == name and (tags is None or gauge_tags == tags)
        ]
        return matching_gauges[-1] if matching_gauges else None

    @classmethod
    def from_config(cls, driver_config: DriverConfig_Metrics_Noop) -> "NoOpMetricsCollector":
        """Create a NoOpMetricsCollector from configuration.

        Args:
            driver_config: Typed driver config (currently ignored, for consistency)

        Returns:
            Configured NoOpMetricsCollector instance
        """
        del driver_config
        return cls()
