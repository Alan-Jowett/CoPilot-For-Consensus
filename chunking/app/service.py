# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main chunking service implementation."""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from pymongo.errors import DuplicateKeyError

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

    def start(self, enable_startup_requeue: bool = True):
        """Start the chunking service and subscribe to events.
        
        Args:
            enable_startup_requeue: Whether to requeue incomplete documents on startup (default: True)
        """
        logger.info("Starting Chunking Service")
        
        # Requeue incomplete messages on startup
        if enable_startup_requeue:
            self._requeue_incomplete_messages()
        
        # Subscribe to JSONParsed events
        self.subscriber.subscribe(
            event_type="JSONParsed",
            exchange="copilot.events",
            routing_key="json.parsed",
            callback=self._handle_json_parsed,
        )
        
        logger.info("Subscribed to json.parsed events")
        logger.info("Chunking service is ready")
    
    def _requeue_incomplete_messages(self):
        """Requeue parsed messages without chunks on startup for forward progress."""
        try:
            from copilot_startup import StartupRequeue
            
            logger.info("Scanning for parsed messages without chunks to requeue on startup...")
            
            requeue = StartupRequeue(
                document_store=self.document_store,
                publisher=self.publisher,
                metrics_collector=self.metrics_collector,
            )
            
            # Find messages that don't have chunks yet
            # We need to find messages that exist but have no corresponding chunks
            # This is done by querying messages and checking for chunk existence
            
            # For simplicity, we'll requeue based on archive status
            # Archives that are "processed" but messages don't have chunks
            count = requeue.requeue_incomplete(
                collection="archives",
                query={
                    "status": "processed",
                    # Additional logic could check for missing chunks per message
                },
                event_type="JSONParsed",
                routing_key="json.parsed",
                id_field="archive_id",
                build_event_data=lambda doc: {
                    "archive_id": doc.get("archive_id"),
                    "message_keys": [],  # Will be populated by querying messages
                    "message_count": doc.get("message_count", 0),
                },
                limit=100,  # Lower limit for chunking requeue
            )
            
            logger.info(f"Startup requeue: {count} archives with unparsed messages requeued")
            
        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

    def _handle_json_parsed(self, event: Dict[str, Any]):
        """Handle JSONParsed event.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.
        
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
            raise  # Re-raise to trigger message requeue for transient failures

    def process_messages(self, event_data: Dict[str, Any]):
        """Process messages and create chunks.
        
        Args:
            event_data: Data from JSONParsed event
            
        Raises:
            ValueError: If event_data is missing required fields
            TypeError: If message_keys is not iterable
        """
        # Check for required field
        if "message_keys" not in event_data:
            error_msg = "message_keys field missing from event data"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        message_keys = event_data["message_keys"]
        
        # Validate message_keys is iterable (list/array)
        if not isinstance(message_keys, list):
            error_msg = f"message_keys must be a list, got {type(message_keys).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        if not message_keys:
            logger.info("Empty message list in JSONParsed event, nothing to process")
            return
        
        start_time = time.time()
        
        try:
            logger.info(f"Chunking {len(message_keys)} messages")
            
            # Retrieve messages from database
            messages = self.document_store.query_documents(
                collection="messages",
                filter_dict={"message_key": {"$in": message_keys}}
            )
            
            if not messages:
                error_msg = "No messages found in database"
                logger.warning(error_msg)
                self._publish_chunking_failed(
                    message_keys,
                    error_msg,
                    "MessageNotFoundError",
                    0,
                )
                return
            
            # Process each message
            all_chunks = []
            processed_message_keys = []
            
            for message in messages:
                try:
                    if not message.get("message_key"):
                        raise ValueError(
                            f"message_key is required on message documents for chunking (message_id: {message.get('message_id')}, archive_id: {message.get('archive_id')})"
                        )

                    chunks = self._chunk_message(message)
                    if chunks:
                        all_chunks.extend(chunks)
                        processed_message_keys.append(message["message_key"])
                except Exception as e:
                    logger.error(
                        f"Error chunking message {message.get('message_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other messages
            
            # Store chunks in database with idempotency (skip duplicates)
            if all_chunks:
                chunk_ids = []
                skipped_duplicates = 0
                new_chunks_created = 0
                
                for chunk in all_chunks:
                    try:
                        self.document_store.insert_document("chunks", chunk)
                        chunk_ids.append(chunk["chunk_id"])
                        new_chunks_created += 1
                    except DuplicateKeyError:
                        # Chunk already exists (idempotent retry)
                        logger.debug(f"Chunk {chunk.get('chunk_id', 'unknown')} already exists, skipping")
                        chunk_ids.append(chunk.get("chunk_id", "unknown"))  # Still include in output
                        skipped_duplicates += 1
                    except Exception as e:
                        # Other errors (transient) should fail the processing
                        logger.error(f"Error storing chunk {chunk.get('chunk_id')}: {e}")
                        raise
                
                if skipped_duplicates > 0:
                    logger.info(
                        f"Created {len(all_chunks) - skipped_duplicates} chunks, "
                        f"skipped {skipped_duplicates} duplicates"
                    )
                else:
                    logger.info(f"Created {len(all_chunks)} chunks")
                
                # Emit metric for new chunks created with embedding_generated=False
                if self.metrics_collector and new_chunks_created > 0:
                    self.metrics_collector.increment(
                        "chunking_chunk_status_transitions_total",
                        value=new_chunks_created,
                        tags={"embedding_generated": "false", "collection": "chunks"}
                    )
                
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
            self.messages_processed += len(processed_message_keys)
            self.chunks_created_total += len(all_chunks)
            
            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "chunking_messages_processed_total",
                    len(processed_message_keys),
                    {"status": "success"}
                )
                self.metrics_collector.increment(
                    "chunking_chunks_created_total",
                    len(all_chunks)
                )
                self.metrics_collector.observe(
                    "chunking_duration_seconds",
                    duration
                )
                if avg_chunk_size > 0:
                    self.metrics_collector.observe(
                        "chunking_chunk_size_tokens",
                        avg_chunk_size
                    )
            
            # Publish ChunksPrepared event
            self._publish_chunks_prepared(
                processed_message_keys,
                chunk_ids,
                len(all_chunks),
                avg_chunk_size,
            )
            
            logger.info(
                f"Chunking completed: {len(processed_message_keys)} messages, "
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
                message_keys,
                str(e),
                type(e).__name__,
                0,
            )
            
            # Report error
            if self.error_reporter:
                self.error_reporter.report(e, context={"message_keys": message_keys})

    def _chunk_message(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a single message.
        
        Args:
            message: Message document from database
            
        Returns:
            List of chunk documents
        """
        message_id = message.get("message_id")
        message_key = message.get("message_key", "")
        text = message.get("body_normalized", "")
        
        # Skip empty messages
        if not text or not text.strip():
            logger.warning(f"Empty message body: {message_id}")
            return []
        
        # Create thread object for chunking
        thread = Thread(
            thread_id=message_id,
            message_key=message_key,
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
                "chunk_key": chunk.chunk_id,
                "chunk_id": chunk.chunk_id,
                "message_key": chunk.message_key,
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
        message_keys: List[str],
        chunk_ids: List[str],
        chunk_count: int,
        avg_chunk_size: float,
    ):
        """Publish ChunksPrepared event.
        
        Args:
            message_keys: List of message keys that were chunked
            chunk_ids: List of chunk IDs created
            chunk_count: Total number of chunks
            avg_chunk_size: Average chunk size in tokens
        """
        try:
            event = ChunksPreparedEvent(
                data={
                    "message_keys": message_keys,
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
                event=event.to_dict(),
            )
            
            logger.info(f"Published ChunksPrepared event: {chunk_count} chunks")
            
        except Exception as e:
            logger.error(f"Failed to publish ChunksPrepared event: {e}", exc_info=True)
            raise

    def _publish_chunking_failed(
        self,
        message_keys: List[str],
        error_message: str,
        error_type: str,
        retry_count: int,
    ):
        """Publish ChunkingFailed event.
        
        Args:
            message_keys: List of message keys that failed
            error_message: Error description
            error_type: Error classification
            retry_count: Number of retries
        """
        try:
            event = ChunkingFailedEvent(
                data={
                    "message_keys": message_keys,
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
            raise

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
