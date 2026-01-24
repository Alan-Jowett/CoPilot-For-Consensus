# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Orchestration Service: Coordinate summarization and analysis tasks."""

import os
import threading
import time
from dataclasses import replace
from typing import cast

import uvicorn
from app import __version__
from app.service import OrchestrationService
from copilot_config.generated.adapters.message_bus import (
    DriverConfig_MessageBus_AzureServiceBus,
    DriverConfig_MessageBus_Rabbitmq,
)
from copilot_config.generated.adapters.metrics import (
    DriverConfig_Metrics_AzureMonitor,
    DriverConfig_Metrics_Prometheus,
    DriverConfig_Metrics_Pushgateway,
)
from copilot_config.generated.services.orchestrator import ServiceConfig_Orchestrator
from copilot_config.runtime_loader import get_config
from copilot_error_reporting import create_error_reporter
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
from copilot_storage import DocumentStoreConnectionError, create_document_store
from fastapi import FastAPI

# Bootstrap logger for early initialization (before config is loaded)
logger = create_stdout_logger(level="INFO", name="orchestrator")
set_default_logger(logger)

# Create FastAPI app
app = FastAPI(title="Orchestration Service", version=__version__)

# Global service instance
orchestration_service = None
subscriber_thread: threading.Thread | None = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global orchestration_service
    global subscriber_thread

    stats = orchestration_service.get_stats() if orchestration_service is not None else {}

    # Check if subscriber thread is alive
    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()

    # Service is only healthy if subscriber thread is running
    status = "unhealthy" if (subscriber_thread is not None and not subscriber_alive) else "healthy"

    return {
        "status": status,
        "service": "orchestration",
        "version": __version__,
        "events_processed_total": stats.get("events_processed", 0),
        "threads_orchestrated_total": stats.get("threads_orchestrated", 0),
        "failures_total": stats.get("failures_count", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        "config": stats.get("config", {}),
        "subscriber_thread_alive": subscriber_alive,
    }


@app.get("/readyz")
def readyz():
    """Readiness check endpoint - indicates if service is ready to process requests."""
    global orchestration_service
    global subscriber_thread

    # Service is ready only when:
    # 1. Service is initialized
    # 2. Subscriber thread is running
    if orchestration_service is None:
        return {"status": "not_ready", "reason": "Service not initialized"}, 503

    subscriber_alive = subscriber_thread is not None and subscriber_thread.is_alive()
    if not subscriber_alive:
        return {"status": "not_ready", "reason": "Subscriber thread not running"}, 503

    return {"status": "ready", "service": "orchestration"}


@app.get("/stats")
def get_stats():
    """Get orchestration statistics."""
    global orchestration_service

    if not orchestration_service:
        return {"error": "Service not initialized"}

    return orchestration_service.get_stats()


def log_memory_usage(logger, stage: str):
    """Log current memory usage for startup diagnostics.

    Args:
        logger: Logger instance
        stage: Description of current startup stage
    """
    try:
        import psutil

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        logger.info(f"[Startup Diagnostics] {stage}: Memory usage = {mem_mb:.2f} MB")
    except ImportError:
        # psutil not available, skip memory logging
        pass
    except Exception as e:
        logger.debug(f"Failed to log memory usage: {e}")


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

    global logger
    global subscriber_thread

    startup_start = time.time()
    logger.info(f"Starting Orchestration Service (version {__version__})")
    log_memory_usage(logger, "Initial startup")

    try:
        # Load strongly-typed configuration from JSON schemas
        config_start = time.time()
        config = cast(ServiceConfig_Orchestrator, get_config("orchestrator"))
        config_time = time.time() - config_start
        logger.info(f"Configuration loaded successfully in {config_time:.2f}s")
        log_memory_usage(logger, "After config load")

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
                    required_roles=["orchestrator"],
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
        service_name = "orchestrator"
        subscriber_queue_name = "embeddings.generated"

        # Message bus identity:
        # - RabbitMQ: use a stable queue name per service.
        # - Azure Service Bus: use topic/subscription (do NOT use queue_name).
        message_bus_type = str(config.message_bus.message_bus_type).lower()
        if message_bus_type == "rabbitmq":
            rabbitmq_cfg = cast(DriverConfig_MessageBus_Rabbitmq, config.message_bus.driver)
            config.message_bus.driver = replace(rabbitmq_cfg, queue_name=subscriber_queue_name)
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
        from app import service as orchestration_service_module

        orchestration_service_module.logger = get_logger(orchestration_service_module.__name__)

        # Create adapters
        logger.info("Creating message bus publisher...")
        publisher_start = time.time()
        publisher = create_publisher(
            config.message_bus,
            enable_validation=True,
            strict_validation=True,
        )
        try:
            publisher.connect()
            publisher_time = time.time() - publisher_start
            logger.info(f"Publisher connected to message bus in {publisher_time:.2f}s")
            log_memory_usage(logger, "After publisher connect")
        except Exception as e:
            if str(config.message_bus.message_bus_type).lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        logger.info("Creating message bus subscriber...")
        subscriber_start = time.time()
        subscriber = create_subscriber(
            config.message_bus,
            enable_validation=True,
            strict_validation=True,
        )
        try:
            subscriber.connect()
            subscriber_time = time.time() - subscriber_start
            logger.info(f"Subscriber connected to message bus in {subscriber_time:.2f}s")
            log_memory_usage(logger, "After subscriber connect")
        except Exception as e:
            logger.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        logger.info("Creating document store...")
        docstore_start = time.time()
        document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
            schema_provider=create_schema_provider(schema_type="documents"),
        )
        try:
            document_store.connect()
            docstore_time = time.time() - docstore_start
            logger.info(f"Document store connected successfully in {docstore_time:.2f}s")
            log_memory_usage(logger, "After document store connect")
        except DocumentStoreConnectionError as e:
            logger.error(f"Failed to connect to document store: {e}")
            raise

        # Create vector store
        logger.info("Creating vector store...")
        vectorstore_start = time.time()
        try:
            from copilot_vectorstore import create_vector_store

            vector_store = create_vector_store(config.vector_store)
            vectorstore_time = time.time() - vectorstore_start
            logger.info(f"Vector store created successfully in {vectorstore_time:.2f}s")
            log_memory_usage(logger, "After vector store connect")
        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            raise

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector(config.metrics)

        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter(config.error_reporter)

        # Get chunk selection strategy from config
        chunk_selection_strategy = str(
            config.service_settings.chunk_selection_strategy or "top_k_relevance"
        )

        # Create orchestration service
        orchestration_service = OrchestrationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            top_k=int(config.service_settings.top_k or 5),
            context_window_tokens=int(config.service_settings.context_window_tokens or 2048),
            system_prompt_path=str(config.service_settings.system_prompt_path or "/app/prompts/system.txt"),
            user_prompt_path=str(config.service_settings.user_prompt_path or "/app/prompts/user.txt"),
            chunk_selection_strategy=chunk_selection_strategy,
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

        startup_total = time.time() - startup_start
        logger.info(f"[Startup Diagnostics] Service fully initialized in {startup_total:.2f}s")
        log_memory_usage(logger, "Service ready")

        # Start FastAPI server
        http_port = int(config.service_settings.http_port or 8000)
        http_host = "0.0.0.0"
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_level = getattr(config.logger.driver, "level", "INFO")
        log_config = create_uvicorn_log_config(service_name="orchestrator", log_level=log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start orchestration service: {e}", exc_info=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
