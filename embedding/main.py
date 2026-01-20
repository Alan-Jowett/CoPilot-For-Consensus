# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding Service: Generate vector embeddings for text chunks."""

import threading
from dataclasses import replace
from typing import cast

import uvicorn
from app import __version__
from app.service import EmbeddingService
from copilot_config.generated.adapters.embedding_backend import (
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
)
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
from copilot_config.generated.adapters.vector_store import (
    DriverConfig_VectorStore_AzureAiSearch,
    DriverConfig_VectorStore_Faiss,
    DriverConfig_VectorStore_Qdrant,
)
from copilot_config.generated.services.embedding import ServiceConfig_Embedding
from copilot_config.runtime_loader import get_config
from copilot_embedding import create_embedding_provider
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
from copilot_vectorstore import create_vector_store
from fastapi import FastAPI

# Bootstrap logger for early initialization (before config is loaded)
logger = create_stdout_logger(level="INFO", name="embedding")
set_default_logger(logger)

# Create FastAPI app
app = FastAPI(title="Embedding Service", version=__version__)

# Global service instance (consistent with other services in the codebase)
embedding_service: EmbeddingService | None = None
subscriber_thread: threading.Thread | None = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global embedding_service
    global subscriber_thread

    stats = embedding_service.get_stats() if embedding_service is not None else {}

    # Check if subscriber thread is alive
    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()

    # Service is only healthy if subscriber thread is running
    status = "unhealthy" if (subscriber_thread is not None and not subscriber_alive) else "healthy"

    return {
        "status": status,
        "service": "embedding",
        "version": __version__,
        "backend": stats.get("embedding_backend", "unknown"),
        "model": stats.get("embedding_model", "unknown"),
        "dimension": stats.get("embedding_dimension", 0),
        "embeddings_generated_total": stats.get("embeddings_generated_total", 0),
        "uptime_seconds": stats.get("uptime_seconds", 0),
        "subscriber_thread_alive": subscriber_alive,
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


def _get_embedding_model(config: ServiceConfig_Embedding) -> str:
    backend_type = config.embedding_backend.embedding_backend_type

    if backend_type == "sentencetransformers":
        driver = cast(DriverConfig_EmbeddingBackend_Sentencetransformers, config.embedding_backend.driver)
        return driver.model_name
    if backend_type == "huggingface":
        driver = cast(DriverConfig_EmbeddingBackend_Huggingface, config.embedding_backend.driver)
        return driver.model_name
    if backend_type == "openai":
        driver = cast(DriverConfig_EmbeddingBackend_Openai, config.embedding_backend.driver)
        return driver.model
    if backend_type == "azure_openai":
        driver = cast(DriverConfig_EmbeddingBackend_AzureOpenai, config.embedding_backend.driver)
        return driver.model or driver.deployment_name
    if backend_type == "mock":
        return "mock"

    raise ValueError(
        f"Unsupported embedding backend type '{backend_type}' " f"for model resolution in _get_embedding_model"
    )


def main():
    """Main entry point for the embedding service."""
    global embedding_service
    global logger
    global subscriber_thread

    logger.info(f"Starting Embedding Service (version {__version__})")

    try:
        # Load strongly-typed configuration from JSON schemas
        config = cast(ServiceConfig_Embedding, get_config("embedding"))
        logger.info("Configuration loaded successfully")

        # Replace bootstrap logger with config-based logger
        logger = create_logger(config.logger)
        set_default_logger(logger)
        logger.info("Logger initialized from service configuration")

        # Service-owned identity constants (not deployment settings)
        service_name = "embedding"
        subscriber_queue_name = "chunks.prepared"

        # Message bus: keep publisher routing driven by (exchange, routing_key).
        # - RabbitMQ: set a stable queue name for subscribers.
        # - Azure Service Bus: use topic/subscription (do NOT set queue_name on shared config).
        if config.message_bus.message_bus_type == "rabbitmq":
            driver = cast(DriverConfig_MessageBus_Rabbitmq, config.message_bus.driver)
            config.message_bus.driver = replace(driver, queue_name=subscriber_queue_name)
        elif config.message_bus.message_bus_type == "azure_service_bus":
            # Topic-based fanout; each service gets its own subscription.
            driver = cast(DriverConfig_MessageBus_AzureServiceBus, config.message_bus.driver)
            config.message_bus.driver = replace(
                driver,
                topic_name="copilot.events",
                subscription_name=service_name,
                queue_name=None,
            )

        # Metrics: stamp per-service identifier onto driver config
        if config.metrics.metrics_type == "pushgateway":
            driver = cast(DriverConfig_Metrics_Pushgateway, config.metrics.driver)
            config.metrics.driver = replace(driver, job=service_name, namespace=service_name)
        elif config.metrics.metrics_type == "prometheus":
            driver = cast(DriverConfig_Metrics_Prometheus, config.metrics.driver)
            config.metrics.driver = replace(driver, namespace=service_name)
        elif config.metrics.metrics_type == "azure_monitor":
            driver = cast(DriverConfig_Metrics_AzureMonitor, config.metrics.driver)
            config.metrics.driver = replace(driver, namespace=service_name)

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

        # Refresh module-level service logger to use the current default
        from app import service as embedding_service_module

        embedding_service_module.logger = get_logger(embedding_service_module.__name__)

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
        document_schema_provider = create_schema_provider(schema_type="documents")
        document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
            schema_provider=document_schema_provider,
        )
        logger.info("Connecting to document store...")
        document_store.connect()

        logger.info("Creating embedding provider from typed configuration...")
        backend_name = str(config.embedding_backend.embedding_backend_type).lower()
        embedding_provider = create_embedding_provider(config.embedding_backend)

        # Get embedding configuration for service setup
        # For providers that expose dimension property (like mock), use it
        # Otherwise, determine dimension by creating a sample embedding
        dimension_value = getattr(embedding_provider, "dimension", None)
        if isinstance(dimension_value, int):
            embedding_dimension = dimension_value
        else:
            # Get dimension from a sample embedding
            sample_embedding = embedding_provider.embed("test")
            embedding_dimension = len(sample_embedding)

        embedding_model = _get_embedding_model(config)

        embedding_backend_label = backend_name

        logger.info("Creating vector store from adapter configuration...")

        # Ensure vector store dimension matches embedding provider.
        if config.vector_store.vector_store_type == "qdrant":
            driver = cast(DriverConfig_VectorStore_Qdrant, config.vector_store.driver)
            config.vector_store.driver = replace(driver, vector_size=embedding_dimension)
        elif config.vector_store.vector_store_type == "azure_ai_search":
            driver = cast(DriverConfig_VectorStore_AzureAiSearch, config.vector_store.driver)
            config.vector_store.driver = replace(driver, vector_size=embedding_dimension)
        elif config.vector_store.vector_store_type == "faiss":
            driver = cast(DriverConfig_VectorStore_Faiss, config.vector_store.driver)
            config.vector_store.driver = replace(driver, dimension=embedding_dimension)

        vector_store = create_vector_store(config.vector_store)

        connect = getattr(vector_store, "connect", None)
        if callable(connect):
            try:
                result = connect()
                if result is False and config.vector_store.vector_store_type != "inmemory":
                    logger.error("Failed to connect to vector store.")
                    raise ConnectionError("Vector store failed to connect")
            except Exception as e:
                if config.vector_store.vector_store_type != "inmemory":
                    logger.error(f"Failed to connect to vector store: {e}")
                    raise ConnectionError("Vector store failed to connect")

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

        event_retry_config = RetryConfig(
            max_attempts=int(retry_driver.max_attempts),
            base_delay_ms=int(retry_driver.base_delay_ms),
            backoff_factor=float(retry_driver.backoff_factor),
            max_delay_ms=int(retry_driver.max_delay_ms),
            ttl_seconds=int(retry_driver.ttl_seconds),
        )
        logger.info(
            f"Retry configuration: max_attempts={event_retry_config.max_attempts}, "
            f"base_delay_ms={event_retry_config.base_delay_ms}, ttl_seconds={event_retry_config.ttl_seconds}"
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
            embedding_dimension=embedding_dimension,
            batch_size=config.service_settings.batch_size if config.service_settings.batch_size is not None else 32,
            max_retries=config.service_settings.max_retries if config.service_settings.max_retries is not None else 3,
            retry_backoff_seconds=(
                config.service_settings.retry_backoff_seconds
                if config.service_settings.retry_backoff_seconds is not None
                else 5
            ),
            vector_store_collection=(
                cast(DriverConfig_VectorStore_Qdrant, config.vector_store.driver).collection_name
                if config.vector_store.vector_store_type == "qdrant"
                else (
                    cast(DriverConfig_VectorStore_AzureAiSearch, config.vector_store.driver).index_name
                    if config.vector_store.vector_store_type == "azure_ai_search"
                    else "message_embeddings"
                )
            ),
            event_retry_config=event_retry_config,
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
        http_port = config.service_settings.http_port if config.service_settings.http_port is not None else 8000
        http_host = config.service_settings.http_host or "0.0.0.0"
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="embedding", log_level="INFO")
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start embedding service: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
