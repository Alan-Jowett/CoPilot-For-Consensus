# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Parsing Service: Convert raw .mbox files into structured JSON."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from copilot_config import load_service_config, load_driver_config
from copilot_message_bus import (
    create_publisher,
    create_subscriber,
)
from copilot_logging import create_logger, create_uvicorn_log_config, get_logger, set_default_logger
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider, get_configuration_schema_response
from copilot_storage import create_document_store
from copilot_archive_store import create_archive_store
from fastapi import FastAPI, HTTPException

# Configure structured JSON logging
bootstrap_logger_config = load_driver_config(service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": "parsing-bootstrap"})
bootstrap_logger = create_logger("stdout", bootstrap_logger_config)
set_default_logger(bootstrap_logger)

from app import __version__
from app.service import ParsingService
logger = bootstrap_logger

# Create FastAPI app
app = FastAPI(title="Parsing Service", version=__version__)

# Global service instance
parsing_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global parsing_service

    stats = parsing_service.get_stats() if parsing_service is not None else {}

    return {
        "status": "healthy",
        "service": "parsing",
        "version": __version__,
        "messages_parsed_total": stats.get("messages_parsed", 0),
        "threads_created_total": stats.get("threads_created", 0),
        "archives_processed_total": stats.get("archives_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


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
        logger.error("Failed to load configuration schema: %s", exc, exc_info=True)
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


def main():
    """Main entry point for the parsing service."""
    global parsing_service

    log = bootstrap_logger
    log.info(f"Starting Parsing Service (version {__version__})")

    try:
        # Load configuration using schema-driven service config
        config = load_service_config("parsing")
        log.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        if config.jwt_auth_enabled:
            log.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                auth_service_url = getattr(config, 'auth_service_url', None)
                audience = getattr(config, 'service_audience', None)
                auth_middleware = create_jwt_middleware(
                    auth_service_url=auth_service_url,
                    audience=audience,
                    required_roles=["processor"],
                    public_paths=["/health", "/readyz", "/docs", "/openapi.json"],
                )
                app.add_middleware(auth_middleware)
            except ImportError:
                log.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            log.warning("JWT authentication is DISABLED - all endpoints are public")

        # Replace bootstrap logger with config-based logger
        logger_adapter = config.get_adapter("logger")
        if logger_adapter is not None:
            log = create_logger(
                driver_name=logger_adapter.driver_name,
                driver_config=logger_adapter.driver_config
            )
            set_default_logger(log)
            log.info("Logger initialized from service configuration")
        else:
            set_default_logger(bootstrap_logger)
            log.warning("No logger adapter found, keeping bootstrap logger")

        # Refresh module-level service logger to use the current default
        from app import service as parsing_service_module
        parsing_service_module.logger = get_logger(parsing_service_module.__name__)

        # Create event publisher with schema validation
        log.info("Creating event publisher from adapter configuration")
        message_bus_adapter = config.get_adapter("message_bus")
        if message_bus_adapter is None:
            raise ValueError("message_bus adapter is required")

        publisher = create_publisher(
            driver_name=message_bus_adapter.driver_name,
            driver_config=message_bus_adapter.driver_config,
            enable_validation=True,
            strict_validation=True,
        )

        try:
            publisher.connect()
        except Exception as e:
            if str(config.message_bus_type).lower() != "noop":
                log.error("Failed to connect publisher to message bus. Failing fast: %s", e)
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                log.warning("Failed to connect publisher to message bus. Continuing with noop publisher: %s", e)

        # Create event subscriber with built-in schema validation
        log.info("Creating event subscriber from adapter configuration")
        # Add queue_name to subscriber config
        from copilot_config import DriverConfig
        subscriber_config = {**message_bus_adapter.driver_config.config, "queue_name": "archive.ingested"}
        subscriber_driver_config = DriverConfig(
            driver_name=message_bus_adapter.driver_name,
            config=subscriber_config,
            allowed_keys=message_bus_adapter.driver_config.allowed_keys
        )
        subscriber = create_subscriber(
            driver_name=message_bus_adapter.driver_name,
            driver_config=subscriber_driver_config,
            enable_validation=True,
            strict_validation=True,
        )

        try:
            subscriber.connect()
        except Exception as e:
            log.error("Failed to connect subscriber to message bus: %s", e)
            raise ConnectionError("Subscriber failed to connect to message bus")

        # Create document store with schema validation
        log.info("Creating document store from adapter configuration")
        document_store_adapter = config.get_adapter("document_store")
        if document_store_adapter is None:
            raise ValueError("document_store adapter is required")

        document_store = create_document_store(
            driver_name=document_store_adapter.driver_name,
            driver_config=document_store_adapter.driver_config,
            enable_validation=True,
            strict_validation=True,
        )

        try:
            document_store.connect()
        except Exception as e:
            log.error(f"Failed to connect to document store: {e}")
            raise  # Re-raise the original exception

        # Create metrics collector - fail fast on errors
        log.info("Creating metrics collector...")
        from copilot_config import DriverConfig
        metrics_adapter = config.get_adapter("metrics")
        if metrics_adapter is not None:
            # Metrics adapter is configured - initialization MUST succeed
            metrics_driver_config = DriverConfig(
                driver_name=metrics_adapter.driver_name,
                config={**metrics_adapter.driver_config.config, "job": "parsing"},
                allowed_keys=metrics_adapter.driver_config.allowed_keys
            )
            metrics_collector = create_metrics_collector(
                driver_name=metrics_adapter.driver_name,
                driver_config=metrics_driver_config,
            )
        else:
            # No metrics adapter configured - use noop
            metrics_collector = create_metrics_collector(
                driver_name="noop",
                driver_config=DriverConfig(driver_name="noop")
            )

        # Create error reporter using adapter configuration (optional)
        log.info("Creating error reporter...")
        error_reporter_adapter = config.get_adapter("error_reporter")
        if error_reporter_adapter is not None:
            error_reporter = create_error_reporter(
                driver_name=error_reporter_adapter.driver_name,
                driver_config=error_reporter_adapter.driver_config,
            )
        else:
            error_reporter = create_error_reporter(
                driver_name="silent",
                driver_config={"logger_name": config.logger_name},
            )

        # Create archive store from adapter configuration (required)
        log.info("Creating archive store from adapter configuration...")
        archive_store_adapter = config.get_adapter("archive_store")
        if archive_store_adapter is None:
            raise ValueError("archive_store adapter is required")

        archive_store = create_archive_store(
            driver_name=archive_store_adapter.driver_name,
            driver_config=archive_store_adapter.driver_config,
        )

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
        log.info(f"Starting FastAPI server on port {config.http_port}")

        # Configure Uvicorn with structured JSON logging
        log_level = "INFO"
        for adapter in config.adapters:
            if adapter.adapter_type == "logger":
                log_level = adapter.driver_config.config.get("level", "INFO")
                break
        log_config = create_uvicorn_log_config(service_name="parsing", log_level=log_level)
        uvicorn.run(app, host=config.http_host, port=config.http_port, log_config=log_config, access_log=False)

    except KeyboardInterrupt:
        log.info("Shutting down parsing service")
    except Exception as e:
        log.error(f"Fatal error in parsing service: {e}", exc_info=True)
        sys.exit(1)
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
