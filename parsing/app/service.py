# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main parsing service implementation."""

import logging
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

from .parser import MessageParser
from .thread_builder import ThreadBuilder

logger = logging.getLogger(__name__)


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

    def start(self):
        """Start the parsing service and subscribe to events."""
        logger.info("Starting Parsing Service")
        
        # Subscribe to ArchiveIngested events
        self.subscriber.subscribe(
            event_type="ArchiveIngested",
            exchange="copilot.events",
            routing_key="archive.ingested",
            callback=self._handle_archive_ingested,
        )
        
        logger.info("Subscribed to archive.ingested events")
        logger.info("Parsing service is ready")

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
            
            # Publish JSONParsed event
            self._publish_json_parsed(
                archive_id,
                len(parsed_messages),
                [msg["message_id"] for msg in parsed_messages],
                len(threads),
                [thread["thread_id"] for thread in threads],
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
                    self.error_reporter.capture_exception()
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
                logger.debug(f"Skipping message {message_id} ({error_type}): {e}")
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
                logger.debug(f"Skipping thread {thread_id} ({error_type}): {e}")
                skipped_count += 1
            except Exception as e:
                # Other errors are transient failures - re-raise
                logger.error(f"Error storing thread: {e}")
                raise
        
        if skipped_count > 0:
            logger.info(f"Stored {stored_count} threads, skipped {skipped_count} (duplicates/validation)")

    def _publish_json_parsed(
        self,
        archive_id: str,
        message_count: int,
        parsed_message_ids: list,
        thread_count: int,
        thread_ids: list,
        duration: float,
    ):
        """Publish JSONParsed event.
        
        Args:
            archive_id: Archive identifier
            message_count: Number of messages parsed
            parsed_message_ids: List of message IDs
            thread_count: Number of threads created
            thread_ids: List of thread IDs
            duration: Parsing duration in seconds
        """
        event = JSONParsedEvent(
            data={
                "archive_id": archive_id,
                "message_count": message_count,
                "parsed_message_ids": parsed_message_ids,
                "thread_count": thread_count,
                "thread_ids": thread_ids,
                "parsing_duration_seconds": duration,
            }
        )
        
        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="json.parsed",
                event=event.to_dict(),
            )
        except Exception:
            logger.exception(f"Exception while publishing JSONParsed event for {archive_id}")
            if self.error_reporter:
                self.error_reporter.capture_exception()
            raise

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
        except Exception:
            logger.exception(f"Exception while publishing ParsingFailed event for {archive_id}")
            if self.error_reporter:
                self.error_reporter.capture_exception()
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
