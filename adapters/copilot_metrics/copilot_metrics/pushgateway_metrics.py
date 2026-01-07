# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Prometheus Pushgateway metrics collector implementation."""

import logging
import os

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

        if not gateway:
            raise ValueError("gateway is required for PrometheusPushGatewayMetricsCollector")
        if not job:
            raise ValueError("job is required for PrometheusPushGatewayMetricsCollector")

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
