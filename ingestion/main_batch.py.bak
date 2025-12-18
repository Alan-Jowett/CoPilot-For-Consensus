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
from copilot_storage import (
    create_document_store,
    ValidatingDocumentStore,
    DocumentStoreConnectionError,
)
from copilot_config.providers import DocStoreConfigProvider

from app import __version__
from app.service import IngestionService, _enabled_sources

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_logger(logger_type="stdout", level="INFO", name="ingestion-bootstrap")


class _ConfigWithSources:
    """Wrapper that adds sources to the loaded config without modifying it."""
    
    def __init__(self, base_config: object, sources: list):
        self._base_config = base_config
        self.sources = sources

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent runtime mutation to keep config immutable."""
        if name in ("_base_config", "sources"):
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(
                f"Cannot modify configuration. '{name}' is read-only."
            )
    
    def __getattr__(self, name: str) -> object:
        if name in ("_base_config", "sources"):
            return object.__getattribute__(self, name)
        return getattr(self._base_config, name)


def main():
    """Main entry point for the ingestion service."""
    log = bootstrap_logger
    log.info("Starting Ingestion Service", version=__version__)

    try:
        # Load configuration using adapter (env + defaults validated by schema)
        config = load_typed_config("ingestion")
        
        # Load sources from document store (storage-backed config)
        # Note: SchemaConfigLoader no longer supports storage-backed sources,
        # so we load them explicitly here and pass separately to IngestionService.
        sources = []
        try:
            # Create a temporary document store to load sources
            temp_store = create_document_store(
                store_type=config.doc_store_type,
                host=config.doc_store_host,
                port=config.doc_store_port,
                database=config.doc_store_name,
                username=config.doc_store_user,
                password=config.doc_store_password,
            )
            temp_store.connect()
            
            doc_store_provider = DocStoreConfigProvider(temp_store)
            sources = doc_store_provider.query_documents_from_collection("sources") or []
            
            temp_store.disconnect()
            log.info(
                "Sources loaded from document store",
                source_count=len(sources),
            )
        except Exception as e:
            log.warning(
                "Failed to load sources from document store; using empty list",
                error=str(e),
            )

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
        try:
            base_publisher.connect()
        except Exception as e:
            if str(config.message_bus_type).lower() != "noop":
                log.error(
                    "Failed to connect to message bus. Failing fast as message_bus_type is not noop.",
                    host=config.message_bus_host,
                    port=config.message_bus_port,
                    message_bus_type=config.message_bus_type,
                )
                # Raise ConnectionError to signal publisher connection failure
                raise ConnectionError("Publisher failed to connect to message bus")
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

        # Create document store
        log.info(
            "Creating document store",
            doc_store_type=config.doc_store_type,
            doc_store_host=config.doc_store_host,
            doc_store_port=config.doc_store_port,
        )
        base_document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user,
            password=config.doc_store_password,
        )

        # Connect to document store
        try:
            base_document_store.connect()
        except DocumentStoreConnectionError as e:
            if str(config.doc_store_type).lower() != "inmemory":
                log.error(
                    "Failed to connect to document store. Failing fast as doc_store_type is not inmemory.",
                    host=config.doc_store_host,
                    port=config.doc_store_port,
                    doc_store_type=config.doc_store_type,
                    error=str(e),
                )
                raise
            log.warning(
                "Failed to connect to document store. Continuing with inmemory store.",
                host=config.doc_store_host,
                port=config.doc_store_port,
                error=str(e),
            )

        # Wrap document store with validation layer
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=schema_provider,
            strict=False,  # Log validation warnings but don't raise
        )
        log.info("Document store configured with schema validation")

        # Create config wrapper that includes sources
        config_with_sources = _ConfigWithSources(config, sources)

        # Create ingestion service
        service = IngestionService(
            config_with_sources,
            publisher,
            document_store=document_store,
            logger=log,
            metrics=metrics,
        )

        # Ingest from all enabled sources
        log.info(
            "Starting ingestion for enabled sources",
            enabled_source_count=len(_enabled_sources(sources)),
        )

        results = service.ingest_all_enabled_sources()

        # Log results
        for source_name, exception in results.items():
            if exception is None:
                status = "SUCCESS"
                log.info("Source ingestion summary", source_name=source_name, status=status)
            else:
                status = "FAILED"
                log.error(
                    "Source ingestion summary",
                    source_name=source_name,
                    status=status,
                    error=str(exception),
                    error_type=type(exception).__name__,
                )

        # Count successes (None values indicate success)
        successful = sum(1 for exc in results.values() if exc is None)
        log.info(
            "Ingestion complete",
            successful_sources=successful,
            total_sources=len(results),
        )

        # Cleanup
        base_publisher.disconnect()
        base_document_store.disconnect()

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
