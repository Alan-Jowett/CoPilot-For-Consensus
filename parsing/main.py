# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Parsing Service: Convert raw .mbox files into structured JSON."""

import threading
from dataclasses import replace
from typing import cast

import uvicorn
from app import __version__
from app.service import ParsingService
from copilot_archive_store import create_archive_store
from copilot_config.generated.adapters.message_bus import (
    DriverConfig_MessageBus_AzureServiceBus,
    DriverConfig_MessageBus_Rabbitmq,
)
from copilot_config.generated.adapters.metrics import (
    DriverConfig_Metrics_AzureMonitor,
    DriverConfig_Metrics_Prometheus,
    DriverConfig_Metrics_Pushgateway,
)
from copilot_config.generated.services.parsing import ServiceConfig_Parsing
from copilot_config.runtime_loader import get_config
from copilot_error_reporting import create_error_reporter
from copilot_logging import (
    create_logger,
    create_stdout_logger,
    create_uvicorn_log_config,
    get_logger,
    set_default_logger,
)
from copilot_message_bus import (
    create_publisher,
    create_subscriber,
)
from copilot_metrics import create_metrics_collector
from copilot_schema_validation import create_schema_provider, get_configuration_schema_response
from copilot_storage import DocumentStoreConnectionError, create_document_store
from fastapi import FastAPI, HTTPException

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_stdout_logger(level="INFO", name="parsing")
set_default_logger(bootstrap_logger)

logger = bootstrap_logger

# Create FastAPI app
app = FastAPI(title="Parsing Service", version=__version__)

