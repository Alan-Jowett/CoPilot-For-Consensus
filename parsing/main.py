# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Parsing Service: Convert raw .mbox files into structured JSON."""

import logging
import os
import sys
from pathlib import Path
import threading

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
import uvicorn

from copilot_config import load_typed_config
from copilot_events import create_publisher, create_subscriber, ValidatingEventPublisher, ValidatingEventSubscriber
from copilot_storage import create_document_store, ValidatingDocumentStore
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter
from copilot_schema_validation import FileSchemaProvider

from app import __version__
from app.service import ParsingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Parsing Service", version=__version__)


def get_service() -> ParsingService:
    """Get the parsing service instance from app state.
    
    Returns:
        ParsingService instance
        
    Raises:
        RuntimeError: If service is not initialized in app state
    """
    if not hasattr(app.state, "parsing_service") or app.state.parsing_service is None:
        raise RuntimeError("Service not initialized")
    return app.state.parsing_service


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
        "service": "parsing",
        "version": __version__,
        "messages_parsed_total": stats.get("messages_parsed", 0),
        "threads_created_total": stats.get("threads_created", 0),
        "archives_processed_total": stats.get("archives_processed", 0),
        "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
    }


@app.get("/stats")
def stats():
    """Get parsing statistics."""
    try:
        service = get_service()
        return service.get_stats()
    except RuntimeError:
        return {"error": "Service not initialized"}


def start_subscriber_thread(service: ParsingService):
    """Start the event subscriber in a separate thread.
    
    Args:
        service: Parsing service instance
        
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
    """Main entry point for the parsing service."""
    logger.info(f"Starting Parsing Service (version {__version__})")
    
    try:
        # Load configuration using config adapter
        config = load_typed_config("parsing")
        logger.info("Configuration loaded successfully")
        
        # Set logging level from config
        logging.getLogger().setLevel(config.log_level)
        
        # Create event publisher with schema validation
        logger.info(f"Creating event publisher ({config.message_bus_type})")
        base_publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )
        
        if not base_publisher.connect():
            if str(config.message_bus_type).lower() != "noop":
                logger.error(
                    "Failed to connect publisher to message bus. Failing fast.")
                raise ConnectionError("Publisher failed to connect to message bus")
            else:
                logger.warning("Failed to connect publisher to message bus. Continuing with noop publisher.")
        
        # Wrap with schema validation
        # Create schema providers for event and document validation
        # Events use schemas from documents/schemas/events/
        # Documents use schemas from documents/schemas/documents/
        event_schema_provider = FileSchemaProvider()
        document_schema_provider = FileSchemaProvider(
            schema_dir=Path(__file__).parent / "documents" / "schemas" / "documents"
        )
        
        publisher = ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=event_schema_provider,
        )
        
        # Create event subscriber with schema validation
        logger.info(f"Creating event subscriber ({config.message_bus_type})")
        base_subscriber = create_subscriber(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
            queue_name="parsing-service",
        )
        
        if not base_subscriber.connect():
            logger.error("Failed to connect subscriber to message bus")
            raise ConnectionError("Subscriber failed to connect to message bus")
        
        # Wrap with schema validation
        subscriber = ValidatingEventSubscriber(
            subscriber=base_subscriber,
            schema_provider=event_schema_provider,
        )
        
        # Create document store with schema validation
        logger.info(f"Creating document store ({config.doc_store_type})")
        base_document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user,
            password=config.doc_store_password,
        )
        
        try:
            base_document_store.connect()
        except Exception as e:
            logger.error(f"Failed to connect to document store: {e}", exc_info=True)
            raise  # Re-raise the original exception
        
        # Wrap with schema validation
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=document_schema_provider,
        )
        
        # Create metrics collector - fail fast on errors
        logger.info(f"Creating metrics collector ({config.metrics_backend})...")
        metrics_collector = create_metrics_collector(backend=config.metrics_backend)
        
        # Create error reporter - fail fast on errors
        logger.info(f"Creating error reporter ({config.error_reporter_type})...")
        error_reporter = create_error_reporter(reporter_type=config.error_reporter_type)
        
        # Create parsing service
        service = ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        # Store service in FastAPI app state for dependency injection
        app.state.parsing_service = service
        
        # Start subscriber in a separate thread (non-daemon to fail fast)
        subscriber_thread = threading.Thread(
            target=start_subscriber_thread,
            args=(service,),
            daemon=False,
        )
        subscriber_thread.start()
        
        # Start FastAPI server (blocking)
        logger.info(f"Starting FastAPI server on port {config.http_port}")
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
        
    except KeyboardInterrupt:
        logger.info("Shutting down parsing service")
    except Exception as e:
        logger.error(f"Fatal error in parsing service: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        try:
            service = get_service()
            if service.subscriber:
                service.subscriber.disconnect()
            if service.publisher:
                service.publisher.disconnect()
            if service.document_store:
                service.document_store.disconnect()
        except RuntimeError:
            # Service not initialized, nothing to clean up
            pass


if __name__ == "__main__":
    main()
