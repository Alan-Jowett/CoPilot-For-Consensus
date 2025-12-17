# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main parsing service implementation."""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pymongo.errors import DuplicateKeyError

from copilot_storage.validating_document_store import DocumentValidationError

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    ArchiveIngestedEvent,
    JSONParsedEvent,
    ParsingFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter
from copilot_schema_validation import generate_message_key
from copilot_logging import create_logger

from .parser import MessageParser
from .thread_builder import ThreadBuilder

logger = create_logger(name="parsing")


class ParsingService:
    """Main parsing service for converting mbox archives to structured JSON."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        """Initialize parsing service.
        
        Args:
            document_store: Document store for persisting messages and threads
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        
        # Create parser and thread builder
        self.parser = MessageParser()
        self.thread_builder = ThreadBuilder()
        
        # Stats
        self.archives_processed = 0
        self.messages_parsed = 0
        self.threads_created = 0
        self.last_processing_time = 0.0

    def start(self, enable_startup_requeue: bool = True):
        """Start the parsing service and subscribe to events.
        
        Args:
            enable_startup_requeue: Whether to requeue incomplete documents on startup (default: True)
        """
        logger.info("Starting Parsing Service")
        
        # Requeue incomplete archives on startup
        if enable_startup_requeue:
            self._requeue_incomplete_archives()
        
        # Subscribe to ArchiveIngested events
        self.subscriber.subscribe(
            event_type="ArchiveIngested",
            exchange="copilot.events",
            routing_key="archive.ingested",
            callback=self._handle_archive_ingested,
        )
        
        logger.info("Subscribed to archive.ingested events")
        logger.info("Parsing service is ready")
    
    def _requeue_incomplete_archives(self):
        """Requeue incomplete archives on startup for forward progress."""
        try:
            from copilot_startup import StartupRequeue
            
            logger.info("Scanning for incomplete archives to requeue on startup...")
            
            requeue = StartupRequeue(
                document_store=self.document_store,
                publisher=self.publisher,
                metrics_collector=self.metrics_collector,
            )
            
            count = requeue.requeue_incomplete(
                collection="archives",
                query={"status": {"$in": ["pending", "processing"]}},
                event_type="ArchiveIngested",
                routing_key="archive.ingested",
                id_field="archive_id",
                build_event_data=lambda doc: {
                    "archive_id": doc.get("archive_id"),
                    "file_path": doc.get("file_path"),
                    "source": doc.get("source"),
                    "message_count": doc.get("message_count", 0),
                },
                limit=1000,
            )
            
            logger.info(f"Startup requeue: {count} incomplete archives requeued")
            
        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

    def _handle_archive_ingested(self, event: Dict[str, Any]):
        """Handle ArchiveIngested event.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.
        
        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            archive_ingested = ArchiveIngestedEvent(data=event.get("data", {}))
            
            logger.info(f"Received ArchiveIngested event: {archive_ingested.data.get('archive_id')}")
            
            # Process the archive
            self.process_archive(archive_ingested.data)
            
        except Exception as e:
            logger.error(f"Error handling ArchiveIngested event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_archive(self, archive_data: Dict[str, Any]):
        """Process an archive and parse messages.
        
        Errors are handled by publishing ParsingFailed events and collecting
        metrics. Exceptions are not re-raised to allow graceful error handling
        in the event processing pipeline.
        
        Args:
            archive_data: Archive metadata from ArchiveIngested event
            
        Raises:
            KeyError: If required fields are missing from archive_data
        """
        archive_id = archive_data.get("archive_id")
        file_path = archive_data.get("file_path")
        
        if not archive_id or not file_path:
            error_msg = "Missing required fields in archive data"
            logger.error(error_msg)
            raise KeyError(error_msg)
        
        start_time = time.time()
        
        try:
            logger.info(f"Parsing archive {archive_id} from {file_path}")
            
            # Parse mbox file
            parsed_messages, errors = self.parser.parse_mbox(file_path, archive_id)
            
            if not parsed_messages:
                # No messages parsed
                error_msg = f"No messages parsed from archive. Errors: {errors}"
                logger.warning(error_msg)
                
                # Update archive status to 'failed'
                self._update_archive_status(archive_id, "failed", 0)
                
                self._publish_parsing_failed(
                    archive_id,
                    file_path,
                    error_msg,
                    "NoMessagesError",
                    0,
                )
                return
            
            # Build threads
            threads = self.thread_builder.build_threads(parsed_messages)
            
            # Store messages in document store
            if parsed_messages:
                self._store_messages(parsed_messages)
                logger.info(f"Stored {len(parsed_messages)} messages")
            
            # Store threads
            if threads:
                self._store_threads(threads)
                logger.info(f"Created {len(threads)} threads")
            
            # Update archive status to 'processed'
            self._update_archive_status(archive_id, "processed", len(parsed_messages))
            
            # Calculate duration
            duration = time.time() - start_time
            self.last_processing_time = duration
            
            # Update stats
            self.archives_processed += 1
            self.messages_parsed += len(parsed_messages)
            self.threads_created += len(threads)
            
            # Collect metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "parsing_archives_processed_total",
                    tags={"status": "success"},
                )
                self.metrics_collector.increment(
                    "parsing_messages_parsed_total",
                    value=len(parsed_messages),
                )
                self.metrics_collector.increment(
                    "parsing_threads_created_total",
                    value=len(threads),
                )
                self.metrics_collector.observe(
                    "parsing_duration_seconds",
                    duration,
                )
            
            # Publish JSONParsed events (one per message for fine-grained retry)
            self._publish_json_parsed_per_message(
                archive_id,
                parsed_messages,
                threads,
                duration,
            )
            
            logger.info(
                f"Successfully parsed archive {archive_id}: "
                f"{len(parsed_messages)} messages, {len(threads)} threads, "
                f"{duration:.2f}s"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to parse archive {archive_id} after {duration:.2f}s: {e}", exc_info=True)
            
            # Update archive status to 'failed'
            self._update_archive_status(archive_id, "failed", 0)
            
            # Collect metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "parsing_archives_processed_total",
                    tags={"status": "failed"},
                )
                self.metrics_collector.increment(
                    "parsing_failures_total",
                    tags={"error_type": type(e).__name__},
                )
            
            # Report error
            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "archive_id": archive_id,
                        "file_path": file_path,
                        "operation": "process_archive",
                    }
                )
            
            # Publish ParsingFailed event
            try:
                self._publish_parsing_failed(
                    archive_id,
                    file_path,
                    str(e),
                    type(e).__name__,
                    0,
                )
            except Exception as publish_error:
                # Event publishing failed but parsing definitely failed too
                # Log both errors to ensure visibility
                logger.error(
                    f"Failed to publish ParsingFailed event for {archive_id}",
                    exc_info=True,
                    extra={"original_error": str(e), "publish_error": str(publish_error)}
                )
                if self.error_reporter:
                    self.error_reporter.report(publish_error, context={"archive_id": archive_id})
                # Re-raise the original exception to trigger message requeue
                raise e from publish_error
            
            # Re-raise to trigger message requeue for transient failures
            raise e

    def _store_messages(self, messages: list):
        """Store messages in document store.
        
        Args:
            messages: List of message dictionaries
            
        Note:
            - Computes message_key for each message before storing
            - Inserts documents one at a time
            - Skips duplicate and validation errors and logs them
            - Re-raises other errors (transient failures)
        """
        skipped_count = 0
        stored_count = 0
        
        for message in messages:
            try:
                # Compute message_key if not already present
                if "message_key" not in message:
                    message["message_key"] = generate_message_key(
                        archive_id=message.get("archive_id", ""),
                        message_id=message.get("message_id", ""),
                        date=message.get("date"),
                        sender_email=message.get("from", {}).get("email"),
                        subject=message.get("subject"),
                    )
                
                self.document_store.insert_document("messages", message)
                stored_count += 1
            except (DuplicateKeyError, DocumentValidationError) as e:
                # Permanent errors - skip but log it
                message_id = message.get("message_id", "unknown")
                error_type = type(e).__name__
                logger.info(f"Skipping message {message_id} ({error_type}): {e}")
                skipped_count += 1
            except Exception as e:
                # Other errors are transient failures - re-raise
                logger.error(f"Error storing message: {e}")
                raise
        
        if skipped_count > 0:
            logger.info(f"Stored {stored_count} messages, skipped {skipped_count} (duplicates/validation)")

    def _store_threads(self, threads: list):
        """Store threads in document store.
        
        Args:
            threads: List of thread dictionaries
            
        Note:
            - Inserts documents one at a time
            - Skips duplicate and validation errors and logs them
            - Re-raises other errors (transient failures)
        """
        skipped_count = 0
        stored_count = 0
        
        for thread in threads:
            try:
                self.document_store.insert_document("threads", thread)
                stored_count += 1
            except (DuplicateKeyError, DocumentValidationError) as e:
                # Permanent errors - skip but log it
                thread_id = thread.get("thread_id", "unknown")
                error_type = type(e).__name__
                logger.info(f"Skipping thread {thread_id} ({error_type}): {e}")
                skipped_count += 1
            except Exception as e:
                # Other errors are transient failures - re-raise
                logger.error(f"Error storing thread: {e}")
                raise
        
        if skipped_count > 0:
            logger.info(f"Stored {stored_count} threads, skipped {skipped_count} (duplicates/validation)")

    def _update_archive_status(self, archive_id: str, status: str, message_count: int):
        """Update archive status in document store.
        
        Args:
            archive_id: Archive identifier
            status: New status (e.g., 'processed', 'failed')
            message_count: Number of messages parsed from archive
            
        Note:
            - Best-effort update - logs warnings but doesn't raise on failure
            - This allows parsing to continue even if archive record doesn't exist
        """
        try:
            self.document_store.update_document(
                "archives",
                archive_id,
                {
                    "status": status,
                    "message_count": message_count,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info(f"Updated archive {archive_id} status to '{status}' with {message_count} messages")
            
            # Emit metric for status transition
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "parsing_archive_status_transitions_total",
                    tags={"status": status, "collection": "archives"}
                )
        except Exception as e:
            # Log but don't raise - archive status update is not critical
            # The parsing can succeed even if the archive record doesn't exist
            logger.warning(
                f"Failed to update archive {archive_id} status: {e}",
                exc_info=True,
            )
            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "update_archive_status",
                        "archive_id": archive_id,
                        "status": status,
                        "message_count": message_count,
                    }
                )

    def _publish_json_parsed_per_message(
        self,
        archive_id: str,
        parsed_messages: list,
        threads: list,
        duration: float,
    ):
        """Publish JSONParsed events (one per message for fine-grained retry).
        
        This implements per-message event publishing to enable fine-grained
        retry granularity. If chunking fails on a single message, only that
        message is retried, not the entire archive batch.
        
        Args:
            archive_id: Archive identifier
            parsed_messages: List of parsed message dictionaries
            threads: List of thread dictionaries
            duration: Total parsing duration in seconds
            
        Raises:
            Exception: If event publishing fails for any message
        """
        # Build thread_id lookup for quick access
        thread_lookup = {thread["thread_id"]: thread for thread in threads}
        
        # Track failed publications for error reporting
        failed_publishes = []
        
        for message in parsed_messages:
            # Validate required fields exist
            message_key = message.get("message_key")
            if not message_key:
                logger.error(f"Cannot publish event: message missing required 'message_key' field")
                failed_publishes.append((
                    "unknown",
                    ValueError("Message missing required 'message_key' field")
                ))
                continue
            
            thread_id = message.get("thread_id")
            
            # Get thread info if this message is part of a thread
            thread_ids = [thread_id] if thread_id and thread_id in thread_lookup else []
            
            event = JSONParsedEvent(
                data={
                    "archive_id": archive_id,
                    "message_count": 1,  # Single message per event
                    "message_keys": [message_key],  # Single-item array
                    "thread_count": len(thread_ids),
                    "thread_ids": thread_ids,
                    # Note: parsing_duration_seconds represents the total archive parsing time,
                    # not individual message processing time. This is shared across all message events.
                    "parsing_duration_seconds": duration,
                }
            )
            
            try:
                self.publisher.publish(
                    exchange="copilot.events",
                    routing_key="json.parsed",
                    event=event.to_dict(),
                )
                logger.debug(f"Published JSONParsed event for message {message_key}")
            except Exception as e:
                logger.error(
                    f"Failed to publish JSONParsed event for message {message_key}: {e}",
                    exc_info=True
                )
                failed_publishes.append((message_key, e))
                if self.error_reporter:
                    self.error_reporter.report(
                        e,
                        context={
                            "operation": "publish_json_parsed",
                            "archive_id": archive_id,
                            "message_key": message_key,
                        }
                    )
        
        # If any publishes failed, raise an exception to fail the archive processing
        if failed_publishes:
            error_msg = f"Failed to publish {len(failed_publishes)} JSONParsed events for archive {archive_id}"
            logger.error(error_msg)
            # Raise the first exception to trigger archive processing failure
            raise failed_publishes[0][1]
        
        logger.info(f"Published {len(parsed_messages)} JSONParsed events for archive {archive_id}")

    def _publish_parsing_failed(
        self,
        archive_id: str,
        file_path: str,
        error_message: str,
        error_type: str,
        messages_parsed_before_failure: int,
    ):
        """Publish ParsingFailed event.
        
        Args:
            archive_id: Archive identifier
            file_path: Path to mbox file
            error_message: Error description
            error_type: Error type
            messages_parsed_before_failure: Partial progress
        """
        event = ParsingFailedEvent(
            data={
                "archive_id": archive_id,
                "file_path": file_path,
                "error_message": error_message,
                "error_type": error_type,
                "messages_parsed_before_failure": messages_parsed_before_failure,
                "retry_count": 0,
                "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        
        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="parsing.failed",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Exception while publishing ParsingFailed event for {archive_id}")
            if self.error_reporter:
                self.error_reporter.report(e, context={"archive_id": archive_id})
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get parsing statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "archives_processed": self.archives_processed,
            "messages_parsed": self.messages_parsed,
            "threads_created": self.threads_created,
            "last_processing_time_seconds": self.last_processing_time,
        }
