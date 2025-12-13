# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Reporting Service: Persist and serve summaries via REST and notifications."""

import logging
import os
import sys
import threading

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Query
import uvicorn

from copilot_config import load_typed_config
from copilot_events import create_publisher, create_subscriber
from copilot_storage import create_document_store
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter

from app import __version__
from app.service import ReportingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
        config = load_typed_config("reporting")
        logger.info("Configuration loaded successfully")
        
        # Create adapters
        logger.info("Creating message bus publisher...")
        publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )
        
        logger.info("Creating message bus subscriber...")
        subscriber = create_subscriber(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
            queue_name="reporting-service",
        )
        
        if not subscriber.connect():
            logger.error("Failed to connect subscriber to message bus.")
            raise ConnectionError("Subscriber failed to connect to message bus")
        
        document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        
        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector()
        
        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter()
        
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
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
        
    except Exception as e:
        logger.error(f"Failed to start reporting service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
