# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Continuous service for managing and ingesting mailing list archives."""

import os
import sys
import signal

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
import uvicorn

from copilot_config import load_typed_config
from copilot_events import create_publisher, ValidatingEventPublisher
from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_schema_validation import FileSchemaProvider
from copilot_metrics import create_metrics_collector
from copilot_storage import (
    create_document_store,
    ValidatingDocumentStore,
    DocumentStoreConnectionError,
)
from copilot_config.providers import DocStoreConfigProvider
from copilot_auth import create_jwt_middleware

from app import __version__
from app.service import IngestionService
from app.api import create_api_router
from app.scheduler import IngestionScheduler

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_logger(logger_type="stdout", level="INFO", name="ingestion-bootstrap")

# Create FastAPI app
app = FastAPI(title="Ingestion Service", version=__version__)

# Global service instance and scheduler
ingestion_service = None
scheduler = None
base_publisher = None
base_document_store = None


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


@app.get("/")
def root():
    """Root endpoint redirects to health check."""
    return health()


@app.get("/health")
def health():
    """Health check endpoint."""
    global ingestion_service, scheduler
    
    stats = ingestion_service.get_stats() if ingestion_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "ingestion",
        "version": __version__,
        "scheduler_running": scheduler.is_running() if scheduler else False,
        "sources_configured": stats.get("sources_configured", 0),
        "sources_enabled": stats.get("sources_enabled", 0),
        "total_files_ingested": stats.get("total_files_ingested", 0),
        "last_ingestion_at": stats.get("last_ingestion_at"),
    }


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global scheduler, base_publisher, base_document_store
    logger = bootstrap_logger
    
    logger.info("Received shutdown signal", signal=signum)
    
    if scheduler:
        scheduler.stop()
    
    # Cleanup resources
    if base_publisher:
        try:
            base_publisher.disconnect()
            logger.info("Publisher disconnected")
        except Exception as e:
            logger.warning("Failed to disconnect publisher", error=str(e))
    
    if base_document_store:
        try:
            base_document_store.disconnect()
            logger.info("Document store disconnected")
        except Exception as e:
            logger.warning("Failed to disconnect document store", error=str(e))
    
    sys.exit(0)


def main():
    """Main entry point for the ingestion service."""
    global ingestion_service, scheduler, base_publisher, base_document_store
    
    log = bootstrap_logger
    log.info("Starting Ingestion Service (continuous mode)", version=__version__)

    try:
        # Load configuration using adapter (env + defaults validated by schema)
        config = load_typed_config("ingestion")
        
        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            log.info("JWT authentication is enabled")
            auth_middleware = create_jwt_middleware(
                required_roles=["admin"],
                public_paths=["/", "/health", "/readyz", "/docs", "/openapi.json"],
            )
            app.add_middleware(auth_middleware)
        else:
            log.warning("JWT authentication is DISABLED - all endpoints are public")
        
        # Load sources from document store (storage-backed config)
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
        schema_provider = FileSchemaProvider()
        publisher = ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
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
            strict=False,
        )
        log.info("Document store configured with schema validation")

        # Create config wrapper that includes sources
        config_with_sources = _ConfigWithSources(config, sources)

        # Create ingestion service
        ingestion_service = IngestionService(
            config_with_sources,
            publisher,
            document_store=document_store,
            logger=log,
            metrics=metrics,
        )
        ingestion_service.version = __version__

        # Mount API routes
        api_router = create_api_router(ingestion_service, log)
        app.include_router(api_router)
        
        log.info("API routes configured")

        # Create and start scheduler for periodic ingestion
        schedule_interval = int(os.getenv("INGESTION_SCHEDULE_INTERVAL_SECONDS", "21600"))  # Default: 6 hours
        scheduler = IngestionScheduler(
            service=ingestion_service,
            interval_seconds=schedule_interval,
            logger=log,
        )
        scheduler.start()
        
        log.info(
            "Ingestion scheduler configured and started",
            interval_seconds=schedule_interval,
        )

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8080"))
        http_host = os.getenv("HTTP_HOST", "127.0.0.1")
        log.info(f"Starting HTTP server on {http_host}:{http_port}...")
        
        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="ingestion", log_level=config.log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config)

    except Exception as e:
        log.error("Fatal error in ingestion service", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
