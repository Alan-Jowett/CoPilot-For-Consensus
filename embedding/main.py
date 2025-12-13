# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding Service: Generate vector embeddings for text chunks."""

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
from copilot_vectorstore import create_vector_store
from copilot_embedding import create_embedding_provider
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter

from app import __version__
from app.service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Embedding Service", version=__version__)

# Global service instance (consistent with other services in the codebase)
embedding_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global embedding_service
    
    stats = embedding_service.get_stats() if embedding_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "embedding",
        "version": __version__,
        "backend": stats.get("embedding_backend", "unknown"),
        "model": stats.get("embedding_model", "unknown"),
        "dimension": stats.get("embedding_dimension", 0),
        "embeddings_generated_total": stats.get("embeddings_generated_total", 0),
        "uptime_seconds": stats.get("uptime_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get embedding statistics."""
    global embedding_service
    
    if not embedding_service:
        return {"error": "Service not initialized"}
    
    return embedding_service.get_stats()


def start_subscriber_thread(service: EmbeddingService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Embedding service instance
        
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
    """Main entry point for the embedding service."""
    global embedding_service
    
    logger.info(f"Starting Embedding Service (version {__version__})")
    
    try:
        # Load configuration using config adapter
        config = load_typed_config("embedding")
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
            password=config.message_bus_password,            queue_name="embedding-service",        )
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
        if not document_store.connect():
            logger.error("Failed to connect to document store.")
            raise ConnectionError("Document store failed to connect")
        
        logger.info(f"Creating vector store ({config.vector_store_type})...")
        vector_store = create_vector_store(
            backend=config.vector_store_type,
            dimension=config.embedding_dimension,
            host=config.vector_store_host if config.vector_store_type == "qdrant" else None,
            port=config.vector_store_port if config.vector_store_type == "qdrant" else None,
        )
        if hasattr(vector_store, "connect"):
            if not vector_store.connect() and str(config.vector_store_type).lower() != "inmemory":
                logger.error("Failed to connect to vector store.")
                raise ConnectionError("Vector store failed to connect")
        
        logger.info(f"Creating embedding provider ({config.embedding_backend})...")
        embedding_provider = create_embedding_provider(
            backend=config.embedding_backend,
            model=config.embedding_model,
            dimension=config.embedding_dimension,
            device=config.device,
        )
        
        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector()
        
        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter()
        
        # Create embedding service
        embedding_service = EmbeddingService(
            document_store=document_store,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            embedding_model=config.embedding_model,
            embedding_backend=config.embedding_backend,
            embedding_dimension=config.embedding_dimension,
            batch_size=config.batch_size,
            max_retries=config.max_retries,
            retry_backoff_seconds=config.retry_backoff,
        )
        
        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(embedding_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
        
    except Exception as e:
        logger.error(f"Failed to start embedding service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
