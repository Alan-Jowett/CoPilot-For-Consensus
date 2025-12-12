# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization Service: Generate citation-rich summaries from orchestrated requests."""

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
from copilot_summarization import SummarizerFactory

from app import __version__
from app.service import SummarizationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Summarization Service", version=__version__)

# Global service instance
summarization_service = None


@app.get("/health")
def health():
    """Health check endpoint."""
    global summarization_service
    
    stats = summarization_service.get_stats() if summarization_service is not None else {}
    
    return {
        "status": "healthy",
        "service": "summarization",
        "version": __version__,
        "summaries_generated": stats.get("summaries_generated", 0),
        "summarization_failures": stats.get("summarization_failures", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def get_stats():
    """Get summarization statistics."""
    global summarization_service
    
    if not summarization_service:
        return {"error": "Service not initialized"}
    
    return summarization_service.get_stats()


def start_subscriber_thread(service: SummarizationService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Summarization service instance
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
    """Main entry point for the summarization service."""
    global summarization_service
    
    logger.info(f"Starting Summarization Service (version {__version__})")
    
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
        vector_store_collection = os.getenv("VECTOR_DB_COLLECTION", "message_embeddings")
        
        # Summarization configuration
        llm_backend = os.getenv("LLM_BACKEND", "mock")
        llm_model = os.getenv("LLM_MODEL", "mistral")
        top_k = int(os.getenv("TOP_K", "12"))
        citation_count = int(os.getenv("CITATION_COUNT", "12"))
        retry_max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
        retry_backoff_seconds = int(os.getenv("RETRY_BACKOFF_SECONDS", "5"))
        
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
        
        logger.info("Creating vector store...")
        vector_store = create_vector_store(
            store_type=vector_store_type,
            host=vector_store_host if vector_store_type != "inmemory" else None,
            port=vector_store_port if vector_store_type != "inmemory" else None,
            collection_name=vector_store_collection,
        )
        
        # Create summarizer
        logger.info(f"Creating summarizer with backend: {llm_backend}")
        summarizer = SummarizerFactory.create_summarizer(
            provider=llm_backend,
            model=llm_model,
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
        
        # Create summarization service
        summarization_service = SummarizationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            summarizer=summarizer,
            top_k=top_k,
            citation_count=citation_count,
            retry_max_attempts=retry_max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in background thread
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(summarization_service,),
            daemon=True,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        http_port = int(os.getenv("HTTP_PORT", "8000"))
        logger.info(f"Starting HTTP server on port {http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=http_port)
        
    except Exception as e:
        logger.error(f"Failed to start summarization service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
