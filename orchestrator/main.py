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
from app import __version__
from app.service import OrchestrationService
from copilot_config import load_typed_config
from copilot_events import create_publisher, create_subscriber
from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter
from copilot_schema_validation import FileSchemaProvider
from copilot_storage import DocumentStoreConnectionError, ValidatingDocumentStore, create_document_store
from fastapi import FastAPI

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="orchestrator")

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

    logger.info(f"Starting Orchestration Service (version {__version__})")

    try:
        # Load configuration using config adapter
        config = load_typed_config("orchestrator")
        logger.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            logger.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                auth_middleware = create_jwt_middleware(
                    required_roles=["orchestrator"],
                    public_paths=["/health", "/readyz", "/docs", "/openapi.json"],
                )
                app.add_middleware(auth_middleware)
            except ImportError:
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Create adapters
        logger.info("Creating message bus publisher...")
        publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )
        try:
            publisher.connect()
        except Exception as e:
            if str(config.message_bus_type).lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        logger.info("Creating message bus subscriber...")
        subscriber = create_subscriber(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,            queue_name="orchestrator-service",        )
        try:
            subscriber.connect()
        except Exception as e:
            logger.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        logger.info("Creating document store...")
        base_document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        try:
            base_document_store.connect()
        except DocumentStoreConnectionError as e:
            logger.error(f"Failed to connect to document store: {e}")
            raise

        # Wrap with schema validation
        logger.info("Wrapping document store with schema validation...")
        document_schema_provider = FileSchemaProvider(
            schema_dir=Path(__file__).parent / "documents" / "schemas" / "documents"
        )
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=document_schema_provider,
            strict=True,
        )

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector()

        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter()

        # Create orchestration service
        orchestration_service = OrchestrationService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            top_k=config.top_k,
            context_window_tokens=config.context_window_tokens,
            llm_backend=config.llm_backend,
            llm_model=config.llm_model,
            llm_temperature=config.llm_temperature,
            llm_max_tokens=config.llm_max_tokens,
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
        logger.info("Subscriber thread started")

        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="orchestrator", log_level="INFO")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port, log_config=log_config)

    except Exception as e:
        logger.error(f"Failed to start orchestration service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
