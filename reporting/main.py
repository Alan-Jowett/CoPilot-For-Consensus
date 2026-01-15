# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Reporting Service: Persist and serve summaries via REST and notifications."""

import os
import sys
import threading
from dataclasses import replace
from typing import cast

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from copilot_config.runtime_loader import get_config
from copilot_config.generated.services.reporting import ServiceConfig_Reporting
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
from fastapi import FastAPI, HTTPException, Query

# Bootstrap logger before configuration is loaded
bootstrap_logger = create_stdout_logger(level="INFO", name="reporting")
set_default_logger(bootstrap_logger)

from app import __version__
from app.service import ReportingService
logger = bootstrap_logger

# Create FastAPI app
app = FastAPI(title="Reporting Service", version=__version__)

# Global service instance
reporting_service = None


def load_service_config() -> ServiceConfig_Reporting:
    return cast(ServiceConfig_Reporting, get_config("reporting"))


@app.get("/")
def root():
    """Root endpoint redirects to health check."""
    return health()


@app.get("/health")
def health():
    """Health check endpoint."""
    global reporting_service

    stats = reporting_service.get_stats() if reporting_service is not None else {}

    return {
        "status": "healthy",
        "service": "reporting",
        "version": __version__,
        "reports_stored": stats.get("reports_stored", 0),
        "notifications_sent": stats.get("notifications_sent", 0),
        "notifications_failed": stats.get("notifications_failed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get reporting statistics."""
    global reporting_service

    if not reporting_service:
        return {"error": "Service not initialized"}

    return reporting_service.get_stats()


@app.get("/api/reports")
def get_reports(
    thread_id: str = Query(None, description="Filter by thread ID"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    message_start_date: str = Query(None, description="Filter by thread message dates (inclusive overlap) - start of date range (ISO 8601)"),
    message_end_date: str = Query(None, description="Filter by thread message dates (inclusive overlap) - end of date range (ISO 8601)"),
    source: str = Query(None, description="Filter by archive source"),
    min_participants: int = Query(None, ge=0, description="Minimum number of participants"),
    max_participants: int = Query(None, ge=0, description="Maximum number of participants"),
    min_messages: int = Query(None, ge=0, description="Minimum number of messages in thread"),
    max_messages: int = Query(None, ge=0, description="Maximum number of messages in thread"),
    sort_by: str = Query(None, regex="^(thread_start_date|generated_at)$", description="Sort by field ('thread_start_date' or 'generated_at')"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
):
    """Get list of reports with optional filters."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        reports = reporting_service.get_reports(
            thread_id=thread_id,
            limit=limit,
            skip=skip,
            message_start_date=message_start_date,
            message_end_date=message_end_date,
            source=source,
            min_participants=min_participants,
            max_participants=max_participants,
            min_messages=min_messages,
            max_messages=max_messages,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return {
            "reports": reports,
            "count": len(reports),
            "limit": limit,
            "skip": skip,
        }

    except Exception as e:
        logger.error(f"Error fetching reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/search")
def search_reports_by_topic(
    topic: str = Query(..., description="Topic or query text to search for"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    min_score: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score"),
):
    """Search reports by topic using embedding-based similarity."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        reports = reporting_service.search_reports_by_topic(
            topic=topic,
            limit=limit,
            min_score=min_score,
        )

        return {
            "reports": reports,
            "count": len(reports),
            "topic": topic,
            "min_score": min_score,
        }

    except ValueError as e:
        # Topic search may not be configured
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching reports by topic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    """Get a specific report by ID."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        report = reporting_service.get_report_by_id(report_id)

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report {report_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/threads/{thread_id}/summary")
def get_thread_summary(thread_id: str):
    """Get the latest summary for a thread."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        summary = reporting_service.get_thread_summary(thread_id)

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for thread")

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching thread summary {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sources")
def get_available_sources():
    """Get list of available archive sources."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        sources = reporting_service.get_available_sources()

        return {
            "sources": sources,
            "count": len(sources),
        }

    except Exception as e:
        logger.error(f"Error fetching available sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/threads")
def get_threads(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    archive_id: str = Query(None, description="Filter by archive ID"),
):
    """Get list of threads with optional filters."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        threads = reporting_service.get_threads(
            limit=limit,
            skip=skip,
            archive_id=archive_id,
        )

        return {
            "threads": threads,
            "count": len(threads),
            "limit": limit,
            "skip": skip,
        }

    except Exception as e:
        logger.error(f"Error fetching threads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/threads/{thread_id}")
def get_thread(thread_id: str):
    """Get a specific thread by ID."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        thread = reporting_service.get_thread_by_id(thread_id)

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        return thread

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching thread {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages")
def get_messages(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    thread_id: str = Query(None, description="Filter by thread ID"),
    message_id: str = Query(None, description="Filter by RFC 5322 Message-ID"),
):
    """Get list of messages with optional filters."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        messages = reporting_service.get_messages(
            limit=limit,
            skip=skip,
            thread_id=thread_id,
            message_id=message_id,
        )

        return {
            "messages": messages,
            "count": len(messages),
            "limit": limit,
            "skip": skip,
        }

    except Exception as e:
        logger.error(f"Error fetching messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages/{message_doc_id}")
def get_message(message_doc_id: str):
    """Get a specific message by its document ID."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        message = reporting_service.get_message_by_id(message_doc_id)

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching message {message_doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chunks")
def get_chunks(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    message_id: str = Query(None, description="Filter by RFC 5322 Message-ID"),
    thread_id: str = Query(None, description="Filter by thread ID"),
    message_doc_id: str = Query(None, description="Filter by message document ID"),
):
    """Get list of chunks with optional filters."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        chunks = reporting_service.get_chunks(
            limit=limit,
            skip=skip,
            message_id=message_id,
            thread_id=thread_id,
            message_doc_id=message_doc_id,
        )

        return {
            "chunks": chunks,
            "count": len(chunks),
            "limit": limit,
            "skip": skip,
        }

    except Exception as e:
        logger.error(f"Error fetching chunks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    """Get a specific chunk by ID."""
    global reporting_service

    if not reporting_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        chunk = reporting_service.get_chunk_by_id(chunk_id)

        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")

        return chunk

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chunk {chunk_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def start_subscriber_thread(service: ReportingService):
    """Start the event subscriber in a separate thread.

    Args:
        service: Reporting service instance

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
        logger.error(f"Subscriber error: {e}", exc_info=True)
        # Fail fast - re-raise to terminate the service
        raise


def main():
    """Main entry point for the reporting service."""
    global reporting_service
    global logger

    logger.info(f"Starting Reporting Service (version {__version__})")

    try:
        # Load strongly-typed configuration from JSON schemas
        config = load_service_config()
        logger.info("Configuration loaded successfully")

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
                    required_roles=["reader"],
                    public_paths=["/", "/health", "/readyz", "/docs", "/openapi.json"],
                )
                try:
                    app.add_middleware(auth_middleware)
                except RuntimeError as exc:
                    logger.warning(f"Cannot add middleware after app has started: {exc}")
            except ImportError:
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Replace bootstrap logger with config-based logger
        logger = create_logger(config.logger)
        set_default_logger(logger)
        logger.info("Logger initialized from service configuration")

        # Service-owned identity constants (not deployment settings)
        service_name = "reporting"
        subscriber_queue_name = "summary.complete"

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
            config.metrics.driver = replace(pushgateway_cfg, job=service_name, namespace=service_name)
        elif metrics_type == "prometheus":
            prometheus_cfg = cast(DriverConfig_Metrics_Prometheus, config.metrics.driver)
            config.metrics.driver = replace(prometheus_cfg, namespace=service_name)
        elif metrics_type == "azure_monitor":
            azure_monitor_cfg = cast(DriverConfig_Metrics_AzureMonitor, config.metrics.driver)
            config.metrics.driver = replace(azure_monitor_cfg, namespace=service_name)

        # Refresh module-level service logger to use the current default
        from app import service as reporting_service_module

        reporting_service_module.logger = get_logger(reporting_service_module.__name__)

        # Create adapters using typed factory pattern
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
        document_store = create_document_store(
            config.document_store,
            enable_validation=True,
            strict_validation=True,
            schema_provider=create_schema_provider(schema_type="documents"),
        )
        try:
            document_store.connect()
            logger.info("Document store connected successfully")
        except DocumentStoreConnectionError as e:
            logger.error(f"Failed to connect to document store: {e}")
            raise

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector(config.metrics)

        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter(config.error_reporter)

        # Create optional vector store and embedding provider for topic search
        vector_store = None
        embedding_provider = None

        # Vector store + embedding backend for topic search.
        try:
            logger.info("Creating embedding provider for topic search...")
            from copilot_embedding import create_embedding_provider
            from copilot_vectorstore import create_vector_store

            embedding_provider = create_embedding_provider(config.embedding_backend)
            logger.info("Embedding provider created successfully")

            # Determine embedding dimension (prefer explicit provider dimension when available).
            if hasattr(embedding_provider, "dimension"):
                embedding_dimension = embedding_provider.dimension
            else:
                logger.info("Embedding dimension not configured; detecting via test embedding")
                embedding_dimension = len(embedding_provider.embed("test"))
            logger.info(f"Using embedding dimension: {embedding_dimension}")

            vector_store_config = config.vector_store
            vector_store_type = str(vector_store_config.vector_store_type).lower()
            if vector_store_type in {"qdrant", "azure_ai_search"}:
                if vector_store_type == "qdrant":
                    qdrant_cfg = cast(DriverConfig_VectorStore_Qdrant, vector_store_config.driver)
                    vector_store_config = replace(vector_store_config, driver=replace(qdrant_cfg, vector_size=embedding_dimension))
                else:
                    azure_search_cfg = cast(DriverConfig_VectorStore_AzureAiSearch, vector_store_config.driver)
                    vector_store_config = replace(
                        vector_store_config,
                        driver=replace(azure_search_cfg, vector_size=embedding_dimension),
                    )
            elif vector_store_type == "faiss":
                faiss_cfg = cast(DriverConfig_VectorStore_Faiss, vector_store_config.driver)
                vector_store_config = replace(vector_store_config, driver=replace(faiss_cfg, dimension=embedding_dimension))

            logger.info("Creating vector store for topic search...")
            vector_store = create_vector_store(vector_store_config)
            logger.info("Vector store created successfully")
            logger.info("Topic-based search is enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize topic search components: {e}")
            logger.warning("Topic-based search will not be available")
            vector_store = None
            embedding_provider = None

        # Create reporting service
        reporting_service = ReportingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            webhook_url=config.service_settings.notify_webhook_url if config.service_settings.notify_webhook_url else None,
            notify_enabled=bool(config.service_settings.notify_enabled),
            webhook_summary_max_length=int(config.service_settings.webhook_summary_max_length or 0),
            vector_store=vector_store,
            embedding_provider=embedding_provider,
        )

        logger.info(f"Webhook notifications: {'enabled' if config.service_settings.notify_enabled else 'disabled'}")
        if config.service_settings.notify_enabled and config.service_settings.notify_webhook_url:
            logger.info(f"Webhook URL: {config.service_settings.notify_webhook_url}")

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(reporting_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")

        # Start FastAPI server
        http_host = str(config.service_settings.http_host or "0.0.0.0")
        http_port = int(config.service_settings.http_port or 8080)
        logger.info(f"Starting HTTP server on port {http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_level = getattr(config.logger.driver, "level", "INFO")
        log_config = create_uvicorn_log_config(service_name="reporting", log_level=log_level)
        uvicorn.run(app, host=http_host, port=http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start reporting service: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        if reporting_service:
            if reporting_service.subscriber:
                reporting_service.subscriber.disconnect()
            if reporting_service.publisher:
                reporting_service.publisher.disconnect()
            if reporting_service.document_store:
                reporting_service.document_store.disconnect()


if __name__ == "__main__":
    main()
