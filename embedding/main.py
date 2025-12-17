# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding Service: Generate vector embeddings for text chunks."""

import os
import sys
import threading
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
import uvicorn

from copilot_config import load_typed_config
from copilot_events import create_publisher, create_subscriber
from copilot_storage import create_document_store, ValidatingDocumentStore, DocumentStoreConnectionError
from copilot_schema_validation import FileSchemaProvider
from copilot_vectorstore import create_vector_store
from copilot_embedding import create_embedding_provider
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter
from copilot_logging import create_logger

from app import __version__
from app.service import EmbeddingService

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="embedding")

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
        logger.error(f"Subscriber error: {e}")
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
        base_document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        try:
            base_document_store.connect()
        except DocumentStoreConnectionError as e:
            logger.error(f"Failed to connect to document store: {e}")
            raise
        
        # Wrap with schema validation
        logger.info("Wrapping document store with schema validation...")
        document_schema_provider = FileSchemaProvider(
            # In container, this file is at /app/main.py. Use parent (/app).
            schema_dir=Path(__file__).parent / "documents" / "schemas" / "documents"
        )
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=document_schema_provider,
            strict=True,
        )
        
        logger.info(f"Creating vector store ({config.vector_store_type})...")
        
        # Build vector store kwargs based on backend type
        vector_store_kwargs = {
            "backend": config.vector_store_type,
        }
        
        if config.vector_store_type.lower() == "faiss":
            # Validate required config attributes
            if not hasattr(config, "vector_store_index_type"):
                raise ValueError("vector_store_index_type configuration is required for FAISS backend")
            
            vector_store_kwargs.update({
                "dimension": config.embedding_dimension,
                "index_type": config.vector_store_index_type,
                "persist_path": config.vector_store_persist_path if hasattr(config, "vector_store_persist_path") else None,
            })
        elif config.vector_store_type.lower() == "qdrant":
            # Validate required config attributes
            required_attrs = ["vector_store_host", "vector_store_port", "vector_store_collection", 
                            "vector_store_distance", "vector_store_batch_size"]
            missing = [attr for attr in required_attrs if not hasattr(config, attr)]
            if missing:
                raise ValueError(f"Missing required Qdrant configuration: {', '.join(missing)}")
            
            vector_store_kwargs.update({
                "dimension": config.embedding_dimension,
                "host": config.vector_store_host,
                "port": config.vector_store_port,
                "collection_name": config.vector_store_collection,
                "distance": config.vector_store_distance,
                "upsert_batch_size": config.vector_store_batch_size,
                "api_key": config.vector_store_api_key if hasattr(config, "vector_store_api_key") else None,
            })
        
        vector_store = create_vector_store(**vector_store_kwargs)
        
        if hasattr(vector_store, "connect"):
            if not vector_store.connect() and str(config.vector_store_type).lower() != "inmemory":
                logger.error("Failed to connect to vector store.")
                raise ConnectionError("Vector store failed to connect")
        
        logger.info(f"Creating embedding provider ({config.embedding_backend})...")
        
        # Build embedding provider kwargs based on backend type
        embedding_kwargs = {
            "backend": config.embedding_backend,
            "model": config.embedding_model,
        }
        
        if config.embedding_backend.lower() == "mock":
            embedding_kwargs["dimension"] = config.embedding_dimension
        elif config.embedding_backend.lower() in ("sentencetransformers", "huggingface"):
            embedding_kwargs["device"] = config.device
            if hasattr(config, "model_cache_dir"):
                embedding_kwargs["cache_dir"] = config.model_cache_dir
        elif config.embedding_backend.lower() == "openai":
            if not hasattr(config, "openai_api_key"):
                raise ValueError("openai_api_key configuration is required for OpenAI embedding backend")
            embedding_kwargs["api_key"] = config.openai_api_key
            if not embedding_kwargs["api_key"]:
                raise ValueError("openai_api_key configuration is required for OpenAI embedding backend and cannot be empty")
        elif config.embedding_backend.lower() == "azure":
            # Validate required Azure config attributes
            required_attrs = ["azure_openai_key", "azure_openai_endpoint"]
            missing = [attr for attr in required_attrs if not hasattr(config, attr)]
            if missing:
                raise ValueError(f"Missing required Azure embedding configuration: {', '.join(missing)}")
            
            embedding_kwargs["api_key"] = config.azure_openai_key
            embedding_kwargs["api_base"] = config.azure_openai_endpoint
            embedding_kwargs["api_version"] = config.azure_openai_api_version if hasattr(config, "azure_openai_api_version") else None
            embedding_kwargs["deployment_name"] = config.azure_openai_deployment if hasattr(config, "azure_openai_deployment") else None
            
            if not embedding_kwargs["api_key"]:
                raise ValueError("azure_openai_key configuration is required for Azure embedding backend and cannot be empty")
            if not embedding_kwargs["api_base"]:
                raise ValueError("azure_openai_endpoint configuration is required for Azure embedding backend and cannot be empty")
        
        embedding_provider = create_embedding_provider(**embedding_kwargs)
        
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
        logger.error(f"Failed to start embedding service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
