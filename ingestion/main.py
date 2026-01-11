# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Continuous service for managing and ingesting mailing list archives."""

import os
import signal
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from app import __version__
from app.api import create_api_router
from app.scheduler import IngestionScheduler
from app.service import IngestionService
from copilot_config import load_service_config, load_driver_config, DriverConfig
from copilot_message_bus import create_publisher
from copilot_logging import create_logger, create_stdout_logger, create_uvicorn_log_config
from copilot_metrics import create_metrics_collector
from copilot_schema_validation import create_schema_provider
from copilot_storage import (
    DocumentStoreConnectionError,
    create_document_store,
)
from copilot_archive_store import create_archive_store
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_stdout_logger(level="INFO", name="ingestion-bootstrap")

# Create FastAPI app
app = FastAPI(title="Ingestion Service", version=__version__)


# Global exception handler to log unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log and return JSON for unhandled exceptions."""
    bootstrap_logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"}
    )

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
        # Load configuration using schema-driven service config
        config = load_service_config("ingestion")

        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            log.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                # Use shared audience for all services
                auth_service_url = getattr(config, 'auth_service_url', None)
                audience = getattr(config, 'service_audience', None)
                auth_middleware = create_jwt_middleware(
                    auth_service_url=auth_service_url,
                    audience=audience,
                    required_roles=["admin"],
                    public_paths=["/", "/health", "/readyz", "/docs", "/openapi.json"],
                )
                app.add_middleware(auth_middleware)
            except ImportError:
                log.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            log.warning("JWT authentication is DISABLED - all endpoints are public")

        # Create service logger using logger adapter from config or default stdout
        logger_adapter = config.get_adapter("logger")
        if logger_adapter:
            service_logger = create_logger(
                driver_name=logger_adapter.driver_name,
                driver_config=logger_adapter.driver_config,
            )
        else:
            # Fallback to stdout logger with DriverConfig
            logger_config = load_driver_config(
                service="ingestion",
                adapter="logger",
                driver="stdout",
                fields={"level": "INFO", "name": "ingestion"},
            )
            service_logger = create_logger(driver_name="stdout", driver_config=logger_config)

        # Build metrics collector, fall back to NoOp if backend unavailable
        try:
            metrics_adapter = config.get_adapter("metrics")
            if metrics_adapter is not None:
                # Create new DriverConfig with modified config dict
                metrics_config = dict(metrics_adapter.driver_config.config)
                metrics_config.setdefault("job", "ingestion")
                metrics_driver_config = DriverConfig(
                    driver_name=metrics_adapter.driver_config.driver_name,
                    config=metrics_config,
                    allowed_keys=metrics_adapter.driver_config.allowed_keys,
                )
                metrics = create_metrics_collector(
                    driver_name=metrics_adapter.driver_name,
                    driver_config=metrics_driver_config,
                )
            else:
                metrics = create_metrics_collector(driver_name="noop")
        except Exception as e:  # graceful fallback for missing optional deps
            from copilot_metrics import NoOpMetricsCollector

            service_logger.warning(
                "Metrics backend unavailable; falling back to NoOp",
                backend=config.metrics_type,
                error=str(e),
            )
            metrics = NoOpMetricsCollector()

        log = service_logger

        log.info("Ingestion service configured and ready")

        # Ensure storage path exists (if configured)
        storage_path = config.storage_path
        IngestionService._ensure_storage_path(storage_path)
        log.info("Storage path prepared", storage_path=storage_path)

        message_bus_adapter = config.get_adapter("message_bus")
        if message_bus_adapter is None:
            raise ValueError("message_bus adapter is required")

        log.info("Creating message bus publisher...")

        # Create new DriverConfig for publisher
        publisher_config = dict(message_bus_adapter.driver_config.config)
        publisher_driver_config = DriverConfig(
            driver_name=message_bus_adapter.driver_config.driver_name,
            config=publisher_config,
            allowed_keys=message_bus_adapter.driver_config.allowed_keys,
        )
        base_publisher = create_publisher(
            driver_name=message_bus_adapter.driver_name,
            driver_config=publisher_driver_config,
        )

        # Connect publisher
        try:
            base_publisher.connect()
        except Exception:
            if message_bus_adapter.driver_name.lower() != "noop":
                log.error(
                    "Failed to connect to message bus. Failing fast as message_bus_type is not noop.",
                    message_bus_type=message_bus_adapter.driver_name,
                )
                # Raise ConnectionError to signal publisher connection failure
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                log.warning(
                    "Failed to connect to message bus. Continuing with noop publisher.",
                    message_bus_type=message_bus_adapter.driver_name,
                )

        # Wrap publisher already handled by factory (defaults to validating)
        publisher = base_publisher
        schema_provider = create_schema_provider()
        log.info("Event publisher configured")

        # Create document store
        log.info("Creating document store from adapter configuration...")
        document_store_adapter = config.get_adapter("document_store")
        if document_store_adapter is None:
            raise ValueError("document_store adapter is required")

        # Create new DriverConfig for document store with schema provider
        document_store_config = dict(document_store_adapter.driver_config.config)
        document_store_config["schema_provider"] = schema_provider
        document_store_driver_config = DriverConfig(
            driver_name=document_store_adapter.driver_config.driver_name,
            config=document_store_config,
            allowed_keys=document_store_adapter.driver_config.allowed_keys,
        )
        base_document_store = create_document_store(
            driver_name=document_store_adapter.driver_name,
            driver_config=document_store_driver_config,
            enable_validation=True,
            strict_validation=True,
        )

        # Connect to document store
        try:
            base_document_store.connect()
        except DocumentStoreConnectionError as e:
            if document_store_adapter.driver_name.lower() != "inmemory":
                log.error(
                    "Failed to connect to document store. Failing fast as doc_store_type is not inmemory.",
                    doc_store_type=document_store_adapter.driver_name,
                    error=str(e),
                )
                raise
            log.warning(
                "Failed to connect to document store. Continuing with inmemory store.",
                error=str(e),
            )

        # Use document store directly (validation handled by create_document_store if enabled)
        document_store = base_document_store
        log.info("Document store configured")

        log.info("Creating archive store from adapter configuration...")
        archive_store_adapter = config.get_adapter("archive_store")
        if archive_store_adapter is None:
            raise ValueError("archive_store adapter is required")

        archive_store = create_archive_store(
            driver_name=archive_store_adapter.driver_name,
            driver_config=archive_store_adapter.driver_config,
        )

        # Get sources from config (empty list if not configured)
        sources = getattr(config, 'sources', [])
        log.info("Ingestion sources loaded", count=len(sources))

        # Create config wrapper that includes sources
        config_with_sources = _ConfigWithSources(config, sources)

        # Create ingestion service
        ingestion_service = IngestionService(
            config_with_sources,
            publisher,
            document_store=document_store,
            logger=log,
            metrics=metrics,
            archive_store=archive_store,
        )
        ingestion_service.version = __version__

        # Mount API routes
        api_router = create_api_router(ingestion_service, log)
        app.include_router(api_router)

        log.info("API routes configured")

        # Create and start scheduler for periodic ingestion
        schedule_interval = config.schedule_interval_seconds
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
        http_port = int(config.http_port)
        http_host = config.http_host
        log.info(f"Starting HTTP server on {http_host}:{http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_level = config.log_level
        log_config = create_uvicorn_log_config(service_name="ingestion", log_level=log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        log.error("Fatal error in ingestion service", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
