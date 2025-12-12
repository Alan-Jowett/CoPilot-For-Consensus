# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Orchestration Service: Coordinate summarization and analysis tasks."""

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
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter

from app import __version__
from app.service import OrchestrationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Orchestration Service", version=__version__)

# Global service instance
orchestration_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global orchestration_service
    
    stats = orchestration_service.get_stats() if orchestration_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "orchestration",
        "version": __version__,
        "events_processed_total": stats.get("events_processed", 0),
        "threads_orchestrated_total": stats.get("threads_orchestrated", 0),
        "failures_total": stats.get("failures_count", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        "config": stats.get("config", {}),
    }


@app.get("/stats")
def get_stats():
    """Get orchestration statistics."""
    global orchestration_service
    
    if not orchestration_service:
        return {"error": "Service not initialized"}
    
    return orchestration_service.get_stats()


def start_subscriber_thread(service: OrchestrationService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Orchestration service instance
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
    """Main entry point for the orchestration service."""
    global orchestration_service
    
    logger.info(f"Starting Orchestration Service (version {__version__})")
    
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
        
        vector_store_type = os.getenv("VECTOR_STORE_TYPE", "inmemory")
        vector_store_host = os.getenv("VECTOR_DB_HOST", "vectorstore")
        vector_store_port = int(os.getenv("VECTOR_DB_PORT", "6333"))
        vector_collection = os.getenv("VECTOR_DB_COLLECTION", "message_embeddings")
        
        # Orchestration configuration
        top_k = int(os.getenv("TOP_K", "12"))
        context_window_tokens = int(os.getenv("CONTEXT_WINDOW_TOKENS", "3000"))
        llm_backend = os.getenv("LLM_BACKEND", "ollama")
        llm_model = os.getenv("LLM_MODEL", "mistral")
        llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
        
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
        
        logger.info(f"Creating vector store (type: {vector_store_type})...")
        vector_store = create_vector_store(
            store_type=vector_store_type,
            host=vector_store_host,
            port=vector_store_port,
            collection_name=vector_collection,
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
        
        # Create orchestration service
        orchestration_service = OrchestrationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            top_k=top_k,
            context_window_tokens=context_window_tokens,
            llm_backend=llm_backend,
            llm_model=llm_model,
            llm_temperature=llm_temperature,
            llm_max_tokens=llm_max_tokens,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in background thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(orchestration_service,),
            daemon=True,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8000"))
        logger.info(f"Starting HTTP server on port {http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=http_port)
        
    except Exception as e:
        logger.error(f"Failed to start orchestration service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
