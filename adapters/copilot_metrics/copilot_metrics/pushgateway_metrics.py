# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Prometheus Pushgateway metrics collector implementation."""

import logging
import os
from typing import Any

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
        **kwargs: Any,
    ) -> None:
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus_client is required for PrometheusPushGatewayMetricsCollector. "
                "Install with: pip install prometheus-client"
            )

        # Use a dedicated registry by default to keep pushed metrics scoped
        registry = kwargs.pop("registry", CollectorRegistry())

        super().__init__(registry=registry, **kwargs)

        self.gateway = gateway or os.getenv("PROMETHEUS_PUSHGATEWAY", "pushgateway:9091")
        if self.gateway and not self.gateway.startswith("http"):
            self.gateway = f"http://{self.gateway}"

        self.job = job or os.getenv("METRICS_JOB_NAME", "ingestion")
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
