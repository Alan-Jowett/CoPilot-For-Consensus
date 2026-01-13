# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Reporting Service: Persist and serve summaries via REST and notifications."""

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
from fastapi import FastAPI, HTTPException, Query

# Configure structured JSON logging
logger_config = load_driver_config(service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": "reporting"})
logger = create_logger("stdout", logger_config)
set_default_logger(logger)

from app import __version__
from app import service as reporting_service_module
from app.service import ReportingService
reporting_service_module.logger = get_logger(reporting_service_module.__name__)

# Create FastAPI app
app = FastAPI(title="Reporting Service", version=__version__)

# Global service instance
reporting_service = None


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

    logger.info(f"Starting Reporting Service (version {__version__})")

    try:
        # Load configuration using config adapter
        config = load_service_config("reporting")
        logger.info("Configuration loaded successfully")

        # Conditionally add JWT authentication middleware based on config
        # Note: Middleware must be added before routes are accessed, but routes are already
        # defined at module level. For proper middleware setup, we would need to restructure
        # the app initialization. For now, skip middleware addition if app has already started.
        if config.jwt_auth_enabled:
            logger.info("JWT authentication is enabled")
            try:
                from copilot_auth import create_jwt_middleware
                auth_service_url = getattr(config, 'auth_service_url', None)
                audience = getattr(config, 'service_audience', None)
                auth_middleware = create_jwt_middleware(
                    auth_service_url=auth_service_url,
                    audience=audience,
                    required_roles=["reader"],
                    public_paths=["/", "/health", "/readyz", "/docs", "/openapi.json"],
                )
                try:
                    app.add_middleware(auth_middleware)
                except RuntimeError as e:
                    # App already started - middleware cannot be added
                    logger.warning(f"Cannot add middleware after app has started: {e}")
            except ImportError:
                logger.debug("copilot_auth module not available - JWT authentication disabled")
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")

        # Create adapters using factory pattern
        logger.info("Creating message bus publisher from adapter configuration")
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
            if message_bus_adapter.driver_name.lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")

        logger.info("Creating message bus subscriber from adapter configuration")
        subscriber = create_subscriber(
            driver_name=message_bus_adapter.driver_name,
            driver_config=message_bus_adapter.driver_config,
            enable_validation=True,
            strict_validation=True,
        )
        try:
            subscriber.connect()
        except Exception as e:
            logger.error(f"Failed to connect subscriber to message bus: {e}")
            raise ConnectionError("Subscriber failed to connect to message bus")

        logger.info("Creating document store from adapter configuration")
        document_store_adapter = config.get_adapter("document_store")
        if document_store_adapter is None:
            raise ValueError("document_store adapter is required")

        document_store = create_document_store(
            driver_name=document_store_adapter.driver_name,
            driver_config=document_store_adapter.driver_config,
            enable_validation=True,
            strict_validation=True,
        )

        # connect() raises on failure; None return indicates success
        document_store.connect()
        logger.info("Document store connected successfully")

        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
            metrics_adapter = config.get_adapter("metrics")
            if metrics_adapter is not None:
                from copilot_config import DriverConfig
                metrics_driver_config = DriverConfig(
                    driver_name=metrics_adapter.driver_name,
                    config={**metrics_adapter.driver_config.config, "job": "reporting"},
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
            error_reporter = create_error_reporter(
                driver_name=config.error_reporter_type,
            )

        # Create optional vector store and embedding provider for topic search
        vector_store = None
        embedding_provider = None

        # Check if we have vector store configuration via adapter
        vector_store_adapter = config.get_adapter("vector_store")
        embedding_adapter = config.get_adapter("embedding_provider")

        if vector_store_adapter is not None and embedding_adapter is not None:
            try:
                logger.info("Creating embedding provider for topic search from adapter configuration")
                from copilot_embedding import create_embedding_provider
                embedding_provider = create_embedding_provider(
                    driver_name=embedding_adapter.driver_name,
                    driver_config=embedding_adapter.driver_config,
                )
                logger.info("Embedding provider created successfully")

                # Get embedding dimension from adapter config
                embedding_dimension = embedding_adapter.driver_config.get("dimension")
                if embedding_dimension is None:
                    logger.info("Embedding dimension not configured; detecting via test embedding")
                    test_embedding = embedding_provider.embed("test")
                    embedding_dimension = len(test_embedding)
                logger.info(f"Using embedding dimension: {embedding_dimension}")

                logger.info("Creating vector store for topic search from adapter configuration")
                from copilot_vectorstore import create_vector_store
                vector_store = create_vector_store(
                    driver_name=vector_store_adapter.driver_name,
                    driver_config=vector_store_adapter.driver_config,
                    dimension=embedding_dimension
                )
                logger.info("Vector store created successfully")
                logger.info("Topic-based search is enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize topic search components: {e}")
                logger.warning("Topic-based search will not be available")
                vector_store = None
                embedding_provider = None
        else:
            logger.info("Vector store or embedding provider not configured - topic search will not be available")

        # Create reporting service
        reporting_service = ReportingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            webhook_url=config.notify_webhook_url if config.notify_webhook_url else None,
            notify_enabled=config.notify_enabled,
            webhook_summary_max_length=config.webhook_summary_max_length,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
        )

        logger.info(f"Webhook notifications: {'enabled' if config.notify_enabled else 'disabled'}")
        if config.notify_enabled and config.notify_webhook_url:
            logger.info(f"Webhook URL: {config.notify_webhook_url}")

        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(reporting_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")

        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")

        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="reporting", log_level="INFO")
        uvicorn.run(app, host=config.http_host, port=config.http_port, log_config=log_config, access_log=False)

    except Exception as e:
        logger.error(f"Failed to start reporting service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
