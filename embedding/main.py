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
    """Main entry point for the embedding service."""
    global embedding_service
    
    logger.info(f"Starting Embedding Service (version {__version__})")
    
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
        
        vector_store_type = os.getenv("VECTOR_STORE_TYPE", "faiss")
        vector_store_host = os.getenv("VECTOR_DB_HOST", "vectorstore")
        vector_store_port = int(os.getenv("VECTOR_DB_PORT", "6333"))
        
        # Embedding configuration
        embedding_backend = os.getenv("EMBEDDING_BACKEND", "sentencetransformers")
        embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "384"))
        batch_size = int(os.getenv("BATCH_SIZE", "32"))
        device = os.getenv("DEVICE", "cpu")
        
        # Retry configuration
        max_retries = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
        retry_backoff = int(os.getenv("RETRY_BACKOFF_SECONDS", "5"))
        
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
        
        logger.info(f"Creating vector store ({vector_store_type})...")
        vector_store = create_vector_store(
            backend=vector_store_type,
            dimension=embedding_dimension,
            host=vector_store_host if vector_store_type == "qdrant" else None,
            port=vector_store_port if vector_store_type == "qdrant" else None,
        )
        
        logger.info(f"Creating embedding provider ({embedding_backend})...")
        embedding_provider = create_embedding_provider(
            backend=embedding_backend,
            model=embedding_model,
            dimension=embedding_dimension,
            device=device,
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
        
        # Create embedding service
        embedding_service = EmbeddingService(
            document_store=document_store,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
            embedding_model=embedding_model,
            embedding_backend=embedding_backend,
            embedding_dimension=embedding_dimension,
            batch_size=batch_size,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff,
        )
        
        # Start subscriber in background thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(embedding_service,),
            daemon=True,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8000"))
        logger.info(f"Starting HTTP server on port {http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=http_port)
        
    except Exception as e:
        logger.error(f"Failed to start embedding service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
