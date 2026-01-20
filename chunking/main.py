# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Chunking Service: Split long email bodies into semantically coherent chunks."""

import threading
from dataclasses import replace
from pathlib import Path
from typing import cast

import uvicorn
from app import __version__
from app.service import ChunkingService
from copilot_chunking import create_chunker
from copilot_config.generated.adapters.event_retry import (
    DriverConfig_EventRetry_Default,
    DriverConfig_EventRetry_Noop,
)
from copilot_config.generated.adapters.message_bus import (
    DriverConfig_MessageBus_AzureServiceBus,
    DriverConfig_MessageBus_Rabbitmq,
)
from copilot_config.generated.adapters.metrics import (
    DriverConfig_Metrics_AzureMonitor,
    DriverConfig_Metrics_Prometheus,
    DriverConfig_Metrics_Pushgateway,
)
from copilot_config.generated.services.chunking import ServiceConfig_Chunking
from copilot_config.runtime_loader import get_config
from copilot_error_reporting import create_error_reporter
from copilot_event_retry import RetryConfig
from copilot_logging import (
    create_logger,
    create_stdout_logger,
    create_uvicorn_log_config,
    get_logger,
    set_default_logger,
)
from copilot_message_bus import create_publisher, create_subscriber
from copilot_metrics import create_metrics_collector
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store
from fastapi import FastAPI

# Bootstrap logger for early initialization (before config is loaded)
logger = create_stdout_logger(level="INFO", name="chunking")
set_default_logger(logger)

# Create FastAPI app
app = FastAPI(title="Chunking Service", version=__version__)

# Global service instance
chunking_service: ChunkingService | None = None
subscriber_thread: threading.Thread | None = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global chunking_service
    global subscriber_thread

    stats = chunking_service.get_stats() if chunking_service is not None else {}
    
    # Check if subscriber thread is alive
    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()
    
    # Service is only healthy if subscriber thread is running
    status = "healthy" if subscriber_alive else "unhealthy"

    return {
        "status": status,
        "service": "chunking",
        "version": __version__,
        "chunks_created_total": stats.get("chunks_created_total", 0),
        "messages_processed_total": stats.get("messages_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        "subscriber_thread_alive": subscriber_alive,
    }


@app.get("/stats")
def get_stats():
    """Get chunking statistics."""
    global chunking_service

    if not chunking_service:
        return {"error": "Service not initialized"}

    return chunking_service.get_stats()


def start_subscriber_thread(service: ChunkingService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Chunking service instance

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


def main():
    """Main entry point for the chunking service."""
    global chunking_service
    global logger
    global subscriber_thread

    logger.info(f"Starting Chunking Service (version {__version__})")

    try:
        # Load strongly-typed configuration from JSON schemas
        config = cast(ServiceConfig_Chunking, get_config("chunking"))
        logger.info("Configuration loaded successfully")

        # These identities are service-owned constants (not deployment settings).
        # - RabbitMQ: stable queue name (durable) to avoid ephemeral exclusive queues.
        # - Azure Service Bus: stable subscription identity.
        # - Metrics: stable per-service namespace/job label to prevent collisions.
        service_name = "chunking"
        subscriber_queue_name = "json.parsed"

        # Message bus: ensure subscriber identity is set before connect().
        if config.message_bus.message_bus_type == "rabbitmq":
            driver = cast(DriverConfig_MessageBus_Rabbitmq, config.message_bus.driver)
            config.message_bus.driver = replace(driver, queue_name=subscriber_queue_name)
        elif config.message_bus.message_bus_type == "azure_service_bus":
            driver = cast(DriverConfig_MessageBus_AzureServiceBus, config.message_bus.driver)
            config.message_bus.driver = replace(
                driver,
                topic_name="copilot.events",
                subscription_name=service_name,
            )

        # Metrics: stamp per-service identifier onto driver config.
        if config.metrics.metrics_type == "pushgateway":
            driver = cast(DriverConfig_Metrics_Pushgateway, config.metrics.driver)
            config.metrics.driver = replace(driver, job=service_name, namespace=service_name)
        elif config.metrics.metrics_type == "prometheus":
            driver = cast(DriverConfig_Metrics_Prometheus, config.metrics.driver)
            config.metrics.driver = replace(driver, namespace=service_name)
        elif config.metrics.metrics_type == "azure_monitor":
            driver = cast(DriverConfig_Metrics_AzureMonitor, config.metrics.driver)
            config.metrics.driver = replace(driver, namespace=service_name)

        # Replace bootstrap logger with config-based logger
        logger = create_logger(config.logger)
        set_default_logger(logger)
        logger.info("Logger initialized from service configuration")

        # Refresh module-level service logger to use the current default
        from app import service as chunking_service_module

        chunking_service_module.logger = get_logger(chunking_service_module.__name__)

        # Conditionally add JWT authentication middleware based on config
        if bool(config.service_settings.jwt_auth_enabled):
            logger.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware

                auth_service_url = config.service_settings.auth_service_url or "http://auth:8090"
                audience = config.service_settings.service_audience or "copilot-for-consensus"
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

        logger.info("Creating message bus publisher...")
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

        logger.info("Creating message bus subscriber...")
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

        logger.info("Creating document store...")
        document_schema_provider = create_schema_provider(
            schema_dir=Path(__file__).parent / "docs" / "schemas" / "documents",
            schema_type="documents",
        )
        document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
            schema_provider=document_schema_provider,
        )
        logger.info("Connecting to document store...")
        # connect() raises on failure; None return indicates success
        document_store.connect()
        logger.info("Document store connected successfully")

        # Create chunker via adapter config
        logger.info("Creating chunker from adapter configuration")
        try:
            chunker = create_chunker(config.chunker)
        except Exception as e:
            logger.error(f"Failed to create chunker from adapter config: {e}")
            raise

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector(config.metrics)

        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter(config.error_reporter)

        # Create retry configuration from schematized config
        if config.event_retry.event_retry_type == "noop":
            retry_driver = cast(DriverConfig_EventRetry_Noop, config.event_retry.driver)
        else:
            retry_driver = cast(DriverConfig_EventRetry_Default, config.event_retry.driver)

        retry_config = RetryConfig(
            max_attempts=int(retry_driver.max_attempts),
            base_delay_ms=int(retry_driver.base_delay_ms),
            backoff_factor=float(retry_driver.backoff_factor),
            max_delay_ms=int(retry_driver.max_delay_ms),
            ttl_seconds=int(retry_driver.ttl_seconds),
        )
        logger.info(
            f"Retry configuration: max_attempts={retry_config.max_attempts}, "
            f"base_delay_ms={retry_config.base_delay_ms}, ttl_seconds={retry_config.ttl_seconds}"
        )

        # Create chunking service
        chunking_service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            retry_config=retry_config,
        )

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(chunking_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")

        # Start FastAPI server
        http_port = config.service_settings.http_port if config.service_settings.http_port is not None else 8000
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="chunking", log_level="INFO")
        uvicorn.run(app, host="0.0.0.0", port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start chunking service: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
