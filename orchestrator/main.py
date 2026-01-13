# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Orchestration Service: Coordinate summarization and analysis tasks."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from copilot_config import load_service_config, load_driver_config
from copilot_message_bus import create_publisher, create_subscriber
from copilot_logging import create_logger, create_uvicorn_log_config, get_logger, set_default_logger
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStoreConnectionError, create_document_store
from fastapi import FastAPI

# Configure structured JSON logging
bootstrap_logger_config = load_driver_config(service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": "orchestrator-bootstrap"})
bootstrap_logger = create_logger("stdout", bootstrap_logger_config)
set_default_logger(bootstrap_logger)
logger = bootstrap_logger

from app import __version__
from app.service import OrchestrationService

# Create FastAPI app
app = FastAPI(title="Orchestration Service", version=__version__)

# Global service instance
orchestration_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global orchestration_service

    stats = orchestration_service.get_stats() if orchestration_service is not None else {}

    return {
        "status": "healthy",
        "service": "orchestration",
        "version": __version__,
        "events_processed_total": stats.get("events_processed", 0),
        "threads_orchestrated_total": stats.get("threads_orchestrated", 0),
        "failures_total": stats.get("failures_count", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        "config": stats.get("config", {}),
    }


@app.get("/stats")
def get_stats():
    """Get orchestration statistics."""
    global orchestration_service

    if not orchestration_service:
        return {"error": "Service not initialized"}

    return orchestration_service.get_stats()


def start_subscriber_thread(service: OrchestrationService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Orchestration service instance

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
    """Main entry point for the orchestration service."""
    global orchestration_service

    log = bootstrap_logger
    log.info(f"Starting Orchestration Service (version {__version__})")

    try:
        # Load configuration using schema-driven service config
        config = load_service_config("orchestrator")
        log.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            log.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                auth_service_url = getattr(config, 'auth_service_url', None)
                audience = getattr(config, 'service_audience', None)
                auth_middleware = create_jwt_middleware(
                    auth_service_url=auth_service_url,
                    audience=audience,
                    required_roles=["orchestrator"],
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
        from app import service as orchestration_service_module
        orchestration_service_module.logger = get_logger(orchestration_service_module.__name__)

        # Create adapters
        log.info("Creating message bus publisher from adapter configuration...")
        message_bus_adapter = config.get_adapter("message_bus")
        if message_bus_adapter is None:
            raise ValueError("message_bus adapter is required")

        publisher = create_publisher(
            driver_name=message_bus_adapter.driver_name,
            driver_config=message_bus_adapter.driver_config,
        )
        try:
            publisher.connect()
        except Exception as e:
            if str(config.message_bus_type).lower() != "noop":
                log.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                log.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        log.info("Creating message bus subscriber from adapter configuration...")
        # Add queue_name to subscriber config
        from copilot_config import DriverConfig
        subscriber_config = {**message_bus_adapter.driver_config.config, "queue_name": "embeddings.generated"}
        subscriber_driver_config = DriverConfig(
            driver_name=message_bus_adapter.driver_name,
            config=subscriber_config,
            allowed_keys=message_bus_adapter.driver_config.allowed_keys
        )
        subscriber = create_subscriber(
            driver_name=message_bus_adapter.driver_name,
            driver_config=subscriber_driver_config,
        )
        try:
            subscriber.connect()
        except Exception as e:
            log.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        log.info("Creating document store from adapter configuration...")
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
        except DocumentStoreConnectionError as e:
            log.error(f"Failed to connect to document store: {e}")
            raise

        # Create metrics collector - fail fast on errors
        log.info("Creating metrics collector...")
        try:
            metrics_adapter = config.get_adapter("metrics")
            if metrics_adapter is not None:
                from copilot_config import DriverConfig
                metrics_driver_config = DriverConfig(
                    driver_name=metrics_adapter.driver_name,
                    config={**metrics_adapter.driver_config.config, "job": "orchestrator"},
                    allowed_keys=metrics_adapter.driver_config.allowed_keys
                )
                metrics_collector = create_metrics_collector(
                    driver_name=metrics_adapter.driver_name,
                    driver_config=metrics_driver_config,
                )
            else:
                from copilot_config import DriverConfig
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
            from copilot_config import DriverConfig
            error_reporter = create_error_reporter(
                driver_name="silent",
                driver_config=DriverConfig(driver_name="silent", config={"logger_name": config.logger_name}),
            )

        # Create orchestration service
        orchestration_service = OrchestrationService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            top_k=config.top_k,
            context_window_tokens=config.context_window_tokens,
            system_prompt_path=config.system_prompt_path,
            user_prompt_path=config.user_prompt_path,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(orchestration_service,),
            daemon=False,
        )
        subscriber_thread.start()
        log.info("Subscriber thread started")

        # Start FastAPI server
        log.info(f"Starting HTTP server on port {config.http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_level = "INFO"
        for adapter in config.adapters:
            if adapter.adapter_type == "logger":
                log_level = adapter.driver_config.config.get("level", "INFO")
                break
        log_config = create_uvicorn_log_config(service_name="orchestrator", log_level=log_level)
        uvicorn.run(app, host="0.0.0.0", port=config.http_port, log_config=log_config, access_log=False)

    except Exception as e:
        log.error(f"Failed to start orchestration service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
