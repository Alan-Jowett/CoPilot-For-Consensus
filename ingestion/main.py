# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Continuous service for managing and ingesting mailing list archives."""

import json
import os
import signal
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from copilot_config.runtime_loader import get_config
from copilot_message_bus import create_publisher
from copilot_logging import (
    create_logger,
    create_stdout_logger,
    create_uvicorn_log_config,
    get_logger,
    set_default_logger,
)
from copilot_metrics import create_metrics_collector
from copilot_storage import (
    DocumentStoreConnectionError,
    create_document_store,
)
from copilot_archive_store import create_archive_store
from copilot_error_reporting import create_error_reporter
from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_AzureServiceBus
from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_Rabbitmq
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_stdout_logger(level="INFO", name="ingestion-bootstrap")
set_default_logger(bootstrap_logger)

from app import __version__
from app.api import create_api_router
from app.scheduler import IngestionScheduler
from app.service import IngestionService

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
ingestion_service: IngestionService | None = None
scheduler: IngestionScheduler | None = None
base_publisher = None
base_document_store = None

def _substitute_env_vars(
    value: object,
    *,
    _depth: int = 0,
    _max_depth: int = 50,
    _seen: set[int] | None = None,
) -> object:
    if _depth > _max_depth:
        raise ValueError("Sources config expansion exceeded maximum nesting depth")

    if isinstance(value, str):
        return os.path.expandvars(value)

    if isinstance(value, list):
        if _seen is None:
            _seen = set()
        obj_id = id(value)
        if obj_id in _seen:
            raise ValueError("Sources config expansion detected a cyclic structure")
        _seen.add(obj_id)
        try:
            return [
                _substitute_env_vars(v, _depth=_depth + 1, _max_depth=_max_depth, _seen=_seen)
                for v in value
            ]
        finally:
            _seen.remove(obj_id)

    if isinstance(value, dict):
        if _seen is None:
            _seen = set()
        obj_id = id(value)
        if obj_id in _seen:
            raise ValueError("Sources config expansion detected a cyclic structure")
        _seen.add(obj_id)
        try:
            return {
                k: _substitute_env_vars(v, _depth=_depth + 1, _max_depth=_max_depth, _seen=_seen)
                for k, v in value.items()
            }
        finally:
            _seen.remove(obj_id)

    return value


def _load_sources_from_file(path: Path) -> list[dict]:
    if not path.exists():
        bootstrap_logger.info("Sources config file not found; starting with no sources", path=str(path))
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to read sources config from {path}: {e}") from e

    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(f"Invalid sources config in {path}: 'sources' must be a list")
    expanded = _substitute_env_vars(sources)
    if not isinstance(expanded, list):
        return []
    return [s for s in expanded if isinstance(s, dict)]


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
        # Load typed configuration
        config = get_config("ingestion")

        # Service-owned identity constants (not deployment settings)
        service_name = "ingestion"

        # Message bus identity:
        # - RabbitMQ: use a stable queue name per service.
        # - Azure Service Bus: use topic/subscription (do NOT use queue_name).
        message_bus_type = str(config.message_bus.message_bus_type).lower()
        if message_bus_type == "rabbitmq":
            rabbitmq_cfg = cast(DriverConfig_MessageBus_Rabbitmq, config.message_bus.driver)
            config.message_bus.driver = replace(rabbitmq_cfg, queue_name=service_name)
        elif message_bus_type == "azure_service_bus":
            asb_cfg = cast(DriverConfig_MessageBus_AzureServiceBus, config.message_bus.driver)
            config.message_bus.driver = replace(
                asb_cfg,
                topic_name="copilot.events",
                subscription_name=service_name,
                queue_name=None,
            )

        # Metrics: stamp per-service identifier onto driver config
        if str(config.metrics.metrics_type).lower() == "pushgateway" and hasattr(config.metrics.driver, "job"):
            config.metrics.driver = replace(config.metrics.driver, job=service_name, namespace=service_name)
        elif hasattr(config.metrics.driver, "namespace"):
            config.metrics.driver = replace(config.metrics.driver, namespace=service_name)

        # Conditionally add JWT authentication middleware based on config
        if config.service_settings.jwt_auth_enabled is True:
            log.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                # Use shared audience for all services
                auth_service_url = config.service_settings.auth_service_url
                audience = config.service_settings.service_audience

                if auth_service_url is None or audience is None:
                    raise ValueError(
                        "JWT auth is enabled but auth_service_url/service_audience is missing"
                    )

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

        # Create service logger from typed config
        service_logger = create_logger(config.logger)

        # Set the default logger for the application so any module can use get_logger()
        set_default_logger(service_logger)

        # Refresh module-level service logger to use the current default
        from app import service as ingestion_service_module
        ingestion_service_module.logger = get_logger(ingestion_service_module.__name__)

        metrics = create_metrics_collector(config.metrics)

        error_reporter = create_error_reporter(config.error_reporter)


        log = service_logger

        log.info("Ingestion service configured and ready")

        # Ensure storage path exists (if configured)
        storage_path = config.service_settings.storage_path or "/data/ingestion"
        IngestionService._ensure_storage_path(storage_path)
        log.info("Storage path prepared", storage_path=storage_path)

        log.info("Creating message bus publisher...")

        base_publisher = create_publisher(
            config.message_bus,
            enable_validation=True,
            strict_validation=True,
        )

        # Connect publisher
        try:
            base_publisher.connect()
        except Exception:
            if str(config.message_bus.message_bus_type).lower() != "noop":
                log.error(
                    "Failed to connect to message bus. Failing fast as message_bus_type is not noop.",
                    message_bus_type=config.message_bus.message_bus_type,
                )
                # Raise ConnectionError to signal publisher connection failure
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                log.warning(
                    "Failed to connect to message bus. Continuing with noop publisher.",
                    message_bus_type=config.message_bus.message_bus_type,
                )

        # Wrap publisher already handled by factory (defaults to validating)
        publisher = base_publisher
        log.info("Event publisher configured")

        # Create document store
        log.info("Creating document store from adapter configuration...")
        base_document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
        )

        # Connect to document store
        try:
            base_document_store.connect()
        except DocumentStoreConnectionError as e:
            if str(config.document_store.doc_store_type).lower() != "inmemory":
                log.error(
                    "Failed to connect to document store. Failing fast as doc_store_type is not inmemory.",
                    doc_store_type=config.document_store.doc_store_type,
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
        archive_store = create_archive_store(config.archive_store)

        # Load sources from local config file (optional)
        sources_path = Path(os.environ.get("INGESTION_SOURCES_CONFIG_PATH", Path(__file__).with_name("config.json")))
        sources = _load_sources_from_file(sources_path)
        log.info("Ingestion sources loaded", count=len(sources))

        # Create ingestion service
        ingestion_service = IngestionService(
            config,
            publisher,
            sources=sources,
            document_store=document_store,
            error_reporter=error_reporter,
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
        schedule_interval = (
            config.service_settings.schedule_interval_seconds
            if config.service_settings.schedule_interval_seconds is not None
            else 21600
        )
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
        http_port = (
            int(config.service_settings.http_port)
            if config.service_settings.http_port is not None
            else 8000
        )
        http_host = config.service_settings.http_host or "0.0.0.0"
        log.info(f"Starting HTTP server on {http_host}:{http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_level = "INFO"
        if hasattr(config.logger.driver, "level"):
            log_level = getattr(config.logger.driver, "level") or "INFO"
        log_config = create_uvicorn_log_config(service_name="ingestion", log_level=log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        log.error("Fatal error in ingestion service", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
