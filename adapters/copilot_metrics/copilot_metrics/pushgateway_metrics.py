# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Prometheus Pushgateway metrics collector implementation."""

import logging
import os

from copilot_config import DriverConfig

from .prometheus_metrics import PrometheusMetricsCollector

logger = logging.getLogger(__name__)

# Import prometheus_client with graceful fallback
try:
    from prometheus_client import CollectorRegistry, push_to_gateway
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed. Install with: pip install prometheus-client")


class PrometheusPushGatewayMetricsCollector(PrometheusMetricsCollector):
    """Prometheus metrics collector that pushes to a Pushgateway.

    Uses a dedicated registry so we only push ingestion-specific metrics and
    avoid leaking default process metrics.
    """
    # Hint for runtimes that feature-detect push capability
    can_push: bool = True

    def __init__(
        self,
        gateway: str | None = None,
        job: str | None = None,
        grouping_key: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """Initialize Prometheus Pushgateway metrics collector.

        Args:
            gateway: Pushgateway URL (e.g., "pushgateway:9091" or "http://pushgateway:9091")
                     Required parameter - must be explicitly provided
            job: Job name for metrics (e.g., "ingestion", "orchestrator")
                 Required parameter - must be explicitly provided
            grouping_key: Optional grouping key dict for metric grouping
            **kwargs: Additional arguments passed to PrometheusMetricsCollector

        Raises:
            ImportError: If prometheus_client is not installed
            ValueError: If gateway or job is not provided
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus_client is required for PrometheusPushGatewayMetricsCollector. "
                "Install with: pip install prometheus-client"
            )

        # Use a dedicated registry by default to keep pushed metrics scoped
        registry = kwargs.pop("registry", CollectorRegistry())

        super().__init__(registry=registry, **kwargs)

        self.gateway = gateway
        if not self.gateway.startswith("http"):
            self.gateway = f"http://{self.gateway}"

        self.job = job
        self.grouping_key = grouping_key or {}

    def push(self) -> None:
        """Push collected metrics to the configured Pushgateway."""
        try:
            push_to_gateway(
                self.gateway,
                job=self.job,
                registry=self.registry,
                grouping_key=self.grouping_key,
            )
            logger.debug(
                "Pushed metrics to Pushgateway",
                extra={"gateway": self.gateway, "job": self.job, "grouping_key": self.grouping_key},
            )
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error("Failed to push metrics to Pushgateway: %s", e)
            raise

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "PrometheusPushGatewayMetricsCollector":
        """Create a PrometheusPushGatewayMetricsCollector from configuration.

        Args:
            driver_config: DriverConfig instance with required attributes:
                - gateway: Pushgateway URL (e.g., "pushgateway:9091")
                - job: Job name for metrics
                Optional attributes:
                - grouping_key: Optional grouping key dict (default: None)
                - namespace: Namespace prefix (default: "copilot")
                - raise_on_error: Whether to raise on metric errors (default: False)

        Returns:
            Configured PrometheusPushGatewayMetricsCollector instance

        Raises:
            ImportError: If prometheus_client is not installed
            ValueError: If gateway or job is not provided
        """
        return cls(
            gateway=driver_config.gateway,
            job=driver_config.job,
            grouping_key=driver_config.grouping_key,
            namespace=driver_config.namespace,
            raise_on_error=driver_config.raise_on_error
        )
