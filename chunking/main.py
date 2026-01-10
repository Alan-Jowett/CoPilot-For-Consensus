# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Chunking Service: Split long email bodies into semantically coherent chunks."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from app import __version__
from app.service import ChunkingService
from copilot_chunking import create_chunker
from copilot_config import load_service_config
from copilot_message_bus import create_publisher, create_subscriber
from copilot_logging import create_logger, create_stdout_logger, create_uvicorn_log_config
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store
from fastapi import FastAPI

# Bootstrap logger for early initialization (before config is loaded)
logger = create_stdout_logger(level="INFO", name="chunking")

# Create FastAPI app
app = FastAPI(title="Chunking Service", version=__version__)

# Global service instance
chunking_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global chunking_service

    stats = chunking_service.get_stats() if chunking_service is not None else {}

    return {
        "status": "healthy",
        "service": "chunking",
        "version": __version__,
        "chunks_created_total": stats.get("chunks_created_total", 0),
        "messages_processed_total": stats.get("messages_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
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

    logger.info(f"Starting Chunking Service (version {__version__})")

    try:
        # Load configuration using schema-driven service config
        config = load_service_config("chunking")
        logger.info("Configuration loaded successfully")
        
        # Replace bootstrap logger with config-based logger
        logger_adapter = config.get_adapter("logger")
        if logger_adapter is not None:
            logger = create_logger(
                driver_name=logger_adapter.driver_name,
                driver_config=logger_adapter.driver_config
            )
            logger.info("Logger initialized from service configuration")

        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            logger.info("JWT authentication is enabled")
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
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Create adapters
        message_bus_adapter = config.get_adapter("message_bus")
        if message_bus_adapter is None:
            raise ValueError("message_bus adapter is required")

        logger.info("Creating message bus publisher...")
        publisher = create_publisher(
            driver_name=message_bus_adapter.driver_name,
            driver_config=message_bus_adapter.driver_config,
        )
        try:
            publisher.connect()
        except Exception as e:
            if str(message_bus_adapter.driver_name).lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        logger.info("Creating message bus subscriber...")
        # Add queue_name to subscriber config
        from copilot_config import DriverConfig
        subscriber_config = {**message_bus_adapter.driver_config.config, "queue_name": "json.parsed"}
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
            logger.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        logger.info("Creating document store...")
        document_store_adapter = config.get_adapter("document_store")
        if document_store_adapter is None:
            raise ValueError("document_store adapter is required")

        document_schema_provider = create_schema_provider(
            schema_dir=Path(__file__).parent / "docs" / "schemas" / "documents",
            schema_type="documents",
        )

        from copilot_config import DriverConfig
        document_store_driver_config = DriverConfig(
            driver_name=document_store_adapter.driver_name,
            config={**document_store_adapter.driver_config.config, "schema_provider": document_schema_provider},
            allowed_keys=document_store_adapter.driver_config.allowed_keys
        )
        document_store = create_document_store(
            driver_name=document_store_adapter.driver_name,
            driver_config=document_store_driver_config,
            enable_validation=True,
            strict_validation=True,
        )
        logger.info("Connecting to document store...")
        # connect() raises on failure; None return indicates success
        document_store.connect()
        logger.info("Document store connected successfully")

        # Create chunker via adapter config
        logger.info("Creating chunker from adapter configuration")
        try:
            chunker_adapter = config.get_adapter("chunker")
            chunker = create_chunker(
                driver_name=chunker_adapter.driver_name,
                driver_config=chunker_adapter.driver_config,
            )
        except Exception as e:
            logger.error(f"Failed to create chunker from adapter config: {e}")
            raise

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_adapter = config.get_adapter("metrics")
        if metrics_adapter is not None:
            from copilot_config import DriverConfig
            metrics_driver_config = DriverConfig(
                driver_name=metrics_adapter.driver_name,
                config={**metrics_adapter.driver_config.config, "job": "chunking"},
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

        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter_adapter = config.get_adapter("error_reporter")
        if error_reporter_adapter is not None:
            error_reporter = create_error_reporter(
                driver_name=error_reporter_adapter.driver_name,
                driver_config=error_reporter_adapter.driver_config,
            )
        else:
            # Fallback to console reporter with empty config
            from copilot_config import DriverConfig
            error_reporter = create_error_reporter(
                driver_name="console",
                driver_config=DriverConfig(driver_name="console", config={}, allowed_keys=set()),
            )

        # Create chunking service
        chunking_service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
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
        http_port = getattr(config, "http_port", 8000)
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="chunking", log_level="INFO")
        uvicorn.run(app, host="0.0.0.0", port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start chunking service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
