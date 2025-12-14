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

from copilot_config import load_typed_config
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
    """Main entry point for the chunking service."""
    global chunking_service
    
    logger.info(f"Starting Chunking Service (version {__version__})")
    
    try:
        # Load configuration using config adapter
        config = load_typed_config("chunking")
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
            password=config.message_bus_password,            queue_name="chunking-service",        )
        
        logger.info("Creating document store...")
        document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        
        logger.info("Connecting to document store...")
        document_store.connect()
        logger.info("Document store connected successfully")
        
        # Create chunker
        logger.info(f"Creating chunker with strategy: {config.chunking_strategy}")
        chunker = create_chunker(
            strategy=config.chunking_strategy,
            chunk_size=config.chunk_size,
            overlap=config.chunk_overlap,
            min_chunk_size=config.min_chunk_size,
            max_chunk_size=config.max_chunk_size,
        )
        
        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector()
        
        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter()
        
        # Create chunking service
        chunking_service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(chunking_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
        
    except Exception as e:
        logger.error(f"Failed to start chunking service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
