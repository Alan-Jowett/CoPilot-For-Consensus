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

from copilot_config import load_typed_config
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
        # Load configuration from schema
        config = load_config("summarization")
        
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
            password=config.message_bus_password,
        )
        
        logger.info("Creating document store...")
        document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        
        logger.info("Creating vector store...")
        vector_store = create_vector_store(
            store_type=config.vector_store_type,
            host=config.vector_store_host if config.vector_store_type != "inmemory" else None,
            port=config.vector_store_port if config.vector_store_type != "inmemory" else None,
            collection_name="message_embeddings",
        )
        
        # Create summarizer
        logger.info(f"Creating summarizer with backend: {config.llm_backend}")
        summarizer = SummarizerFactory.create_summarizer(
            provider=config.llm_backend,
            model=config.llm_model,
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
            top_k=config.top_k,
            citation_count=12,
            retry_max_attempts=config.max_retries,
            retry_backoff_seconds=config.retry_delay,
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
        logger.info(f"Starting HTTP server on port {config.http_port}...")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
        
    except Exception as e:
        logger.error(f"Failed to start summarization service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
