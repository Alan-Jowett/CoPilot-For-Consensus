# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Startup requeue utility for incomplete documents."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional

from copilot_storage import DocumentStore
from copilot_events import EventPublisher
from copilot_metrics import MetricsCollector

logger = logging.getLogger(__name__)


class StartupRequeue:
    """Utility to requeue incomplete documents on service startup.
    
    This class scans the document store for incomplete items and publishes
    requeue events to the message bus. It ensures forward progress after
    service crashes or restarts.
    """
    
    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """Initialize startup requeue utility.
        
        Args:
            document_store: Document store to query for incomplete items
            publisher: Event publisher for requeue events
            metrics_collector: Optional metrics collector
        """
        self.document_store = document_store
        self.publisher = publisher
        self.metrics_collector = metrics_collector
    
    def requeue_incomplete(
        self,
        collection: str,
        query: Dict[str, Any],
        event_type: str,
        routing_key: str,
        id_field: str,
        build_event_data: Callable[[Dict[str, Any]], Dict[str, Any]],
        limit: int = 1000,
    ) -> int:
        """Requeue incomplete documents from a collection.
        
        Args:
            collection: Collection name to query
            query: MongoDB query to find incomplete documents
            event_type: Event type to publish (e.g., "ArchiveIngested")
            routing_key: RabbitMQ routing key (e.g., "archive.ingested")
            id_field: Document ID field name (e.g., "archive_id")
            build_event_data: Function to build event data from document
            limit: Maximum documents to requeue (default: 1000)
            
        Returns:
            Number of documents requeued
            
        Raises:
            Exception: If document query or event publishing fails
        """
        logger.info(
            f"Startup requeue: scanning {collection} for incomplete documents "
            f"(query: {query}, limit: {limit})"
        )
        
        try:
            # Query for incomplete documents
            incomplete_docs = self.document_store.query_documents(
                collection=collection,
                filter_dict=query,
                limit=limit,
            )
            
            if not incomplete_docs:
                logger.info(f"No incomplete documents found in {collection}")
                return 0
            
            count = len(incomplete_docs)
            logger.info(f"Found {count} incomplete documents in {collection}, requeuing...")
            
            # Requeue each document
            requeued = 0
            for doc in incomplete_docs:
                try:
                    doc_id = doc.get(id_field, "unknown")
                    
                    # Build event data
                    event_data = build_event_data(doc)
                    
                    # Publish requeue event
                    self.publisher.publish(
                        event_type=event_type,
                        data=event_data,
                        routing_key=routing_key,
                        exchange="copilot.events",
                    )
                    
                    requeued += 1
                    logger.debug(f"Requeued {id_field}={doc_id} from {collection}")
                    
                except Exception as e:
                    logger.error(
                        f"Failed to requeue document {doc.get(id_field, 'unknown')} "
                        f"from {collection}: {e}",
                        exc_info=True
                    )
                    # Continue with other documents
                    
            # Emit metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "startup_requeue_documents_total",
                    requeued,
                    tags={"collection": collection}
                )
            
            logger.info(
                f"Startup requeue completed for {collection}: "
                f"{requeued}/{count} documents requeued"
            )
            
            return requeued
            
        except Exception as e:
            logger.error(
                f"Startup requeue failed for {collection}: {e}",
                exc_info=True
            )
            # Emit error metric
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "startup_requeue_errors_total",
                    1,
                    tags={"collection": collection, "error_type": type(e).__name__}
                )
            raise
