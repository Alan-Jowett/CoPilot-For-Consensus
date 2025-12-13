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
from copilot_schema_validation import FileSchemaProvider

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


def get_service() -> ChunkingService:
    """Get the chunking service instance from app state.
    
    Returns:
        ChunkingService instance
        
    Raises:
        RuntimeError: If service is not initialized in app state
    """
    if not hasattr(app.state, "chunking_service") or app.state.chunking_service is None:
        raise RuntimeError("Service not initialized")
    return app.state.chunking_service


@app.get("/health")
def health():
    """Health check endpoint."""
    try:
        service = get_service()
        stats = service.get_stats()
    except RuntimeError:
        stats = {}
    
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
    try:
        service = get_service()
        return service.get_stats()
    except RuntimeError:
        return {"error": "Service not initialized"}


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
        if not publisher.connect():
            if str(config.message_bus_type).lower() != "noop":
                logger.error("Failed to connect publisher to message bus. Failing fast.")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning("Failed to connect publisher to message bus. Continuing with noop publisher.")
        
        logger.info("Creating message bus subscriber...")
        subscriber = create_subscriber(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
            queue_name="chunking-service",
        )
        if not subscriber.connect():
            logger.error("Failed to connect subscriber to message bus.")
            raise ConnectionError("Subscriber failed to connect to message bus")
        
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
        
        # Validate document store permissions (read/write access)
        logger.info("Validating document store permissions...")
        if str(config.doc_store_type).lower() != "inmemory":
            try:
                # Test write permission
                test_doc_id = document_store.insert_document("_startup_validation", {"test": True})
                # Test read permission
                retrieved = document_store.get_document("_startup_validation", test_doc_id)
                if retrieved is None:
                    logger.error("Failed to read test document from document store.")
                    raise PermissionError("Document store read permission validation failed")
                # Clean up test document
                document_store.delete_document("_startup_validation", test_doc_id)
                logger.info("Document store permissions validated successfully")
            except Exception as e:
                logger.error(f"Document store permission validation failed: {e}")
                raise PermissionError(f"Document store does not have required read/write permissions: {e}")
        
        # Validate required event schemas can be loaded
        logger.info("Validating event schemas...")
        schema_provider = FileSchemaProvider()
        required_schemas = ["JSONParsed", "ChunksPrepared", "ChunkingFailed"]
        for schema_name in required_schemas:
            schema = schema_provider.get_schema(schema_name)
            if schema is None:
                logger.error(f"Failed to load required schema: {schema_name}")
                raise RuntimeError(f"Required event schema '{schema_name}' could not be loaded")
        logger.info(f"Successfully validated {len(required_schemas)} required event schemas")
        
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
        service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Store service in FastAPI app state for dependency injection
        app.state.chunking_service = service
        
        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(service,),
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
