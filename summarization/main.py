# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization Service: Generate citation-rich summaries from orchestrated requests."""

import os
import sys
import threading
from dataclasses import replace
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from copilot_config.runtime_loader import get_config
from copilot_message_bus import create_publisher, create_subscriber
from copilot_logging import (
    create_logger,
    create_stdout_logger,
    create_uvicorn_log_config,
    get_logger,
    set_default_logger,
)
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStoreConnectionError, create_document_store
from copilot_summarization import create_llm_backend
from copilot_vectorstore import create_vector_store
from fastapi import FastAPI

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_stdout_logger(level="INFO", name="summarization")
set_default_logger(bootstrap_logger)
logger = bootstrap_logger

from app import __version__
from app.service import SummarizationService

# Create FastAPI app
app = FastAPI(title="Summarization Service", version=__version__)

# Global service instance
summarization_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global summarization_service

    stats = summarization_service.get_stats() if summarization_service is not None else {}

    return {
        "status": "healthy",
        "service": "summarization",
        "version": __version__,
        "summaries_generated": stats.get("summaries_generated", 0),
        "summarization_failures": stats.get("summarization_failures", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get summarization statistics."""
    global summarization_service

    if not summarization_service:
        return {"error": "Service not initialized"}

    return summarization_service.get_stats()


def start_subscriber_thread(service: SummarizationService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Summarization service instance

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
    """Main entry point for the summarization service."""
    global summarization_service
    global logger

    logger.info(f"Starting Summarization Service (version {__version__})")

    try:
        # Load strongly-typed configuration from JSON schemas
        config = get_config("summarization")
        logger.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        if config.service_settings.jwt_auth_enabled:
            logger.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware

                auth_middleware = create_jwt_middleware(
                    auth_service_url=config.service_settings.auth_service_url,
                    audience=config.service_settings.service_audience,
                    required_roles=["processor"],
                    public_paths=["/health", "/readyz", "/docs", "/openapi.json"],
                )
                try:
                    app.add_middleware(auth_middleware)
                except RuntimeError as exc:
                    logger.warning(
                        f"JWT middleware could not be added (app already started): {exc}"
                    )
            except ImportError:
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Replace bootstrap logger with config-based logger
        logger = create_logger(config.logger)
        set_default_logger(logger)
        logger.info("Logger initialized from service configuration")

        # Service-owned identity constants (not deployment settings)
        service_name = "summarization"
        subscriber_queue_name = "summarization.requested"

        # Message bus identity:
        # - RabbitMQ: use a stable queue name per service.
        # - Azure Service Bus: use topic/subscription (do NOT use queue_name).
        if str(config.message_bus.message_bus_type).lower() == "rabbitmq" and hasattr(
            config.message_bus.driver, "queue_name"
        ):
            config.message_bus.driver = replace(config.message_bus.driver, queue_name=subscriber_queue_name)
        elif str(config.message_bus.message_bus_type).lower() == "azure_service_bus":
            if hasattr(config.message_bus.driver, "topic_name") and hasattr(config.message_bus.driver, "subscription_name"):
                config.message_bus.driver = replace(
                    config.message_bus.driver,
                    topic_name="copilot.events",
                    subscription_name=service_name,
                    queue_name=None,
                )

        # Metrics identity: stamp per-service identifier onto driver config
        if str(config.metrics.metrics_type).lower() == "pushgateway" and hasattr(config.metrics.driver, "job"):
            config.metrics.driver = replace(config.metrics.driver, job=service_name, namespace=service_name)
        elif hasattr(config.metrics.driver, "namespace"):
            config.metrics.driver = replace(config.metrics.driver, namespace=service_name)

        # Refresh module-level service logger to use the current default
        from app import service as summarization_service_module
        summarization_service_module.logger = get_logger(summarization_service_module.__name__)

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

        logger.info("Creating vector store...")
        vector_store = create_vector_store(config.vector_store)

        if hasattr(vector_store, "connect"):
            try:
                result = vector_store.connect()
                if result is False and str(config.vector_store.vector_store_type).lower() != "inmemory":
                    logger.error("Failed to connect to vector store.")
                    raise ConnectionError("Vector store failed to connect")
            except Exception as e:
                if str(config.vector_store.vector_store_type).lower() != "inmemory":
                    logger.error(f"Failed to connect to vector store: {e}")
                    raise ConnectionError("Vector store failed to connect")

        logger.info("Creating LLM backend...")
        summarizer = create_llm_backend(config.llm_backend)

        # Resolve human-readable model name for event metadata / startup requeue
        llm_driver = config.llm_backend.driver
        llm_model = (
            getattr(llm_driver, "local_llm_model", None)
            or getattr(llm_driver, "llamacpp_model", None)
            or getattr(llm_driver, "openai_model", None)
            or getattr(llm_driver, "azure_openai_model", None)
            or "mistral"
        )

        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector(config.metrics)

        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter(config.error_reporter)

        summarization_service = SummarizationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            summarizer=summarizer,
            top_k=int(config.service_settings.top_k or 12),
            citation_count=int(config.service_settings.citation_count or 12),
            retry_max_attempts=int(config.service_settings.max_retries or 3),
            retry_backoff_seconds=int(config.service_settings.retry_delay_seconds or 5),
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            llm_backend=str(config.llm_backend.llm_backend_type),
            llm_model=str(llm_model),
            context_window_tokens=4096,
            prompt_template="",
        )

        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(summarization_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")

        http_port = int(config.service_settings.http_port or 8000)
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Get log level from logger adapter config
        log_level = getattr(config.logger.driver, "level", "INFO")
        log_config = create_uvicorn_log_config(service_name="summarization", log_level=log_level)
        uvicorn.run(app, host="0.0.0.0", port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start summarization service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
