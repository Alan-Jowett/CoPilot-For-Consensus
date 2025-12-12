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
from fastapi.responses import JSONResponse
import uvicorn

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
    """
    try:
        service.start()
        # Start consuming events (blocking)
        service.subscriber.start_consuming()
    except KeyboardInterrupt:
        logger.info("Subscriber interrupted")
    except Exception as e:
        logger.error(f"Subscriber error: {e}", exc_info=True)


def main():
    """Main entry point for the reporting service."""
    global reporting_service
    
    logger.info(f"Starting Reporting Service (version {__version__})")
    
    try:
        # Load configuration from environment
        message_bus_type = os.getenv("MESSAGE_BUS_TYPE", "rabbitmq")
        message_bus_host = os.getenv("MESSAGE_BUS_HOST", "messagebus")
        message_bus_port = int(os.getenv("MESSAGE_BUS_PORT", "5672"))
        message_bus_user = os.getenv("MESSAGE_BUS_USER", "guest")
        message_bus_password = os.getenv("MESSAGE_BUS_PASSWORD", "guest")
        
        doc_store_type = os.getenv("DOC_STORE_TYPE", "mongodb")
        doc_store_host = os.getenv("DOC_DB_HOST", "documentdb")
        doc_store_port = int(os.getenv("DOC_DB_PORT", "27017"))
        doc_store_name = os.getenv("DOC_DB_NAME", "copilot")
        doc_store_user = os.getenv("DOC_DB_USER", "")
        doc_store_password = os.getenv("DOC_DB_PASSWORD", "")
        
        # Notification configuration
        webhook_url = os.getenv("NOTIFY_WEBHOOK_URL", "")
        notify_enabled = os.getenv("NOTIFY_ENABLED", "false").lower() in ("true", "1", "yes")
        webhook_summary_max_length = int(os.getenv("WEBHOOK_SUMMARY_MAX_LENGTH", "500"))
        
        # Create adapters
        logger.info("Creating message bus publisher...")
        publisher = create_publisher(
            message_bus_type=message_bus_type,
            host=message_bus_host,
            port=message_bus_port,
            username=message_bus_user,
            password=message_bus_password,
        )
        
        logger.info("Creating message bus subscriber...")
        subscriber = create_subscriber(
            message_bus_type=message_bus_type,
            host=message_bus_host,
            port=message_bus_port,
            username=message_bus_user,
            password=message_bus_password,
        )
        
        logger.info("Creating document store...")
        document_store = create_document_store(
            store_type=doc_store_type,
            host=doc_store_host,
            port=doc_store_port,
            database=doc_store_name,
            username=doc_store_user if doc_store_user else None,
            password=doc_store_password if doc_store_password else None,
        )
        
        # Create optional services
        metrics_collector = None
        error_reporter = None
        
        try:
            metrics_collector = create_metrics_collector()
            logger.info("Metrics collector created")
        except Exception as e:
            logger.warning(f"Could not create metrics collector: {e}")
        
        try:
            error_reporter = create_error_reporter()
            logger.info("Error reporter created")
        except Exception as e:
            logger.warning(f"Could not create error reporter: {e}")
        
        # Create reporting service
        reporting_service = ReportingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            webhook_url=webhook_url if webhook_url else None,
            notify_enabled=notify_enabled,
            webhook_summary_max_length=webhook_summary_max_length,
        )
        
        logger.info(f"Webhook notifications: {'enabled' if notify_enabled else 'disabled'}")
        if notify_enabled and webhook_url:
            logger.info(f"Webhook URL: {webhook_url}")
        
        # Start subscriber in background thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(reporting_service,),
            daemon=True,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8080"))
        logger.info(f"Starting HTTP server on port {http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=http_port)
        
    except Exception as e:
        logger.error(f"Failed to start reporting service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
