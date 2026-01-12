# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization Service: Generate citation-rich summaries from orchestrated requests."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from app import __version__
from app.service import SummarizationService
from copilot_config import load_service_config, load_driver_config
from copilot_message_bus import create_publisher, create_subscriber
from copilot_logging import create_logger, create_uvicorn_log_config, set_default_logger
from copilot_metrics import create_metrics_collector
from copilot_error_reporting import create_error_reporter
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStoreConnectionError, create_document_store
from copilot_summarization import create_llm_backend
from copilot_vectorstore import create_vector_store
from fastapi import FastAPI

# Configure structured JSON logging
bootstrap_logger_config = load_driver_config(service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": "summarization-bootstrap"})
bootstrap_logger = create_logger("stdout", bootstrap_logger_config)
logger = bootstrap_logger

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

    log = bootstrap_logger
    log.info(f"Starting Summarization Service (version {__version__})")

    try:
        config = load_service_config("summarization")

        # Replace bootstrap logger with config-based logger
        logger_adapter = config.get_adapter("logger")
        if logger_adapter is not None:
            service_logger = create_logger(
                driver_name=logger_adapter.driver_name,
                driver_config=logger_adapter.driver_config
            )
            logger = service_logger
            log = service_logger
            set_default_logger(service_logger)
            log.info("Logger initialized from service configuration")
        else:
            logger = log
            set_default_logger(bootstrap_logger)
            log.warning("No logger adapter found, keeping bootstrap logger")

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
            log.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        log.info("Creating message bus subscriber from adapter configuration...")
        # Add queue_name to subscriber config
        from copilot_config import DriverConfig
        subscriber_config = {**message_bus_adapter.driver_config.config, "queue_name": "summarization.requested"}
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

        log.info("Creating vector store from adapter configuration...")
        vector_store_adapter = config.get_adapter("vector_store")
        if vector_store_adapter is None:
            raise ValueError("vector_store adapter is required")

        vector_store = create_vector_store(
            driver_name=vector_store_adapter.driver_name,
            driver_config=vector_store_adapter.driver_config,
        )

        if hasattr(vector_store, "connect"):
            try:
                result = vector_store.connect()
                if result is False and str(config.vector_store_type).lower() != "inmemory":
                    log.error("Failed to connect to vector store.")
                    raise ConnectionError("Vector store failed to connect")
            except Exception as e:
                if str(config.vector_store_type).lower() != "inmemory":
                    log.error(f"Failed to connect to vector store: {e}")
                    raise ConnectionError("Vector store failed to connect")

        log.info("Creating summarizer from adapter configuration...")
        llm_backend_adapter = config.get_adapter("llm_backend")
        if llm_backend_adapter is None:
            raise ValueError("llm_backend adapter is required")

        summarizer = create_llm_backend(
            driver_name=llm_backend_adapter.driver_name,
            driver_config=llm_backend_adapter.driver_config,
        )

        log.info("Creating metrics collector...")
        try:
            metrics_adapter = config.get_adapter("metrics")
            if metrics_adapter is not None:
                from copilot_config import DriverConfig
                metrics_driver_config = DriverConfig(
                    driver_name=metrics_adapter.driver_name,
                    config={**metrics_adapter.driver_config.config, "job": "summarization"},
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
        except Exception as e:
            from copilot_config import DriverConfig
            log.warning(
                "Metrics backend unavailable; falling back to NoOp",
                backend=config.metrics_type,
                error=str(e),
            )
            metrics_collector = create_metrics_collector(
                driver_name="noop",
                driver_config=DriverConfig(driver_name="noop")
            )
            metrics_collector = NoOpMetricsCollector()

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
                driver_config=DriverConfig(
                    driver_name="silent",
                    config={"logger_name": config.logger_name}
                ),
            )

        summarization_service = SummarizationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            summarizer=summarizer,
            top_k=config.top_k,
            citation_count=config.citation_count,
            retry_max_attempts=config.max_retries,
            retry_backoff_seconds=config.retry_delay_seconds,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            llm_backend=llm_backend_adapter.driver_name,
            llm_model=llm_backend_adapter.driver_config.config.get("local_llm_model", "mistral"),
            context_window_tokens=llm_backend_adapter.driver_config.config.get("context_window_tokens", 4096),
            prompt_template=llm_backend_adapter.driver_config.config.get("prompt_template", ""),
        )

        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(summarization_service,),
            daemon=False,
        )
        subscriber_thread.start()
        log.info("Subscriber thread started")

        log.info(f"Starting HTTP server on port {config.http_port}...")

        # Get log level from logger adapter config
        log_level = "INFO"
        for adapter in config.adapters:
            if adapter.adapter_type == "logger":
                log_level = adapter.driver_config.get("level", "INFO")
                break
        log_config = create_uvicorn_log_config(service_name="summarization", log_level=log_level)
        uvicorn.run(app, host="0.0.0.0", port=config.http_port, log_config=log_config, access_log=False)

    except Exception as e:
        log.error(f"Failed to start summarization service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
