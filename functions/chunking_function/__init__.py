# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Azure Function: Chunking Service
Service Bus triggered function for chunking parsed messages.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import azure.functions as func

# Add parent adapters to path to import shared modules
# In production, these would be packaged together or installed as dependencies
parent_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_path))

from chunking.app.service import ChunkingService
from copilot_chunking import create_chunker
from copilot_config import load_typed_config
from copilot_events import create_publisher, get_azure_servicebus_kwargs
from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter
from copilot_schema_validation import FileSchemaProvider
from copilot_storage import ValidatingDocumentStore, create_document_store

# Initialize structured logger for Azure Functions
logger = create_logger(logger_type="stdout", level="INFO", name="chunking_function")

# Global service instance (initialized once per function instance)
_chunking_service: ChunkingService | None = None


def get_chunking_service() -> ChunkingService:
    """
    Get or create the chunking service instance.
    
    This function implements lazy initialization to avoid startup overhead.
    The service is created once per function instance and reused across invocations.
    
    Returns:
        ChunkingService: Initialized chunking service
    """
    global _chunking_service
    
    if _chunking_service is not None:
        return _chunking_service
    
    logger.info("Initializing chunking service for Azure Function")
    
    try:
        # Load configuration from environment variables
        # Note: Azure Functions uses environment variables from Function App Configuration
        config = load_typed_config("chunking")
        logger.info("Configuration loaded successfully")
        
        # Create message bus publisher for output events
        message_bus_kwargs = {}
        if config.message_bus_type == "azureservicebus":
            message_bus_kwargs = get_azure_servicebus_kwargs()
            logger.info("Using Azure Service Bus configuration")
        
        publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
            **message_bus_kwargs,
        )
        publisher.connect()
        logger.info("Publisher connected to message bus")
        
        # Create document store
        base_document_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user if config.doc_store_user else None,
            password=config.doc_store_password if config.doc_store_password else None,
        )
        base_document_store.connect()
        logger.info("Document store connected successfully")
        
        # Wrap with schema validation
        document_schema_provider = FileSchemaProvider(
            schema_dir=parent_path / "chunking" / "docs" / "schemas" / "documents"
        )
        document_store = ValidatingDocumentStore(
            store=base_document_store,
            schema_provider=document_schema_provider,
            strict=True,
        )
        
        # Create chunker
        logger.info(f"Creating chunker with strategy: {config.chunking_strategy}")
        chunker = create_chunker(
            strategy=config.chunking_strategy,
            chunk_size=config.chunk_size,
            overlap=config.chunk_overlap,
            min_chunk_size=config.min_chunk_size,
            max_chunk_size=config.max_chunk_size,
        )
        
        # Create metrics collector
        metrics_collector = create_metrics_collector()
        
        # Create error reporter
        error_reporter = create_error_reporter()
        
        # Create chunking service (without subscriber since Azure Functions handles that)
        _chunking_service = ChunkingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=None,  # Not needed - Azure Functions runtime handles message consumption
            chunker=chunker,
            metrics_collector=metrics_collector,
            error_reporter=error_reporter,
        )
        
        logger.info("Chunking service initialized successfully")
        return _chunking_service
        
    except Exception as e:
        logger.error(f"Failed to initialize chunking service: {e}", exc_info=True)
        raise


def main(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function entry point - triggered by Service Bus queue message.
    
    This function is automatically invoked by the Azure Functions runtime when
    a message arrives in the 'json.parsed' queue. The runtime handles:
    - Message dequeuing
    - Automatic retries on failure
    - Dead-letter queue routing for persistent failures
    - Message completion/abandonment
    
    Args:
        msg: Service Bus message from 'json.parsed' queue
        
    Raises:
        Exception: Any exception will cause the message to be retried
    """
    start_time = time.time()
    
    # Log invocation details
    logger.info(
        f"Chunking function triggered",
        extra={
            "message_id": msg.message_id,
            "sequence_number": msg.sequence_number,
            "enqueued_time": msg.enqueued_time_utc.isoformat() if msg.enqueued_time_utc else None,
            "delivery_count": msg.delivery_count,
        }
    )
    
    try:
        # Get or initialize service
        service = get_chunking_service()
        
        # Parse message body
        message_body = msg.get_body().decode('utf-8')
        event_data = json.loads(message_body)
        
        logger.info(
            f"Processing JSONParsed event",
            extra={
                "archive_id": event_data.get("data", {}).get("archive_id"),
                "message_count": len(event_data.get("data", {}).get("message_doc_ids", [])),
            }
        )
        
        # Process the messages using the existing service logic
        # Note: We're calling process_messages directly, bypassing the event handler wrapper
        service.process_messages(event_data.get("data", {}))
        
        duration = time.time() - start_time
        logger.info(
            f"Chunking completed successfully",
            extra={
                "duration_seconds": round(duration, 2),
                "message_id": msg.message_id,
            }
        )
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Chunking failed: {e}",
            extra={
                "duration_seconds": round(duration, 2),
                "message_id": msg.message_id,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        
        # Re-raise to trigger Azure Functions retry mechanism
        # The message will be retried up to MaxDeliveryCount times before going to dead-letter queue
        raise
