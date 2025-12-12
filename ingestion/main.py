# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Fetch mailing list archives from various sources."""

import os
import sys
import time

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from copilot_config import load_typed_config
from copilot_events import create_publisher, ValidatingEventPublisher
from copilot_logging import create_logger
from copilot_schema_validation import FileSchemaProvider
from copilot_metrics import create_metrics_collector

from app import __version__
from app.service import IngestionService, _enabled_sources

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_logger(name="ingestion-bootstrap")


def main():
    """Main entry point for the ingestion service."""
    log = bootstrap_logger
    log.info("Starting Ingestion Service", version=__version__)

    try:
        # Load configuration using adapter (env + defaults validated by schema)
        config = load_typed_config("ingestion")

        # Recreate logger with configured settings
        service_logger = create_logger(
            logger_type=config.log_type,
            level=config.log_level,
            name=config.logger_name,
        )

        metrics_backend = config.metrics_backend.lower()

        # Build metrics collector, fall back to NoOp if backend unavailable
        try:
            metrics = create_metrics_collector(backend=config.metrics_backend)
        except Exception as e:  # graceful fallback for missing optional deps
            from copilot_metrics import NoOpMetricsCollector

            service_logger.warning(
                "Metrics backend unavailable; falling back to NoOp",
                backend=config.metrics_backend,
                error=str(e),
            )
            metrics = NoOpMetricsCollector()

        log = service_logger

        log.info(
            "Logger configured",
            log_level=config.log_level,
            log_type=config.log_type,
            metrics_backend=config.metrics_backend,
        )

        # Start Prometheus metrics endpoint when enabled so Prometheus can scrape /metrics
        if metrics_backend == "prometheus":
            try:
                from prometheus_client import start_http_server

                metrics_port = int(os.getenv("METRICS_PORT", "8000"))
                start_http_server(metrics_port)
                log.info("Prometheus metrics server started", port=metrics_port)
            except Exception as e:
                log.warning(
                    "Failed to start Prometheus metrics server",
                    metrics_backend=config.metrics_backend,
                    error=str(e),
                )

        # Ensure storage path exists
        IngestionService._ensure_storage_path(config.storage_path)
        log.info("Storage path prepared", storage_path=config.storage_path)

        # Create event publisher
        base_publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )

        # Connect publisher
        if not base_publisher.connect():
            if str(config.message_bus_type).lower() != "noop":
                log.error(
                    "Failed to connect to message bus. Failing fast as message_bus_type is not noop.",
                    host=config.message_bus_host,
                    port=config.message_bus_port,
                    message_bus_type=config.message_bus_type,
                )
                # Exit with non-zero to signal container/startup failure
                raise SystemExit(1)
            else:
                log.warning(
                    "Failed to connect to message bus. Continuing with noop publisher.",
                    host=config.message_bus_host,
                    port=config.message_bus_port,
                )

        # Wrap publisher with validation layer
        # This ensures all published events are validated against their schemas
        schema_provider = FileSchemaProvider()
        publisher = ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,  # Raise ValidationError if event doesn't match schema
        )
        log.info("Event publisher configured with schema validation")

        # Create ingestion service
        service = IngestionService(
            config,
            publisher,
            logger=log,
            metrics=metrics,
        )

        # Ingest from all enabled sources
        log.info(
            "Starting ingestion for enabled sources",
            enabled_source_count=len(_enabled_sources(getattr(config, "sources", []))),
        )

        results = service.ingest_all_enabled_sources()

        # Log results
        for source_name, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            log.info("Source ingestion summary", source_name=source_name, status=status)

        # Count successes
        successful = sum(1 for s in results.values() if s)
        log.info(
            "Ingestion complete",
            successful_sources=successful,
            total_sources=len(results),
        )

        # Cleanup
        base_publisher.disconnect()

        # Push metrics to Pushgateway for short-lived jobs
        is_pushgateway_backend = metrics_backend in ("prometheus_pushgateway", "pushgateway")
        # Prefer explicit capability check over hasattr; see MetricsCollector.can_push
        if is_pushgateway_backend and getattr(metrics, "can_push", False):
            try:
                metrics.push()
                log.info(
                    "Pushed metrics to Prometheus Pushgateway",
                    metrics_backend=metrics_backend,
                    gateway=getattr(metrics, "gateway", None),
                    job=getattr(metrics, "job", None),
                )
            except Exception as e:
                log.warning(
                    "Failed to push metrics to Prometheus Pushgateway",
                    metrics_backend=metrics_backend,
                    error=str(e),
                )

        # Optional grace period so Prometheus can scrape metrics before exit
        scrape_wait = int(os.getenv("METRICS_SCRAPE_WAIT_SECONDS", "0"))
        if scrape_wait > 0 and not is_pushgateway_backend:
            log.info("Waiting for Prometheus scrape window", seconds=scrape_wait)
            time.sleep(scrape_wait)

        # Exit with appropriate code
        sys.exit(0 if successful == len(results) else 1)

    except Exception as e:
        log.error("Fatal error in ingestion service", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
