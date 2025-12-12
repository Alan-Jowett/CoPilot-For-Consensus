# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Chunking Service: Split long email bodies into semantically coherent chunks."""

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
from copilot_chunking import create_chunker

from app import __version__
from app.service import ChunkingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Chunking Service", version=__version__)

# Global service instance
chunking_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global chunking_service
    
    stats = chunking_service.get_stats() if chunking_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "chunking",
        "version": __version__,
        "chunks_created_total": stats.get("chunks_created_total", 0),
        "messages_processed_total": stats.get("messages_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get chunking statistics."""
    global chunking_service
    
    if not chunking_service:
        return {"error": "Service not initialized"}
    
    return chunking_service.get_stats()


def start_subscriber_thread(service: ChunkingService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Chunking service instance
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
    """Main entry point for the chunking service."""
    global chunking_service
    
    logger.info(f"Starting Chunking Service (version {__version__})")
    
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
        
        # Chunking configuration
        chunking_strategy = os.getenv("CHUNKING_STRATEGY", "token_window")
        chunk_size = int(os.getenv("CHUNK_SIZE_TOKENS", "384"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))
        min_chunk_size = int(os.getenv("MIN_CHUNK_SIZE_TOKENS", "100"))
        max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE_TOKENS", "512"))
        
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
        
        # Create chunker
        logger.info(f"Creating chunker with strategy: {chunking_strategy}")
        chunker = create_chunker(
            strategy=chunking_strategy,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
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
        
        # Create chunking service
        chunking_service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in background thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(chunking_service,),
            daemon=True,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8000"))
        logger.info(f"Starting HTTP server on port {http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=http_port)
        
    except Exception as e:
        logger.error(f"Failed to start chunking service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
