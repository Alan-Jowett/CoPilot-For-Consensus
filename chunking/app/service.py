# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main chunking service implementation."""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    JSONParsedEvent,
    ChunksPreparedEvent,
    ChunkingFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter
from copilot_chunking import Thread, ThreadChunker

logger = logging.getLogger(__name__)


class ChunkingService:
    """Main chunking service for splitting messages into token-aware chunks."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        chunker: ThreadChunker,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        """Initialize chunking service.
        
        Args:
            document_store: Document store for persisting chunks
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            chunker: Chunking strategy implementation
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.chunker = chunker
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        
        # Stats
        self.messages_processed = 0
        self.chunks_created_total = 0
        self.last_processing_time = 0.0

    def start(self):
        """Start the chunking service and subscribe to events."""
        logger.info("Starting Chunking Service")
        
        # Subscribe to JSONParsed events
        self.subscriber.subscribe(
            event_type="JSONParsed",
            exchange="copilot.events",
            routing_key="json.parsed",
            callback=self._handle_json_parsed,
        )
        
        logger.info("Subscribed to json.parsed events")
        logger.info("Chunking service is ready")

    def _handle_json_parsed(self, event: Dict[str, Any]):
        """Handle JSONParsed event.
        
        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            json_parsed = JSONParsedEvent(data=event.get("data", {}))
            
            logger.info(f"Received JSONParsed event: {json_parsed.data.get('archive_id')}")
            
            # Process the messages
            self.process_messages(json_parsed.data)
            
        except Exception as e:
            logger.error(f"Error handling JSONParsed event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            # Re-raise so RabbitMQ can nack and requeue the message
            raise

    def process_messages(self, event_data: Dict[str, Any]):
        """Process messages and create chunks.
        
        Args:
            event_data: Data from JSONParsed event
        """
        message_ids = event_data.get("parsed_message_ids", [])
        
        if not message_ids:
            logger.warning("No message IDs in JSONParsed event")
            return
        
        start_time = time.time()
        
        try:
            logger.info(f"Chunking {len(message_ids)} messages")
            
            # Retrieve messages from database
            messages = self.document_store.query_documents(
                collection="messages",
                filter_dict={"message_id": {"$in": message_ids}}
            )
            
            if not messages:
                error_msg = "No messages found in database"
                logger.warning(error_msg)
                self._publish_chunking_failed(
                    message_ids,
                    error_msg,
                    "MessageNotFoundError",
                    0,
                )
                return
            
            # Process each message
            all_chunks = []
            processed_message_ids = []
            
            for message in messages:
                try:
                    chunks = self._chunk_message(message)
                    if chunks:
                        all_chunks.extend(chunks)
                        processed_message_ids.append(message["message_id"])
                except Exception as e:
                    logger.error(
                        f"Error chunking message {message.get('message_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other messages
            
            # Store chunks in database
            if all_chunks:
                chunk_ids = []
                for chunk in all_chunks:
                    self.document_store.insert_document("chunks", chunk)
                    chunk_ids.append(chunk["chunk_id"])
                
                logger.info(f"Created {len(all_chunks)} chunks")
                
                # Calculate average chunk size
                avg_chunk_size = (
                    sum(c["token_count"] for c in all_chunks) / len(all_chunks)
                    if all_chunks else 0
                )
            else:
                chunk_ids = []
                avg_chunk_size = 0
                logger.warning("No chunks created")
            
            # Calculate duration
            duration = time.time() - start_time
            self.last_processing_time = duration
            
            # Update stats
            self.messages_processed += len(processed_message_ids)
            self.chunks_created_total += len(all_chunks)
            
            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "chunking_messages_processed_total",
                    len(processed_message_ids),
                    {"status": "success"}
                )
                self.metrics_collector.increment(
                    "chunking_chunks_created_total",
                    len(all_chunks)
                )
                self.metrics_collector.histogram(
                    "chunking_duration_seconds",
                    duration
                )
                if avg_chunk_size > 0:
                    self.metrics_collector.histogram(
                        "chunking_chunk_size_tokens",
                        avg_chunk_size
                    )
            
            # Publish ChunksPrepared event
            self._publish_chunks_prepared(
                processed_message_ids,
                chunk_ids,
                len(all_chunks),
                avg_chunk_size,
            )
            
            logger.info(
                f"Chunking completed: {len(processed_message_ids)} messages, "
                f"{len(all_chunks)} chunks in {duration:.2f}s"
            )
            
        except Exception as e:
            logger.error(f"Chunking failed: {e}", exc_info=True)
            
            # Record failure metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "chunking_failures_total",
                    1,
                    {"error_type": type(e).__name__}
                )
            
            # Publish failure event
            self._publish_chunking_failed(
                message_ids,
                str(e),
                type(e).__name__,
                0,
            )
            
            # Report error
            if self.error_reporter:
                self.error_reporter.report(e, context={"message_ids": message_ids})

    def _chunk_message(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a single message.
        
        Args:
            message: Message document from database
            
        Returns:
            List of chunk documents
        """
        message_id = message.get("message_id")
        text = message.get("body_normalized", "")
        
        # Skip empty messages
        if not text or not text.strip():
            logger.warning(f"Empty message body: {message_id}")
            return []
        
        # Create thread object for chunking
        thread = Thread(
            thread_id=message_id,
            text=text,
            metadata={
                "sender": message.get("from", {}).get("email", ""),
                "sender_name": message.get("from", {}).get("name", ""),
                "date": message.get("date", ""),
                "subject": message.get("subject", ""),
                "draft_mentions": message.get("draft_mentions", []),
            }
        )
        
        # Chunk the thread
        chunks = self.chunker.chunk(thread)
        
        # Convert to database documents
        chunk_docs = []
        for chunk in chunks:
            chunk_doc = {
                "chunk_id": chunk.chunk_id,
                "message_id": message_id,
                "thread_id": message.get("thread_id"),
                "archive_id": message.get("archive_id"),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "start_offset": chunk.start_offset,
                "end_offset": chunk.end_offset,
                "overlap_with_previous": chunk.chunk_index > 0 and self._has_overlap(),
                "overlap_with_next": chunk.chunk_index < len(chunks) - 1 and self._has_overlap(),
                "metadata": chunk.metadata,
                "chunking_strategy": type(self.chunker).__name__,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "embedding_generated": False,
            }
            chunk_docs.append(chunk_doc)
        
        return chunk_docs

    def _has_overlap(self) -> bool:
        """Check if the chunker uses overlap.
        
        Returns:
            True if chunker has overlap configured, False otherwise
        """
        return hasattr(self.chunker, 'overlap') and self.chunker.overlap > 0

    def _publish_chunks_prepared(
        self,
        message_ids: List[str],
        chunk_ids: List[str],
        chunk_count: int,
        avg_chunk_size: float,
    ):
        """Publish ChunksPrepared event.
        
        Args:
            message_ids: List of message IDs that were chunked
            chunk_ids: List of chunk IDs created
            chunk_count: Total number of chunks
            avg_chunk_size: Average chunk size in tokens
        """
        try:
            event = ChunksPreparedEvent(
                data={
                    "message_ids": message_ids,
                    "chunk_count": chunk_count,
                    "chunk_ids": chunk_ids,
                    "chunks_ready": True,
                    "chunking_strategy": type(self.chunker).__name__,
                    "avg_chunk_size_tokens": int(round(avg_chunk_size)),
                }
            )
            
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="chunks.prepared",
                message=event.to_dict(),
            )
            
            logger.info(f"Published ChunksPrepared event: {chunk_count} chunks")
            
        except Exception as e:
            logger.error(f"Failed to publish ChunksPrepared event: {e}", exc_info=True)

    def _publish_chunking_failed(
        self,
        message_ids: List[str],
        error_message: str,
        error_type: str,
        retry_count: int,
    ):
        """Publish ChunkingFailed event.
        
        Args:
            message_ids: List of message IDs that failed
            error_message: Error description
            error_type: Error classification
            retry_count: Number of retries
        """
        try:
            event = ChunkingFailedEvent(
                data={
                    "message_ids": message_ids,
                    "error_message": error_message,
                    "error_type": error_type,
                    "retry_count": retry_count,
                    "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
            
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="chunking.failed",
                event=event.to_dict(),
            )
            
            logger.info(f"Published ChunkingFailed event: {error_type}")
            
        except Exception as e:
            logger.error(f"Failed to publish ChunkingFailed event: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "messages_processed": self.messages_processed,
            "chunks_created_total": self.chunks_created_total,
            "last_processing_time_seconds": round(self.last_processing_time, 2),
        }