# Global service instance
parsing_service = None
subscriber_thread: threading.Thread | None = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global parsing_service
    global subscriber_thread

    stats = parsing_service.get_stats() if parsing_service is not None else {}

    # Check if subscriber thread is alive
    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()

    # Service is only healthy if subscriber thread is running
    status = "unhealthy" if (subscriber_thread is not None and not subscriber_alive) else "healthy"

    return {
        "status": status,
        "service": "parsing",
        "version": __version__,
        "messages_parsed_total": stats.get("messages_parsed", 0),
        "threads_created_total": stats.get("threads_created", 0),
        "archives_processed_total": stats.get("archives_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        "subscriber_thread_alive": subscriber_alive,
    }


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness check endpoint - indicates if service is ready to process requests."""
    global parsing_service
    global subscriber_thread

    # Service is ready only when:
    # 1. Service is initialized
    # 2. Subscriber thread is running
    if parsing_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()
    if not subscriber_alive:
        raise HTTPException(status_code=503, detail="Subscriber thread not running")

    return {"status": "ready", "service": "parsing"}


@app.get("/stats")
def stats():
    """Get parsing statistics."""
    global parsing_service

    if not parsing_service:
        return {"error": "Service not initialized"}

    return parsing_service.get_stats()


@app.get("/.well-known/configuration-schema")
def configuration_schema():
    """Configuration schema discovery endpoint."""
    try:
        return get_configuration_schema_response(
            service_name="parsing",
            service_version=__version__,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Schema not found")
    except Exception as exc:
        logger.error(f"Failed to load configuration schema: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load schema")


def start_subscriber_thread(service: ParsingService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Parsing service instance

    Raises:
        Exception: Re-raises any exception to fail fast
    """
    try:
        service.start()
        # Start consuming events (blocking)
        service.subscriber.start_consuming()
    except KeyboardInterrupt:
        logger.info("Subscriber interrupted")
    except Exception as e:
        logger.error(f"Subscriber error: {e}")
        # Fail fast - re-raise to terminate the service
        raise


def load_service_config() -> ServiceConfig_Parsing:
    return cast(ServiceConfig_Parsing, get_config("parsing"))


def main():
    """Main entry point for the parsing service."""
    global parsing_service
    global logger
    global subscriber_thread

    logger.info(f"Starting Parsing Service (version {__version__})")

    try:
        # Load strongly-typed configuration from JSON schemas
        config = load_service_config()
        logger.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        if bool(config.service_settings.jwt_auth_enabled):
            logger.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware

                auth_service_url = str(config.service_settings.auth_service_url or "http://auth:8090")
                audience = str(config.service_settings.service_audience or "copilot-for-consensus")
                auth_middleware = create_jwt_middleware(
                    auth_service_url=auth_service_url,
                    audience=audience,
                    required_roles=["processor"],
                    public_paths=["/health", "/readyz", "/docs", "/openapi.json"],
                )
                app.add_middleware(auth_middleware)
            except ImportError:
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Replace bootstrap logger with config-based logger
        logger = create_logger(config.logger)
        set_default_logger(logger)
        logger.info("Logger initialized from service configuration")

        # Service-owned identity constants (not deployment settings)
        service_name = "parsing"
        subscriber_queue_name = "archive.ingested"

        # Message bus identity:
        # - RabbitMQ: use a stable queue name per service.
        # - Azure Service Bus: use topic/subscription (do NOT use queue_name).
        message_bus_type = str(config.message_bus.message_bus_type).lower()
        if message_bus_type == "rabbitmq":
            rabbitmq_cfg = cast(DriverConfig_MessageBus_Rabbitmq, config.message_bus.driver)
            config.message_bus.driver = replace(
                rabbitmq_cfg,
                queue_name=subscriber_queue_name,
            )
        elif message_bus_type == "azure_service_bus":
            asb_cfg = cast(DriverConfig_MessageBus_AzureServiceBus, config.message_bus.driver)
            config.message_bus.driver = replace(
                asb_cfg,
                topic_name="copilot.events",
                subscription_name=service_name,
                queue_name=None,
            )

        # Metrics identity: stamp per-service identifier onto driver config
        metrics_type = str(config.metrics.metrics_type).lower()
        if metrics_type == "pushgateway":
            pushgateway_cfg = cast(DriverConfig_Metrics_Pushgateway, config.metrics.driver)
            config.metrics.driver = replace(
                pushgateway_cfg,
                job=service_name,
                namespace=service_name,
            )
        elif metrics_type == "prometheus":
            prometheus_cfg = cast(DriverConfig_Metrics_Prometheus, config.metrics.driver)
            config.metrics.driver = replace(prometheus_cfg, namespace=service_name)
        elif metrics_type == "azure_monitor":
            azure_monitor_cfg = cast(DriverConfig_Metrics_AzureMonitor, config.metrics.driver)
            config.metrics.driver = replace(azure_monitor_cfg, namespace=service_name)

        # Refresh module-level service logger to use the current default
        from app import service as parsing_service_module

        parsing_service_module.logger = get_logger(parsing_service_module.__name__)

        # Create event publisher with schema validation
        logger.info("Creating event publisher...")
        publisher = create_publisher(
            config.message_bus,
            enable_validation=True,
            strict_validation=True,
        )

        try:
            publisher.connect()
        except Exception as e:
            if str(config.message_bus.message_bus_type).lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        # Create event subscriber with built-in schema validation
        logger.info("Creating event subscriber...")
        subscriber = create_subscriber(
            config.message_bus,
            enable_validation=True,
            strict_validation=True,
        )

        try:
            subscriber.connect()
        except Exception as e:
            logger.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        # Create document store with schema validation
        logger.info("Creating document store...")
        document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
            schema_provider=create_schema_provider(schema_type="documents"),
        )

        try:
            document_store.connect()
        except DocumentStoreConnectionError as e:
            logger.error(f"Failed to connect to document store: {e}")
            raise

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector(config.metrics)

        # Create error reporter using adapter configuration (optional)
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter(config.error_reporter)

        # Create archive store from adapter configuration (required)
        logger.info("Creating archive store...")
        archive_store = create_archive_store(config.archive_store)

        # Create parsing service
        parsing_service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            archive_store=archive_store,
        )

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(parsing_service,),
            daemon=False,
        )
        subscriber_thread.start()

        # Start FastAPI server (blocking)
        http_host = str(config.service_settings.http_host or "0.0.0.0")
        http_port = int(config.service_settings.http_port or 8000)
        logger.info(f"Starting FastAPI server on port {http_port}")

        # Configure Uvicorn with structured JSON logging
        log_level = getattr(config.logger.driver, "level", "INFO")
        log_config = create_uvicorn_log_config(service_name="parsing", log_level=log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except KeyboardInterrupt:
        logger.info("Shutting down parsing service")
    except Exception as e:
        logger.error(f"Fatal error in parsing service: {e}", exc_info=True)
        raise SystemExit(1)
    finally:
        # Cleanup
        if parsing_service:
            if parsing_service.subscriber:
                parsing_service.subscriber.disconnect()
            if parsing_service.publisher:
                parsing_service.publisher.disconnect()
            if parsing_service.document_store:
                parsing_service.document_store.disconnect()


if __name__ == "__main__":
    main()
