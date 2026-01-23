# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main parsing service implementation."""

import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

from copilot_archive_store import ArchiveStore
from copilot_error_reporting import ErrorReporter
from copilot_event_retry import (
    DocumentNotFoundError,
    RetryConfig,
    handle_event_with_retry,
)
from copilot_logging import get_logger
from copilot_message_bus import (
    ArchiveIngestedEvent,
    EventPublisher,
    EventSubscriber,
    JSONParsedEvent,
    ParsingFailedEvent,
    SourceCleanupProgressEvent,
    SourceDeletionRequestedEvent,
)
from copilot_metrics import MetricsCollector
from copilot_schema_validation import generate_message_doc_id
from copilot_storage import DocumentStore
from copilot_storage.validating_document_store import DocumentValidationError

from .parser import MessageParser
from .thread_builder import ThreadBuilder

logger = get_logger(__name__)

# Valid source types for ArchiveIngested events (must match schema enum)
VALID_SOURCE_TYPES = ["rsync", "imap", "http", "local"]


def _is_duplicate_key_error(exc: BaseException) -> bool:
    return (
        type(exc).__name__ == "DuplicateKeyError" or "duplicate key" in str(exc).lower() or "e11000" in str(exc).lower()
    )


class ParsingService:
    """Main parsing service for converting mbox archives to structured JSON."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        metrics_collector: MetricsCollector | None = None,
        error_reporter: ErrorReporter | None = None,
        archive_store: ArchiveStore | None = None,
        retry_config: RetryConfig | None = None,
    ):
        """Initialize parsing service.

        Args:
            document_store: Document store for persisting messages and threads
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
            archive_store: Archive store for retrieving raw archives (required)
            retry_config: Retry configuration for race condition handling (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        if archive_store is None:
            raise ValueError("archive_store is required and must be provided by the caller")
        self.archive_store = archive_store
        self.retry_config = retry_config or RetryConfig()

        # Create parser and thread builder
        self.parser = MessageParser()
        self.thread_builder = ThreadBuilder()

        # Stats
        self.archives_processed = 0
        self.messages_parsed = 0
        self.threads_created = 0
        self.last_processing_time = 0.0
        
        # Track if we've logged the legacy source_type warning to reduce noise
        self._legacy_source_type_warning_logged = False

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

        # Subscribe to SourceDeletionRequested events for cascade cleanup
        self.subscriber.subscribe(
            event_type="SourceDeletionRequested",
            exchange="copilot.events",
            routing_key="source.deletion.requested",
            callback=self._handle_source_deletion_requested,
        )

        logger.info("Subscribed to archive.ingested and source.deletion.requested events")
        logger.info("Parsing service is ready")

    def _build_archive_ingested_event_data(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Build and validate event data for ArchiveIngested events.

        This helper performs strict validation of required metadata fields and
        raises ValueError if they are missing or invalid. It is primarily used
        when reconstructing ArchiveIngested events from stored archive
        documents, for example during startup requeue.

        For legacy archives missing source_type, defaults to 'local' with a warning.

        Args:
            doc: Archive document from database

        Returns:
            Event data dictionary with validated required fields

        Raises:
            ValueError: If required metadata fields are missing or invalid
        """
        archive_id = doc.get("archive_id") or doc.get("_id")
        source_name = doc.get("source")
        source_type = doc.get("source_type")

        # Require source_name - this is essential for thread correlation
        if not source_name:
            raise ValueError(
                f"Archive {archive_id} missing required field 'source' (ingestion bug: "
                "source_name must be set when creating archives)"
            )

        # Handle legacy archives missing source_type by defaulting to 'local'
        if not source_type:
            source_type = "local"
            # Log warning once per service instance, then use INFO to reduce noise
            if not self._legacy_source_type_warning_logged:
                logger.warning(
                    f"Archive {archive_id} missing 'source_type' field (legacy document). "
                    f"Defaulting to 'local'. Consider backfilling with correct source_type. "
                    f"(Further occurrences will be logged at INFO level)"
                )
                self._legacy_source_type_warning_logged = True
            else:
                logger.info(
                    f"Archive {archive_id} missing 'source_type' field (legacy document), "
                    f"defaulting to 'local'"
                )

        # Validate source_type is a known enum value
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Archive {archive_id} has invalid source_type '{source_type}' "
                f"(must be one of {VALID_SOURCE_TYPES})"
            )

        return {
            "archive_id": archive_id,
            "source_name": source_name,
            "source_type": source_type,
            "source_url": doc.get("source_url", ""),
            "file_size_bytes": doc.get("file_size_bytes", 0),
            "file_hash_sha256": doc.get("file_hash", ""),
            "ingestion_started_at": doc.get("created_at", doc.get("ingestion_date", "")),
            "ingestion_completed_at": doc.get("ingestion_date", ""),
        }

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
                build_event_data=self._build_archive_ingested_event_data,
                limit=1000,
            )

            logger.info(f"Startup requeue: {count} incomplete archives requeued")

        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

    def _handle_archive_ingested(self, event: dict[str, Any]):
        """Handle ArchiveIngested event with retry logic for race conditions.

        This is an event handler for message queue consumption. Wraps the processing
        logic with retry handling to address race conditions where documents are not
        yet queryable. Exceptions are logged and re-raised to allow message requeue
        for transient failures (e.g., database unavailable). Only exceptions due to
        bad event data should be caught and not re-raised.

        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            archive_ingested = ArchiveIngestedEvent(data=event.get("data", {}))

            logger.info(f"Received ArchiveIngested event: {archive_ingested.data.get('archive_id')}")

            # Process with retry logic for race condition handling
            # Generate idempotency key from archive ID
            archive_id = archive_ingested.data.get("archive_id", "unknown")
            idempotency_key = f"parsing-{archive_id}"

            # Wrap processing with retry logic
            handle_event_with_retry(
                handler=lambda e: self.process_archive(e.get("data", {})),
                event=event,
                config=self.retry_config,
                idempotency_key=idempotency_key,
                metrics_collector=self.metrics_collector,
                error_reporter=self.error_reporter,
                service_name="parsing",
            )

        except Exception as e:
            logger.error(f"Error handling ArchiveIngested event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_archive(self, archive_data: dict[str, Any]):
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

        if not archive_id:
            error_msg = "Missing required field 'archive_id' in archive data"
            logger.error(error_msg)
            raise KeyError(error_msg)

        start_time = time.monotonic()

        try:
            logger.info(f"Parsing archive {archive_id}")

            # Retrieve archive content from ArchiveStore
            try:
                archive_content = self.archive_store.get_archive(archive_id)
                if archive_content is None:
                    error_msg = f"Archive {archive_id} not found in ArchiveStore"
                    logger.warning(error_msg)

                    # Raise retryable error to trigger retry logic for race conditions
                    # This handles cases where events arrive before archives are stored
                    raise DocumentNotFoundError(error_msg)
            except DocumentNotFoundError:
                # Re-raise so the handle_event_with_retry wrapper can retry.
                raise
            except Exception as e:
                error_msg = f"Failed to retrieve archive from ArchiveStore: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Update archive status to 'failed'
                self._update_archive_status(archive_id, "failed", 0)

                self._publish_parsing_failed(
                    archive_id,
                    None,  # Storage-agnostic mode - no file path available
                    error_msg,
                    type(e).__name__,
                    0,
                )
                return

            # Write archive content to temporary file for parsing
            # The parser expects a file path, so we create a temporary file
            # Use try-finally to ensure cleanup
            temp_file_path = None
            try:
                # Create temp file with prefix for easier identification
                with tempfile.NamedTemporaryFile(
                    mode="wb", delete=False, suffix=".mbox", prefix="parsing_"
                ) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(archive_content)

                logger.debug(f"Wrote archive {archive_id} to temporary file {temp_file_path}")

                # Parse mbox file - raises exceptions on failure
                parsed_messages = self.parser.parse_mbox(temp_file_path, archive_id)

                if not parsed_messages:
                    # No messages parsed (empty archive)
                    error_msg = "No messages found in archive"
                    logger.warning(error_msg)

                    # Update archive status to 'completed' with 0 messages
                    # This is not an error - just an empty archive
                    self._update_archive_status(archive_id, "completed", 0)
                    return

                # Generate canonical _id for each message (needed for thread building)
                for message in parsed_messages:
                    if "_id" not in message:
                        message["_id"] = generate_message_doc_id(
                            archive_id=archive_id,
                            message_id=message.get("message_id", ""),
                            date=message.get("date"),
                            sender_email=(message.get("from") or {}).get("email"),
                            subject=message.get("subject"),
                        )

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

                # Update archive status to 'completed'
                self._update_archive_status(archive_id, "completed", len(parsed_messages))

                # Calculate duration
                duration = time.monotonic() - start_time
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
                    # Push metrics to Pushgateway
                    self.metrics_collector.safe_push()

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

            except Exception as parse_error:
                # Parsing or processing failed - update archive status and publish event
                error_msg = f"Failed to parse archive: {str(parse_error)}"
                logger.error(error_msg, exc_info=True)

                # Update archive status to 'failed'
                self._update_archive_status(archive_id, "failed", 0)

                self._publish_parsing_failed(
                    archive_id,
                    None,  # Storage-agnostic mode - temp file path is internal detail
                    error_msg,
                    type(parse_error).__name__,
                    0,
                )

                # Don't re-raise - let event processing continue gracefully
                # The error has been recorded in the archive status and event
                return
            finally:
                # Always clean up temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                        logger.debug(f"Cleaned up temporary file {temp_file_path}")
                    except Exception as cleanup_error:
                        # Make cleanup failures clearly visible in logs and error reporting
                        logger.error(
                            f"Failed to clean up temporary file {temp_file_path}: {cleanup_error}",
                            exc_info=True,
                        )
                        if self.error_reporter:
                            self.error_reporter.report(
                                cleanup_error,
                                context={
                                    "archive_id": archive_id,
                                    "operation": "cleanup_temp_file",
                                    "temp_file_path": temp_file_path,
                                },
                            )

        except DocumentNotFoundError:
            # Treat missing documents/archives as a retryable race condition handled by
            # the outer handle_event_with_retry wrapper.
            raise
        except Exception as e:
            duration = time.monotonic() - start_time
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
                # Push metrics to Pushgateway
                self.metrics_collector.safe_push()

            # Report error
            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "archive_id": archive_id,
                        "operation": "process_archive",
                    },
                )

            # Publish ParsingFailed event
            try:
                self._publish_parsing_failed(
                    archive_id,
                    "",  # No file path in storage-agnostic mode
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
                    extra={"original_error": str(e), "publish_error": str(publish_error)},
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
            - Computes canonical _id for each message before storing
            - Inserts documents one at a time
            - Skips duplicate and validation errors and logs them
            - Re-raises other errors (transient failures)
        """
        skipped_count = 0
        stored_count = 0

        for message in messages:
            try:
                # Compute canonical _id if not already present
                if "_id" not in message:
                    message["_id"] = generate_message_doc_id(
                        archive_id=message.get("archive_id", ""),
                        message_id=message.get("message_id", ""),
                        date=message.get("date"),
                        sender_email=(message.get("from") or {}).get("email"),
                        subject=message.get("subject"),
                    )

                self.document_store.insert_document("messages", message)
                stored_count += 1
            except DocumentValidationError as e:
                # Permanent errors - skip but log it
                message_id = message.get("message_id", "unknown")
                logger.info(f"Skipping message {message_id} (DocumentValidationError): {e}")
                skipped_count += 1

                # Collect metrics for skipped messages
                if self.metrics_collector:
                    # Check if it's an empty body validation error by examining the errors list
                    is_empty_body = any(
                        "body_normalized" in error and ("non-empty" in error or "minLength" in error)
                        for error in e.errors
                    )
                    if is_empty_body:
                        skip_reason = "empty_body"
                        body_raw = message.get("body_raw", "")
                        has_attachments = bool(message.get("attachments"))
                        logger.debug(
                            f"Empty body for {message_id}: "
                            f"raw_length={len(body_raw)}, "
                            f"has_attachments={has_attachments}"
                        )
                    else:
                        skip_reason = "validation_error"

                    self.metrics_collector.increment(
                        "parsing_messages_skipped_total",
                        tags={"reason": skip_reason},
                    )
            except Exception as e:
                if _is_duplicate_key_error(e):
                    message_id = message.get("message_id", "unknown")
                    logger.info(f"Skipping message {message_id} (DuplicateKeyError): {e}")
                    skipped_count += 1

                    if self.metrics_collector:
                        self.metrics_collector.increment(
                            "parsing_messages_skipped_total",
                            tags={"reason": "duplicate"},
                        )
                    continue

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
            except DocumentValidationError as e:
                # Permanent errors - skip but log it
                thread_id = thread.get("thread_id", "unknown")
                logger.info(f"Skipping thread {thread_id} (DocumentValidationError): {e}")
                skipped_count += 1

                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "parsing_threads_skipped_total",
                        tags={"reason": "validation_error"},
                    )
            except Exception as e:
                if _is_duplicate_key_error(e):
                    thread_id = thread.get("thread_id", "unknown")
                    logger.info(f"Skipping thread {thread_id} (DuplicateKeyError): {e}")
                    skipped_count += 1

                    if self.metrics_collector:
                        self.metrics_collector.increment(
                            "parsing_threads_skipped_total",
                            tags={"reason": "duplicate"},
                        )
                    continue

                # Other errors are transient failures - re-raise
                logger.error(f"Error storing thread: {e}")
                raise

        if skipped_count > 0:
            logger.info(f"Stored {stored_count} threads, skipped {skipped_count} (duplicates/validation)")

    def _update_archive_status(self, archive_id: str, status: str, message_count: int):
        """Update archive status in document store.

        Args:
            archive_id: Archive identifier
            status: New status (e.g., 'completed', 'failed')
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
                },
            )
            logger.info(f"Updated archive {archive_id} status to '{status}' with {message_count} messages")

            # Emit metric for status transition
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "parsing_archive_status_transitions_total", tags={"status": status, "collection": "archives"}
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
                    },
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
        failed_publishes: list[tuple[str, Exception]] = []

        for message in parsed_messages:
            # Validate required fields exist
            message_doc_id = message.get("_id")
            if not message_doc_id:
                logger.error("Cannot publish event: message missing required '_id' field")
                failed_publishes.append(("unknown", ValueError("Message missing required '_id' field")))
                continue

            thread_id = message.get("thread_id")

            # Get thread info if this message is part of a thread
            thread_ids = [thread_id] if thread_id and thread_id in thread_lookup else []

            event = JSONParsedEvent(
                data={
                    "archive_id": archive_id,
                    "message_count": 1,  # Single message per event
                    "message_doc_ids": [message_doc_id],  # Single-item array
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
                logger.debug(f"Published JSONParsed event for message {message_doc_id}")
            except Exception as e:
                logger.error(f"Failed to publish JSONParsed event for message {message_doc_id}: {e}", exc_info=True)
                failed_publishes.append((message_doc_id, e))
                if self.error_reporter:
                    self.error_reporter.report(
                        e,
                        context={
                            "operation": "publish_json_parsed",
                            "archive_id": archive_id,
                            "message_doc_id": message_doc_id,
                        },
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
        file_path: str | None,
        error_message: str,
        error_type: str,
        messages_parsed_before_failure: int,
    ):
        """Publish ParsingFailed event.

        Args:
            archive_id: Archive identifier
            file_path: Path to mbox file (None for storage-agnostic mode - field will be omitted)
            error_message: Error description
            error_type: Error type
            messages_parsed_before_failure: Partial progress
        """
        # Build event data - omit file_path entirely for storage-agnostic backends (when None)
        event_data = {
            "archive_id": archive_id,
            "error_message": error_message,
            "error_type": error_type,
            "messages_parsed_before_failure": messages_parsed_before_failure,
            "retry_count": 0,
            "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Only include file_path if provided (local filesystem storage)
        if file_path is not None:
            event_data["file_path"] = file_path

        event = ParsingFailedEvent(data=event_data)

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

    def _handle_source_deletion_requested(self, event: dict[str, Any]):
        """Handle SourceDeletionRequested event to clean up parsing-owned data.

        This handler deletes parsing-owned data for a source including:
        - Threads associated with the source
        - Messages associated with the source
        - Archive metadata (if managed by parsing service)

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
            "Starting cascade cleanup for source in parsing service",
            source_name=source_name,
            correlation_id=correlation_id,
            archive_count=len(archive_ids),
        )

        deletion_counts = {
            "threads": 0,
            "messages": 0,
        }

        try:
            # Delete threads for the source
            try:
                threads = self.document_store.query_documents(
                    "threads",
                    {"source": source_name}
                ) or []
                for thread in threads:
                    thread_id = thread.get("_id")
                    if thread_id:
                        try:
                            self.document_store.delete_document("threads", thread_id)
                            deletion_counts["threads"] += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to delete thread during cascade cleanup",
                                thread_id=thread_id,
                                source_name=source_name,
                                error=str(e),
                            )
                logger.info(
                    "Deleted threads for source",
                    source_name=source_name,
                    count=deletion_counts["threads"],
                )
            except Exception as e:
                logger.error(
                    "Failed to query/delete threads during cascade cleanup",
                    source_name=source_name,
                    error=str(e),
                    exc_info=True,
                )

            # Delete messages for the source
            try:
                messages = self.document_store.query_documents(
                    "messages",
                    {"source": source_name}
                ) or []
                for message in messages:
                    message_id = message.get("_id")
                    if message_id:
                        try:
                            self.document_store.delete_document("messages", message_id)
                            deletion_counts["messages"] += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to delete message during cascade cleanup",
                                message_id=message_id,
                                source_name=source_name,
                                error=str(e),
                            )
                logger.info(
                    "Deleted messages for source",
                    source_name=source_name,
                    count=deletion_counts["messages"],
                )
            except Exception as e:
                logger.error(
                    "Failed to query/delete messages during cascade cleanup",
                    source_name=source_name,
                    error=str(e),
                    exc_info=True,
                )

            # Emit metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "parsing_cascade_cleanup_total",
                    tags={"source_name": source_name}
                )
                for collection, count in deletion_counts.items():
                    if count > 0:
                        self.metrics_collector.gauge(
                            f"parsing_cascade_cleanup_{collection}",
                            float(count),
                            tags={"source_name": source_name}
                        )

            processing_time = time.time() - start_time
            logger.info(
                "Cascade cleanup completed in parsing service",
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
                        "service_name": "parsing",
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
                "Cascade cleanup failed in parsing service",
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
                        "service_name": "parsing",
                        "status": "failed",
                        "deletion_counts": deletion_counts,
                        "error_summary": f"Parsing cleanup failed: {str(e)[:200]}",
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
                        "service": "parsing",
                        "source_name": source_name,
                        "correlation_id": correlation_id,
                        "deletion_counts": deletion_counts,
                    }
                )

    def get_stats(self) -> dict[str, Any]:
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
