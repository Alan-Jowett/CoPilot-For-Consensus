# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding Service: Generate vector embeddings for text chunks."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from app import __version__
from app.service import EmbeddingService
from copilot_config import load_service_config
from copilot_embedding import create_embedding_provider
from copilot_message_bus import create_publisher, create_subscriber
from copilot_logging import (
    create_logger,
    create_stdout_logger,
    create_uvicorn_log_config,
    set_default_logger,
)
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStoreConnectionError, create_document_store
from copilot_vectorstore import create_vector_store
from fastapi import FastAPI

# Bootstrap logger for early initialization (before config is loaded)
logger = create_stdout_logger(level="INFO", name="embedding")

# Create FastAPI app
app = FastAPI(title="Embedding Service", version=__version__)

# Global service instance (consistent with other services in the codebase)
embedding_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global embedding_service

    stats = embedding_service.get_stats() if embedding_service is not None else {}

    return {
        "status": "healthy",
        "service": "embedding",
        "version": __version__,
        "backend": stats.get("embedding_backend", "unknown"),
        "model": stats.get("embedding_model", "unknown"),
        "dimension": stats.get("embedding_dimension", 0),
        "embeddings_generated_total": stats.get("embeddings_generated_total", 0),
        "uptime_seconds": stats.get("uptime_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get embedding statistics."""
    global embedding_service

    if not embedding_service:
        return {"error": "Service not initialized"}

    return embedding_service.get_stats()


def start_subscriber_thread(service: EmbeddingService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Embedding service instance

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
    """Main entry point for the embedding service."""
    global embedding_service
    global logger

    logger.info(f"Starting Embedding Service (version {__version__})")

    try:
        # Load configuration using schema-driven service config
        config = load_service_config("embedding")
        logger.info("Configuration loaded successfully")

        # Replace bootstrap logger with config-based logger
        logger_adapter = config.get_adapter("logger")
        if logger_adapter is not None:
            logger = create_logger(
                driver_name=logger_adapter.driver_name,
                driver_config=logger_adapter.driver_config
            )
            set_default_logger(logger)
            logger.info("Logger initialized from service configuration")

        # Conditionally add JWT authentication middleware based on config
        if config.jwt_auth_enabled:
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

        from copilot_config import DriverConfig
        subscriber_driver_config = DriverConfig(
            driver_name=message_bus_adapter.driver_name,
            config={**message_bus_adapter.driver_config.config, "queue_name": "chunks.prepared"},
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

        document_schema_provider = create_schema_provider(schema_type="documents")

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
        document_store.connect()

        logger.info("Creating embedding provider from adapter configuration...")
        embedding_adapter = config.get_adapter("embedding_backend")
        if embedding_adapter is None:
            raise ValueError("embedding_backend adapter is required")

        backend_name = str(embedding_adapter.driver_name).lower()
        provider_driver_name = backend_name

        embedding_provider = create_embedding_provider(
            driver_name=provider_driver_name,
            driver_config=embedding_adapter.driver_config,
        )

        # Get embedding configuration for service setup
        # For providers that expose dimension property (like mock), use it
        # Otherwise, determine dimension by creating a sample embedding
        if hasattr(embedding_provider, "dimension"):
            embedding_dimension = embedding_provider.dimension
        else:
            # Get dimension from a sample embedding
            sample_embedding = embedding_provider.embed("test")
            embedding_dimension = len(sample_embedding)

        embedding_model = getattr(embedding_adapter.driver_config, "model_name", provider_driver_name)
        embedding_backend_label = backend_name
        embedding_driver_config = embedding_adapter.driver_config

        logger.info("Creating vector store from adapter configuration...")
        vector_store_adapter = config.get_adapter("vector_store")
        if vector_store_adapter is None:
            raise ValueError("vector_store adapter is required")

        from copilot_config import DriverConfig
        vector_store_driver_config = DriverConfig(
            driver_name=vector_store_adapter.driver_name,
            config={**vector_store_adapter.driver_config.config, "embedding_dimension": embedding_dimension},
            allowed_keys=vector_store_adapter.driver_config.allowed_keys
        )
        vector_store = create_vector_store(
            driver_name=vector_store_adapter.driver_name,
            driver_config=vector_store_driver_config,
        )

        if hasattr(vector_store, "connect"):
            try:
                result = vector_store.connect()
                if result is False and str(vector_store_adapter.driver_name).lower() != "inmemory":
                    logger.error("Failed to connect to vector store.")
                    raise ConnectionError("Vector store failed to connect")
            except Exception as e:
                if str(vector_store_adapter.driver_name).lower() != "inmemory":
                    logger.error(f"Failed to connect to vector store: {e}")
                    raise ConnectionError("Vector store failed to connect")

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_adapter = config.get_adapter("metrics")
        if metrics_adapter is not None:
            from copilot_config import DriverConfig
            metrics_driver_config = DriverConfig(
                driver_name=metrics_adapter.driver_name,
                config={**metrics_adapter.driver_config.config, "job": "embedding"},
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

        # Create embedding service
        embedding_service = EmbeddingService(
            document_store=document_store,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            embedding_model=embedding_model,
            embedding_backend=embedding_backend_label,
            embedding_dimension=(
                vector_store_driver_config.get("dimension")
                or vector_store_driver_config.get("vector_size")
                or embedding_driver_config.get("embedding_dimension")
            ),
            batch_size=config.batch_size,
            max_retries=config.max_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
            vector_store_collection=(
                vector_store_driver_config.get("collection_name")
                or vector_store_driver_config.get("index_name")
                or "message_embeddings"
            ),
        )

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(embedding_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")

        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="embedding", log_level="INFO")
        uvicorn.run(app, host=config.http_host, port=config.http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start embedding service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
