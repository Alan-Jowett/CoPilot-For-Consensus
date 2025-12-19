# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization Service: Generate citation-rich summaries from orchestrated requests."""

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
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter
from copilot_summarization import SummarizerFactory
from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_auth import create_jwt_middleware

from app import __version__
from app.service import SummarizationService

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="summarization")

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
    """Main entry point for the summarization service."""
    global summarization_service
    
    logger.info(f"Starting Summarization Service (version {__version__})")
    
    try:
        # Load configuration from schema with typed access
        config = load_typed_config("summarization")
        
        # Conditionally add JWT authentication middleware based on config
        if getattr(config, 'jwt_auth_enabled', True):
            logger.info("JWT authentication is enabled")
            auth_middleware = create_jwt_middleware(
                required_roles=["processor"],
                public_paths=["/health", "/readyz", "/docs", "/openapi.json"],
            )
            app.add_middleware(auth_middleware)
        else:
            logger.warning("JWT authentication is DISABLED - all endpoints are public")
        
        # Create adapters
        logger.info("Creating message bus publisher...")
        publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )
        try:
            publisher.connect()
        except Exception as e:
            if str(config.message_bus_type).lower() != "noop":
                logger.error(f"Failed to connect publisher to message bus. Failing fast: {e}")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning(f"Failed to connect publisher to message bus. Continuing with noop publisher: {e}")
        
        logger.info("Creating message bus subscriber...")
        subscriber = create_subscriber(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
            queue_name="summarization.requested",
        )
        try:
            subscriber.connect()
        except Exception as e:
            logger.error(f"Failed to connect subscriber to message bus: {e}")
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
            schema_dir=Path(__file__).parent / "documents" / "schemas" / "documents"
        )
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=document_schema_provider,
            strict=True,
        )
        
        logger.info("Creating vector store...")
        
        # Build vector store kwargs based on backend type
        vector_store_kwargs = {
            "backend": config.vector_store_type,
        }
        
        if config.vector_store_type.lower() == "faiss":
            # Validate required config attributes
            if not hasattr(config, "embedding_dimension"):
                raise ValueError("embedding_dimension configuration is required for FAISS backend")
            if not hasattr(config, "vector_store_index_type"):
                raise ValueError("vector_store_index_type configuration is required for FAISS backend")
            
            vector_store_kwargs.update({
                "dimension": config.embedding_dimension,
                "index_type": config.vector_store_index_type,
                "persist_path": config.vector_store_persist_path if hasattr(config, "vector_store_persist_path") else None,
            })
        elif config.vector_store_type.lower() == "qdrant":
            # Validate required config attributes
            required_attrs = ["embedding_dimension", "vector_store_host", "vector_store_port", 
                            "vector_store_collection", "vector_store_distance", "vector_store_batch_size"]
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

        # Connect vector store if required; in-memory typically doesn't need connect
        if hasattr(vector_store, "connect"):
            try:
                result = vector_store.connect()
                if result is False and str(config.vector_store_type).lower() != "inmemory":
                    logger.error("Failed to connect to vector store.")
                    raise ConnectionError("Vector store failed to connect")
            except Exception as e:
                if str(config.vector_store_type).lower() != "inmemory":
                    logger.error(f"Failed to connect to vector store: {e}")
                    raise ConnectionError("Vector store failed to connect")
        
        # Create summarizer
        logger.info(f"Creating summarizer with backend: {config.llm_backend}")
        
        # Build summarizer kwargs based on backend type
        summarizer_kwargs = {
            "provider": config.llm_backend,
            "model": config.llm_model,
        }
        
        if config.llm_backend.lower() in ("openai", "azure", "local", "llamacpp"):
            if config.llm_backend.lower() == "openai":
                if not hasattr(config, "openai_api_key"):
                    raise ValueError("openai_api_key configuration is required for OpenAI summarizer")
                summarizer_kwargs["api_key"] = config.openai_api_key
                if not summarizer_kwargs["api_key"]:
                    raise ValueError("openai_api_key configuration is required for OpenAI summarizer and cannot be empty")
            elif config.llm_backend.lower() == "azure":
                # Validate required Azure config attributes
                required_attrs = ["azure_openai_api_key", "azure_openai_endpoint"]
                missing = [attr for attr in required_attrs if not hasattr(config, attr)]
                if missing:
                    raise ValueError(f"Missing required Azure summarizer configuration: {', '.join(missing)}")
                
                summarizer_kwargs["api_key"] = config.azure_openai_api_key
                summarizer_kwargs["base_url"] = config.azure_openai_endpoint
                if not summarizer_kwargs["api_key"]:
                    raise ValueError("azure_openai_api_key configuration is required for Azure summarizer and cannot be empty")
                if not summarizer_kwargs["base_url"]:
                    raise ValueError("azure_openai_endpoint configuration is required for Azure summarizer and cannot be empty")
            elif config.llm_backend.lower() == "local":
                if not hasattr(config, "local_llm_endpoint"):
                    raise ValueError("local_llm_endpoint configuration is required for local LLM summarizer")
                summarizer_kwargs["base_url"] = config.local_llm_endpoint
                if not summarizer_kwargs["base_url"]:
                    raise ValueError("local_llm_endpoint configuration is required for local LLM summarizer and cannot be empty")
            elif config.llm_backend.lower() == "llamacpp":
                if not hasattr(config, "llamacpp_endpoint"):
                    raise ValueError("llamacpp_endpoint configuration is required for llama.cpp summarizer")
                summarizer_kwargs["base_url"] = config.llamacpp_endpoint
                if not summarizer_kwargs["base_url"]:
                    raise ValueError("llamacpp_endpoint configuration is required for llama.cpp summarizer and cannot be empty")
        
        summarizer = SummarizerFactory.create_summarizer(**summarizer_kwargs)
        
        # Create metrics collector - fail fast on errors
        logger.info("Creating metrics collector...")
        metrics_collector = create_metrics_collector()
        
        # Create error reporter - fail fast on errors
        logger.info("Creating error reporter...")
        error_reporter = create_error_reporter()
        
        # Create summarization service
        summarization_service = SummarizationService(
            document_store=document_store,
            vector_store=vector_store,
            publisher=publisher,
            subscriber=subscriber,
            summarizer=summarizer,
            top_k=config.top_k,
            citation_count=config.citation_count,
            retry_max_attempts=config.max_retries,
            retry_backoff_seconds=config.retry_delay,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(summarization_service,),
            daemon=False,
        )
        subscriber_thread.start()
        logger.info("Subscriber thread started")
        
        # Start FastAPI server
        logger.info(f"Starting HTTP server on port {config.http_port}...")
        
        # Configure Uvicorn with structured JSON logging
        log_config = create_uvicorn_log_config(service_name="summarization", log_level="INFO")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port, log_config=log_config)
        
    except Exception as e:
        logger.error(f"Failed to start summarization service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
