# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main chunking service implementation."""

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, cast

try:
    from pymongo.errors import DuplicateKeyError
except Exception:
    DuplicateKeyError = None  # type: ignore

from copilot_chunking import Thread, ThreadChunker
from copilot_error_reporting import ErrorReporter
from copilot_event_retry import (
    DocumentNotFoundError,
    RetryConfig,
    handle_event_with_retry,
)
from copilot_logging import get_logger
from copilot_message_bus import (
    ChunkingFailedEvent,
    ChunksPreparedEvent,
    EventPublisher,
    EventSubscriber,
    JSONParsedEvent,
    SourceCleanupProgressEvent,
    SourceDeletionRequestedEvent,
)
from copilot_metrics import MetricsCollector
from copilot_storage import DocumentStore

logger = get_logger(__name__)


class ChunkingService:
    """Main chunking service for splitting messages into token-aware chunks."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        chunker: ThreadChunker,
        metrics_collector: MetricsCollector | None = None,
        error_reporter: ErrorReporter | None = None,
        retry_config: RetryConfig | None = None,
    ):
        """Initialize chunking service.

        Args:
            document_store: Document store for persisting chunks
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            chunker: Chunking strategy implementation
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
            retry_config: Retry configuration for race condition handling (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.chunker = chunker
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        self.retry_config = retry_config or RetryConfig()

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

        # Subscribe to SourceDeletionRequested events for cascade cleanup
        self.subscriber.subscribe(
            event_type="SourceDeletionRequested",
            exchange="copilot.events",
            routing_key="source.deletion.requested",
            callback=self._handle_source_deletion_requested,
        )

        logger.info("Subscribed to json.parsed and source.deletion.requested events")
        logger.info("Chunking service is ready")

    def _requeue_incomplete_messages(self):
        """Requeue parsed messages without chunks on startup for forward progress."""
        try:
            logger.info("Scanning for parsed messages without chunks to requeue on startup...")

            # Use aggregation pipeline to efficiently find messages without chunks
            try:
                aggregate_documents = getattr(self.document_store, "aggregate_documents", None)
                if not callable(aggregate_documents):
                    logger.warning("Document store doesn't support aggregation, skipping chunking requeue")
                    return

                pipeline = [
                    {
                        "$match": {
                            "_id": {"$exists": True},
                        }
                    },
                    {
                        "$lookup": {
                            "from": "chunks",
                            "localField": "_id",
                            "foreignField": "message_doc_id",
                            "as": "chunks",
                        }
                    },
                    {
                        # Keep only messages that have no corresponding chunks
                        "$match": {
                            "chunks": {"$eq": []},
                        }
                    },
                    {
                        # Bound the number of messages we attempt to requeue on startup
                        "$limit": 1000,
                    },
                ]

                unchunked_messages = cast(
                    list[dict[str, Any]],
                    aggregate_documents(
                        collection="messages",
                        pipeline=pipeline,
                    ),
                )

                if not unchunked_messages:
                    logger.info("All messages have chunks, nothing to requeue")
                    return

                logger.info(f"Found {len(unchunked_messages)} messages without chunks")

                # Group messages by archive_id for efficient requeue
                archive_groups = {}
                for msg in unchunked_messages:
                    msg_doc_id = msg.get("_id")
                    archive_id = msg.get("archive_id")
                    if not msg_doc_id or archive_id is None:
                        continue
                    if archive_id not in archive_groups:
                        archive_groups[archive_id] = []
                    archive_groups[archive_id].append(msg_doc_id)

                # Requeue by archive using StartupRequeue helper
                from copilot_startup import StartupRequeue

                requeue_helper = StartupRequeue(
                    document_store=self.document_store,
                    publisher=self.publisher,
                    metrics_collector=self.metrics_collector,
                )

                requeued = 0
                for archive_id, msg_doc_ids in archive_groups.items():
                    try:
                        requeue_helper.publish_event(
                            event_type="JSONParsed",
                            routing_key="json.parsed",
                            event_data={
                                "archive_id": archive_id,
                                "message_doc_ids": msg_doc_ids,
                                "message_count": len(msg_doc_ids),
                                # Required fields for JSONParsed schema compliance
                                # For startup requeue, we use default values since we're just
                                # triggering re-chunking of existing messages
                                "thread_count": 0,
                                "thread_ids": [],
                                "parsing_duration_seconds": 0.0,
                            },
                        )
                        requeued += len(msg_doc_ids)
                        logger.debug(f"Requeued {len(msg_doc_ids)} messages from archive {archive_id}")
                    except Exception as e:
                        logger.error(f"Failed to requeue messages from archive {archive_id}: {e}")

                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "startup_requeue_documents_total", requeued, tags={"collection": "messages"}
                    )

                logger.info(f"Startup requeue: {requeued} messages without chunks requeued")

            except Exception as e:
                logger.error(f"Error querying for unchunked messages: {e}", exc_info=True)
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "startup_requeue_errors_total",
                        1,
                        tags={"collection": "messages", "error_type": type(e).__name__},
                    )

        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

    def _handle_json_parsed(self, event: dict[str, Any]):
        """Handle JSONParsed event with retry logic for race conditions.

        This is an event handler for message queue consumption. Wraps the processing
        logic with retry handling to address race conditions where documents are not
        yet queryable. Exceptions are logged and re-raised to allow message requeue
        for transient failures (e.g., database unavailable).

        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            json_parsed = JSONParsedEvent(data=event.get("data", {}))

            logger.info(f"Received JSONParsed event: {json_parsed.data.get('archive_id')}")

            # Process with retry logic for race condition handling
            # Generate idempotency key from message doc IDs
            # Use all message doc IDs for uniqueness (limited to reasonable length for key storage)
            message_doc_ids = json_parsed.data.get("message_doc_ids", [])
            message_ids_str = "-".join(str(mid) for mid in message_doc_ids)
            # Hash if too long to keep key manageable
            if len(message_ids_str) > 100:
                message_ids_hash = hashlib.sha256(message_ids_str.encode()).hexdigest()[:16]
                idempotency_key = f"chunking-{message_ids_hash}"
            else:
                idempotency_key = f"chunking-{message_ids_str}"

            # Wrap processing with retry logic
            handle_event_with_retry(
                handler=lambda e: self.process_messages(e.get("data", {})),
                event=event,
                config=self.retry_config,
                idempotency_key=idempotency_key,
                metrics_collector=self.metrics_collector,
                error_reporter=self.error_reporter,
                service_name="chunking",
            )

        except Exception as e:
            logger.error(f"Error handling JSONParsed event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_messages(self, event_data: dict[str, Any]):
        """Process messages and create chunks.

        Args:
            event_data: Data from JSONParsed event

        Raises:
            ValueError: If event_data is missing required fields
            TypeError: If message_doc_ids is not iterable
        """
        # Check for required field
        if "message_doc_ids" not in event_data:
            error_msg = "message_doc_ids field missing from event data"
            logger.error(error_msg)
            raise ValueError(error_msg)

        message_doc_ids = event_data["message_doc_ids"]

        # Validate message_doc_ids is iterable (list/array)
        if not isinstance(message_doc_ids, list):
            error_msg = f"message_doc_ids must be a list, got {type(message_doc_ids).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)

        if not message_doc_ids:
            logger.info("Empty message list in JSONParsed event, nothing to process")
            return

        start_time = time.time()

        try:
            logger.info(f"Chunking {len(message_doc_ids)} messages")

            # Retrieve messages from database
            messages = self.document_store.query_documents(
                collection="messages", filter_dict={"_id": {"$in": message_doc_ids}}
            )

            if not messages:
                error_msg = f"No messages found in database for {len(message_doc_ids)} IDs"
                logger.warning(error_msg)
                # Raise retryable error to trigger retry logic for race conditions
                # This handles cases where events arrive before documents are queryable
                raise DocumentNotFoundError(error_msg)

            # Process each message
            all_chunks = []
            processed_message_doc_ids = []

            for message in messages:
                try:
                    if not message.get("_id"):
                        message_id = message.get("message_id")
                        archive_id = message.get("archive_id")
                        raise ValueError(
                            "_id is required on message documents for chunking "
                            f"(message_id: {message_id}, archive_id: {archive_id})"
                        )

                    chunks = self._chunk_message(message)
                    if chunks:
                        all_chunks.extend(chunks)
                        processed_message_doc_ids.append(message["_id"])
                except Exception as e:
                    logger.error(f"Error chunking message {message.get('message_id')}: {e}", exc_info=True)
                    # Continue processing other messages

            # Store chunks in database with idempotency (skip duplicates)
            if all_chunks:
                chunk_ids = []
                skipped_duplicates = 0
                new_chunks_created = 0

                def _is_duplicate_key_error(exc: Exception) -> bool:
                    if DuplicateKeyError is not None and isinstance(exc, DuplicateKeyError):
                        return True

                    # Best-effort fallback when pymongo isn't installed.
                    return type(exc).__name__ == "DuplicateKeyError"

                for chunk in all_chunks:
                    try:
                        self.document_store.insert_document("chunks", chunk)
                        chunk_ids.append(chunk["_id"])
                        new_chunks_created += 1
                    except Exception as e:
                        # Chunk already exists (idempotent retry).
                        # Do not depend on pymongo at import-time; detect duplicates by name/message.
                        if _is_duplicate_key_error(e):
                            logger.debug(f"Chunk {chunk.get('_id', 'unknown')} already exists, skipping")
                            chunk_ids.append(chunk.get("_id", "unknown"))  # Still include in output
                            skipped_duplicates += 1
                            continue

                        # Other errors (transient) should fail the processing
                        logger.error(f"Error storing chunk {chunk.get('_id')}: {e}")
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
                        tags={"embedding_generated": "false", "collection": "chunks"},
                    )

                # Calculate average chunk size
                avg_chunk_size = sum(c["token_count"] for c in all_chunks) / len(all_chunks) if all_chunks else 0
            else:
                chunk_ids = []
                avg_chunk_size = 0
                logger.warning("No chunks created")

            # Calculate duration
            duration = time.time() - start_time
            self.last_processing_time = duration

            # Update stats
            self.messages_processed += len(processed_message_doc_ids)
            self.chunks_created_total += len(all_chunks)

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "chunking_messages_processed_total", len(processed_message_doc_ids), {"status": "success"}
                )
                self.metrics_collector.increment("chunking_chunks_created_total", len(all_chunks))
                self.metrics_collector.observe("chunking_duration_seconds", duration)
                if avg_chunk_size > 0:
                    self.metrics_collector.observe("chunking_chunk_size_tokens", avg_chunk_size)
                # Push metrics to Pushgateway
                self.metrics_collector.safe_push()

            # Publish ChunksPrepared event
            self._publish_chunks_prepared(
                processed_message_doc_ids,
                chunk_ids,
                len(all_chunks),
                avg_chunk_size,
            )

            logger.info(
                f"Chunking completed: {len(processed_message_doc_ids)} messages, "
                f"{len(all_chunks)} chunks in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Chunking failed: {e}", exc_info=True)

            # Record failure metrics
            if self.metrics_collector:
                self.metrics_collector.increment("chunking_failures_total", 1, {"error_type": type(e).__name__})
                # Push metrics to Pushgateway
                self.metrics_collector.safe_push()

            # Publish failure event
            self._publish_chunking_failed(
                message_doc_ids,
                str(e),
                type(e).__name__,
                0,
            )

            # Report error
            if self.error_reporter:
                self.error_reporter.report(e, context={"message_doc_ids": message_doc_ids})

    def _chunk_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk a single message.

        Args:
            message: Message document from database

        Returns:
            List of chunk documents
        """
        message_id = message.get("message_id")
        message_doc_id = message.get("_id", "")
        thread_id = message.get("thread_id", "")
        text = message.get("body_normalized", "")

        # Skip empty messages
        if not text or not text.strip():
            logger.warning(f"Empty message body: {message_id}")
            return []

        # Create thread object for chunking
        # Build metadata with defensive handling for None values
        from_data = message.get("from") or {}
        metadata = {
            "sender": from_data.get("email", ""),
            "sender_name": from_data.get("name", ""),
            "subject": message.get("subject") or "",
            "draft_mentions": message.get("draft_mentions", []),
        }

        # Only include date if it's a valid non-empty string
        date_value = message.get("date")
        if date_value and isinstance(date_value, str) and date_value.strip():
            metadata["date"] = date_value

        thread = Thread(thread_id=thread_id, message_doc_id=message_doc_id, text=text, metadata=metadata)

        # Chunk the thread
        chunks = self.chunker.chunk(thread)

        # Convert to database documents
        chunk_docs = []
        for chunk in chunks:
            chunk_doc = {
                "_id": chunk.chunk_id,
                "message_doc_id": chunk.message_doc_id,
                "message_id": message_id,
                "thread_id": chunk.thread_id,
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
        overlap = getattr(self.chunker, "overlap", None)
        if isinstance(overlap, int | float):
            return overlap > 0
        return False

    def _publish_chunks_prepared(
        self,
        message_doc_ids: list[str],
        chunk_ids: list[str],
        chunk_count: int,
        avg_chunk_size: float,
    ):
        """Publish ChunksPrepared event.

        Args:
            message_doc_ids: List of message document IDs that were chunked
            chunk_ids: List of chunk IDs created
            chunk_count: Total number of chunks
            avg_chunk_size: Average chunk size in tokens
        """
        try:
            event = ChunksPreparedEvent(
                data={
                    "message_doc_ids": message_doc_ids,
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
        message_doc_ids: list[str],
        error_message: str,
        error_type: str,
        retry_count: int,
    ):
        """Publish ChunkingFailed event.

        Args:
            message_doc_ids: List of message document IDs that failed
            error_message: Error description
            error_type: Error classification
            retry_count: Number of retries
        """
        try:
            event = ChunkingFailedEvent(
                data={
                    "message_doc_ids": message_doc_ids,
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

    def _handle_source_deletion_requested(self, event: dict[str, Any]):
        """Handle SourceDeletionRequested event to clean up chunking-owned data.

        This handler deletes chunks associated with a source by source_name and/or archive_id.
        The handler is idempotent - deleting already-deleted data is a no-op.

        Args:
            event: SourceDeletionRequested event payload
        """
        start_time = time.time()
        data = event.get("data", {})
        source_name = data.get("source_name")
        correlation_id = data.get("correlation_id")
        archive_ids = data.get("archive_ids", [])

        if not source_name:
            logger.error("SourceDeletionRequested event missing source_name", event=event)
            return

        logger.info(
            "Starting cascade cleanup for source in chunking service",
            source_name=source_name,
            correlation_id=correlation_id,
            archive_count=len(archive_ids),
        )

        deletion_counts = {
            "chunks": 0,
        }

        try:
            # Delete chunks for the source
            try:
                # Try querying by source first
                chunks = self.document_store.query_documents(
                    "chunks",
                    {"source": source_name}
                ) or []

                # If no chunks found by source and we have archive_ids, try by archive_id
                if not chunks and archive_ids:
                    for archive_id in archive_ids:
                        archive_chunks = self.document_store.query_documents(
                            "chunks",
                            {"archive_id": archive_id}
                        ) or []
                        chunks.extend(archive_chunks)

                for chunk in chunks:
                    chunk_id = chunk.get("_id")
                    if chunk_id:
                        try:
                            self.document_store.delete_document("chunks", chunk_id)
                            deletion_counts["chunks"] += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to delete chunk during cascade cleanup",
                                chunk_id=chunk_id,
                                source_name=source_name,
                                error=str(e),
                            )
                logger.info(
                    "Deleted chunks for source",
                    source_name=source_name,
                    count=deletion_counts["chunks"],
                )
            except Exception as e:
                logger.error(
                    "Failed to query/delete chunks during cascade cleanup",
                    source_name=source_name,
                    error=str(e),
                    exc_info=True,
                )

            # Emit metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "chunking_cascade_cleanup_total",
                    tags={"source_name": source_name}
                )
                if deletion_counts["chunks"] > 0:
                    self.metrics_collector.gauge(
                        "chunking_cascade_cleanup_chunks",
                        float(deletion_counts["chunks"]),
                        tags={"source_name": source_name}
                    )

            processing_time = time.time() - start_time
            logger.info(
                "Cascade cleanup completed in chunking service",
                source_name=source_name,
                correlation_id=correlation_id,
                deletion_counts=deletion_counts,
                processing_time_seconds=processing_time,
            )

            # Publish SourceCleanupProgress event
            try:
                completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                progress_event = SourceCleanupProgressEvent(
                    data={
                        "source_name": source_name,
                        "correlation_id": correlation_id,
                        "service_name": "chunking",
                        "status": "completed",
                        "deletion_counts": deletion_counts,
                        "completed_at": completed_at,
                    }
                )
                self.publisher.publish(
                    event=progress_event.to_dict(),
                    routing_key="source.cleanup.progress",
                    exchange="copilot.events",
                )
                logger.info(
                    "Published SourceCleanupProgress event",
                    source_name=source_name,
                    correlation_id=correlation_id,
                    status="completed",
                )
            except Exception as e:
                logger.error(
                    "Failed to publish SourceCleanupProgress event",
                    source_name=source_name,
                    correlation_id=correlation_id,
                    error=str(e),
                    exc_info=True,
                )

        except Exception as e:
            logger.error(
                "Cascade cleanup failed in chunking service",
                source_name=source_name,
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True,
            )

            # Publish failure progress event
            try:
                completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                progress_event = SourceCleanupProgressEvent(
                    data={
                        "source_name": source_name,
                        "correlation_id": correlation_id,
                        "service_name": "chunking",
                        "status": "failed",
                        "deletion_counts": deletion_counts,
                        "error_summary": f"Chunking cleanup failed: {str(e)[:200]}",
                        "completed_at": completed_at,
                    }
                )
                self.publisher.publish(
                    event=progress_event.to_dict(),
                    routing_key="source.cleanup.progress",
                    exchange="copilot.events",
                )
            except Exception as pub_error:
                logger.error(
                    "Failed to publish failure SourceCleanupProgress event",
                    source_name=source_name,
                    correlation_id=correlation_id,
                    error=str(pub_error),
                    exc_info=True,
                )

            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "source_cascade_cleanup",
                        "service": "chunking",
                        "source_name": source_name,
                        "correlation_id": correlation_id,
                        "deletion_counts": deletion_counts,
                    }
                )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "messages_processed": self.messages_processed,
            "chunks_created_total": self.chunks_created_total,
            "last_processing_time_seconds": round(self.last_processing_time, 2),
        }
