# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Parsing Service: Convert raw .mbox files into structured JSON."""

import logging
import os
import sys
import threading

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
import uvicorn

from copilot_events import create_publisher, create_subscriber
from copilot_storage import create_document_store
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter

from app import __version__
from app.service import ParsingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Parsing Service", version=__version__)

# Global service instance
parsing_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global parsing_service
    
    stats = parsing_service.get_stats() if parsing_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "parsing",
        "version": __version__,
        "messages_parsed_total": stats.get("messages_parsed", 0),
        "threads_created_total": stats.get("threads_created", 0),
        "archives_processed_total": stats.get("archives_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def stats():
    """Get parsing statistics."""
    global parsing_service
    
    if not parsing_service:
        return {"error": "Service not initialized"}
    
    return parsing_service.get_stats()


def start_subscriber_thread(service: ParsingService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Parsing service instance
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
    """Main entry point for the parsing service."""
    global parsing_service
    
    logger.info(f"Starting Parsing Service (version {__version__})")
    
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
        doc_store_user = os.getenv("DOC_DB_USER")
        doc_store_password = os.getenv("DOC_DB_PASSWORD")
        
        metrics_backend = os.getenv("METRICS_BACKEND", "noop")
        error_reporter_type = os.getenv("ERROR_REPORTER_TYPE", "noop")
        
        log_level = os.getenv("LOG_LEVEL", "INFO")
        logging.getLogger().setLevel(log_level)
        
        # Create event publisher
        logger.info(f"Creating event publisher ({message_bus_type})")
        publisher = create_publisher(
            message_bus_type=message_bus_type,
            host=message_bus_host,
            port=message_bus_port,
            username=message_bus_user,
            password=message_bus_password,
        )
        
        if not publisher.connect():
            logger.warning("Failed to connect publisher to message bus. Will continue with noop publisher.")
        
        # Create event subscriber
        logger.info(f"Creating event subscriber ({message_bus_type})")
        subscriber = create_subscriber(
            message_bus_type=message_bus_type,
            host=message_bus_host,
            port=message_bus_port,
            username=message_bus_user,
            password=message_bus_password,
        )
        
        if not subscriber.connect():
            logger.error("Failed to connect subscriber to message bus")
            sys.exit(1)
        
        # Create document store
        logger.info(f"Creating document store ({doc_store_type})")
        document_store = create_document_store(
            store_type=doc_store_type,
            host=doc_store_host,
            port=doc_store_port,
            database=doc_store_name,
            username=doc_store_user,
            password=doc_store_password,
        )
        
        if not document_store.connect():
            logger.error("Failed to connect to document store")
            sys.exit(1)
        
        # Create metrics collector
        metrics_collector = create_metrics_collector(backend=metrics_backend)
        
        # Create error reporter
        error_reporter = create_error_reporter(reporter_type=error_reporter_type)
        
        # Create parsing service
        parsing_service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in a separate thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(parsing_service,),
            daemon=True,
        )
        subscriber_thread.start()
        
        # Start FastAPI server (blocking)
        port = int(os.getenv("PORT", "8000"))
        logger.info(f"Starting FastAPI server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
        
    except KeyboardInterrupt:
        logger.info("Shutting down parsing service")
    except Exception as e:
        logger.error(f"Fatal error in parsing service: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        if parsing_service:
            if parsing_service.subscriber:
                parsing_service.subscriber.disconnect()
            if parsing_service.publisher:
                parsing_service.publisher.disconnect()
            if parsing_service.document_store:
                parsing_service.document_store.disconnect()


if __name__ == "__main__":
    main()
