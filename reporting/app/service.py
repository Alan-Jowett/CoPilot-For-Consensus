# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main reporting service implementation."""

import hashlib
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import requests
from copilot_error_reporting import ErrorReporter
from copilot_event_retry import (
    DocumentNotFoundError as RetryDocumentNotFoundError,
    RetryConfig,
    handle_event_with_retry,
)
from copilot_logging import get_logger
from copilot_message_bus import (
    EventPublisher,
    EventSubscriber,
    ReportDeliveryFailedEvent,
    ReportPublishedEvent,
    SourceCleanupProgressEvent,
    SourceDeletionRequestedEvent,
    SummaryCompleteEvent,
)
from copilot_metrics import MetricsCollector
from copilot_storage import DocumentNotFoundError as StorageDocumentNotFoundError
from copilot_storage import DocumentStore

# Optional dependencies for search/filtering features
if TYPE_CHECKING:
    from copilot_embedding import EmbeddingProvider
    from copilot_vectorstore import VectorStore

logger = get_logger(__name__)

# Buffer size for fetching additional documents when metadata filtering is applied.
# This ensures we have enough documents to filter and still return the requested limit.
# The value is chosen to balance between over-fetching and ensuring adequate results
# after filtering by thread/archive metadata.
METADATA_FILTER_BUFFER_SIZE = 100


class ReportingService:
    """Main reporting service for storing and serving summaries."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        metrics_collector: MetricsCollector | None = None,
        error_reporter: ErrorReporter | None = None,
        webhook_url: str | None = None,
        notify_enabled: bool = False,
        webhook_summary_max_length: int = 500,
        vector_store: Optional["VectorStore"] = None,
        embedding_provider: Optional["EmbeddingProvider"] = None,
        retry_config: RetryConfig | None = None,
    ):
        """Initialize reporting service.

        Args:
            document_store: Document store for persisting summaries
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
            webhook_url: Webhook URL for notifications (optional)
            notify_enabled: Enable webhook notifications
            webhook_summary_max_length: Max length for summary in webhook payload
            vector_store: Vector store for topic-based search (optional)
            embedding_provider: Embedding provider for topic search (optional)
            retry_config: Retry configuration for race condition handling (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        self.webhook_url = webhook_url
        self.notify_enabled = notify_enabled
        self.webhook_summary_max_length = webhook_summary_max_length
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.retry_config = retry_config or RetryConfig()

        # Stats
        self.reports_stored = 0
        self.notifications_sent = 0
        self.notifications_failed = 0
        self.last_processing_time = 0.0

    def start(self):
        """Start the reporting service and subscribe to events."""
        logger.info("Starting Reporting Service")

        # Subscribe to SummaryComplete events
        self.subscriber.subscribe(
            event_type="SummaryComplete",
            exchange="copilot.events",
            routing_key="summary.complete",
            callback=self._handle_summary_complete,
        )

        # Subscribe to SourceDeletionRequested events for cascade cleanup
        self.subscriber.subscribe(
            event_type="SourceDeletionRequested",
            exchange="copilot.events",
            routing_key="source.deletion.requested",
            callback=self._handle_source_deletion_requested,
        )

        logger.info("Subscribed to summary.complete and source.deletion.requested events")
        logger.info("Reporting service is ready")

    def _handle_summary_complete(self, event: dict[str, Any]):
        """Handle SummaryComplete event with retry logic for race conditions.

        This is an event handler for message queue consumption. Wraps the processing
        logic with retry handling to address race conditions where documents are not
        yet queryable. Exceptions are logged and re-raised to allow message requeue
        for transient failures (e.g., database unavailable). Only exceptions due to
        bad event data should be caught and not re-raised.

        Args:
            event: Event dictionary
        """
        start_time = time.time()

        try:
            # Parse event
            summary_complete = SummaryCompleteEvent(data=event.get("data", {}))

            logger.info(f"Received SummaryComplete event: {summary_complete.data.get('thread_id')}")

            # Validate required fields before retry wrapper
            # Missing fields indicate malformed events that should NOT be retried
            thread_id = summary_complete.data.get("thread_id")
            summary_id = summary_complete.data.get("summary_id")

            if not thread_id or not summary_id:
                error_msg = "Missing required fields thread_id or summary_id in SummaryComplete event"
                logger.error(error_msg)
                # Record metrics for invalid event
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "reporting_events_total", tags={"event_type": "summary_complete", "outcome": "validation_error"}
                    )
                    self.metrics_collector.increment("reporting_failures_total", tags={"error_type": "ValidationError"})
                # Do NOT re-raise to avoid infinite requeue of malformed events
                return

            idempotency_key = f"reporting-{thread_id}-{summary_id}"

            # Wrap processing with retry logic
            handle_event_with_retry(
                handler=lambda e: self.process_summary(e.get("data", {}), e),
                event=event,
                config=self.retry_config,
                idempotency_key=idempotency_key,
                service_name="reporting",
            )

            # Record processing time
            self.last_processing_time = time.time() - start_time

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "reporting_events_total", tags={"event_type": "summary_complete", "outcome": "success"}
                )
                self.metrics_collector.observe("reporting_latency_seconds", self.last_processing_time)

        except Exception as e:
            logger.error(f"Error handling SummaryComplete event: {e}", exc_info=True)

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "reporting_events_total", tags={"event_type": "summary_complete", "outcome": "error"}
                )
                self.metrics_collector.increment("reporting_failures_total", tags={"error_type": type(e).__name__})

            # Report error
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_summary(self, event_data: dict[str, Any], full_event: dict[str, Any]) -> str:
        """Process and store a summary.

        Args:
            event_data: Data from SummaryComplete event
            full_event: Full event envelope

        Returns:
            Report ID
        """
        # Extract data from event
        original_summary_id = event_data.get("summary_id")  # SHA-256 hash from summarization service
        thread_id_value = event_data.get("thread_id")
        if not isinstance(thread_id_value, str) or not thread_id_value:
            raise ValueError("SummaryComplete event missing required 'thread_id'")
        thread_id = thread_id_value

        # Generate a 16-character hex ID for summaries._id (matching schema requirements)
        # Use a truncated hash of the original summary_id for determinism
        if original_summary_id:
            report_id = hashlib.sha256(original_summary_id.encode()).hexdigest()[:16]
        else:
            # Fallback to UUID for backward compatibility; log for observability
            import uuid

            report_id = str(uuid.uuid4()).replace("-", "")[:16]
            logger.warning(
                "SummaryComplete event missing required 'summary_id'; generated fallback ID "
                "for backward compatibility. "
                "This may indicate an older publisher version or misconfiguration.",
                report_id=report_id,
                event_metadata={
                    "event_type": full_event.get("type"),
                    "event_id": full_event.get("event_id") or full_event.get("id"),
                },
            )

        summary_markdown = event_data.get("summary_markdown", "")
        citations = event_data.get("citations", [])
        llm_backend = event_data.get("llm_backend", "")
        llm_model = event_data.get("llm_model", "")
        tokens_prompt = event_data.get("tokens_prompt", 0)
        tokens_completion = event_data.get("tokens_completion", 0)
        latency_ms = event_data.get("latency_ms", 0)

        # Create summary document
        now = datetime.now(timezone.utc).isoformat()

        # Look up thread to denormalize date fields into the summary.
        # This enables efficient DB-level sorting by thread date in get_reports().
        first_message_date = None
        last_message_date = None
        thread_docs: list[dict[str, Any]] = []
        try:
            thread_docs = list(
                self.document_store.query_documents(
                    "threads",
                    filter_dict={"_id": thread_id},
                    limit=1,
                )
            )
            if not thread_docs:
                # Thread document not yet available; raise a retryable error so we don't
                # persist a summary with null dates, which would sort incorrectly.
                raise RetryDocumentNotFoundError(
                    f"Thread {thread_id} not found for denormalization; will retry"
                )
            first_message_date = thread_docs[0].get("first_message_date")
            last_message_date = thread_docs[0].get("last_message_date")
        except RetryDocumentNotFoundError:
            raise
        except Exception as e:
            # Transient/unexpected error — re-raise so the event can be retried.
            # Persisting a summary with null dates would cause it to sort incorrectly.
            logger.error(
                f"Error fetching thread {thread_id} dates for summary denormalization: {e}",
                exc_info=True,
            )
            raise

        summary_doc = {
            "_id": report_id,
            "summary_id": report_id,
            "thread_id": thread_id,
            "summary_type": "thread",
            "title": f"Summary for {thread_id}",
            "content_markdown": summary_markdown,
            "first_message_date": first_message_date,
            "last_message_date": last_message_date,
            "citations": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "message_id": c.get("message_id", ""),
                    "quote": c.get("text", ""),  # Source text snippet from citation
                    "relevance_score": c.get("relevance_score", 1.0),  # Use provided score or default
                }
                for c in citations
            ],
            "generated_by": llm_backend,
            "generated_at": now,
            "metadata": {
                "llm_model": llm_model,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "latency_ms": latency_ms,
                "event_timestamp": full_event.get("timestamp", now),
                # Store original summary_id (SHA-256 hash) from summarization service
                "original_summary_id": original_summary_id,
                # Store original event citations with offset for reference
                "original_citations": citations,
            },
        }

        # Store summary
        # Idempotency: if the summary already exists, skip insert to avoid retries
        try:
            existing = list(
                self.document_store.query_documents(
                    "summaries",
                    filter_dict={"_id": report_id},
                    limit=1,
                )
            )
            if existing:
                logger.info(f"Summary {report_id} already stored; skipping insert")
                # Backfill denormalized date fields if a prior attempt persisted
                # the summary but the thread lacked date fields at that time.
                existing_doc = existing[0]
                if first_message_date is not None and (
                    existing_doc.get("first_message_date") is None
                    or existing_doc.get("last_message_date") is None
                ):
                    logger.info(
                        f"Backfilling date fields on summary {report_id}"
                    )
                    self.document_store.update_document(
                        "summaries",
                        report_id,
                        {
                            "first_message_date": first_message_date,
                            "last_message_date": last_message_date,
                        },
                    )
            else:
                logger.info(f"Storing summary {report_id} for thread {thread_id}")
                self.document_store.insert_document("summaries", summary_doc)
                self.reports_stored += 1
        except Exception as e:
            # If insert races, treat duplicate key as success to allow ack and prevent requeue
            if type(e).__name__ == "DuplicateKeyError" or "duplicate key error" in str(e):
                logger.info(f"Summary {report_id} already exists (duplicate); treating as success")
            else:
                raise

        # Update thread document with summary_id to mark as complete
        logger.info(f"Updating thread {thread_id} with summary_id {report_id}")
        # Threads use thread_id as document _id; update by ID.
        # thread_docs is guaranteed non-empty (we raise RetryDocumentNotFoundError above if not).
        try:
            self.document_store.update_document(
                "threads",
                thread_id,
                {"summary_id": report_id},
            )
        except StorageDocumentNotFoundError as e:
            # Convert storage-layer not-found into a retryable race-condition error.
            raise RetryDocumentNotFoundError(
                f"Thread {thread_id} not found in database"
            ) from e
        except RetryDocumentNotFoundError:
            raise
        except Exception as e:
            # Do not swallow this: if we stored the summary but failed to link it to the
            # thread, we must retry/requeue so the system converges.
            logger.warning(
                f"Failed to update thread {thread_id} with summary_id {report_id}: {e}",
                exc_info=True,
            )
            raise

        # Attempt webhook notification if enabled
        notified = False
        delivery_channels = []

        if self.notify_enabled and self.webhook_url:
            try:
                self._send_webhook_notification(report_id, thread_id, summary_markdown)
                notified = True
                delivery_channels.append("webhook")
                self.notifications_sent += 1

                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "reporting_delivery_total", tags={"channel": "webhook", "status": "success"}
                    )

            except Exception as e:
                # Webhook notifications are best-effort - log and publish failure event but continue
                logger.warning(f"Failed to send webhook notification: {e}", exc_info=True)
                self.notifications_failed += 1

                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "reporting_delivery_total", tags={"channel": "webhook", "status": "failed"}
                    )

                # Publish ReportDeliveryFailed event
                try:
                    self._publish_delivery_failed(report_id, thread_id, "webhook", str(e), type(e).__name__)
                except Exception as publish_error:
                    logger.error(
                        f"Failed to publish ReportDeliveryFailed event for {report_id}",
                        exc_info=True,
                        extra={"original_error": str(e), "publish_error": str(publish_error)},
                    )
                    if self.error_reporter:
                        self.error_reporter.report(
                            publish_error, context={"report_id": report_id, "original_error": str(e)}
                        )
                    # Re-raise original error to trigger requeue
                    raise e from publish_error

        # Publish ReportPublished event
        self._publish_report_published(report_id, thread_id, notified, delivery_channels)

        return report_id

    def _send_webhook_notification(self, report_id: str, thread_id: str, summary: str):
        """Send webhook notification.

        Args:
            report_id: Report identifier
            thread_id: Thread identifier
            summary: Summary markdown content

        Raises:
            Exception: If webhook delivery fails
        """
        payload = {
            "report_id": report_id,
            "thread_id": thread_id,
            "summary": summary[: self.webhook_summary_max_length],  # Truncate for webhook
            "url": f"/api/reports/{report_id}",
        }

        webhook_url = self.webhook_url
        if not isinstance(webhook_url, str) or not webhook_url:
            raise ValueError("Webhook notifications enabled but webhook_url is not configured")

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()

        logger.info(f"Webhook notification sent for report {report_id}")

    def _publish_report_published(
        self,
        report_id: str,
        thread_id: str,
        notified: bool,
        delivery_channels: list[str],
    ):
        """Publish ReportPublished event.

        Args:
            report_id: Report identifier
            thread_id: Thread identifier
            notified: Whether notification was sent
            delivery_channels: List of delivery channels used
        """
        event = ReportPublishedEvent(
            data={
                "thread_id": thread_id,
                "report_id": report_id,
                "format": "markdown",
                "notified": notified,
                "delivery_channels": delivery_channels,
                "summary_url": f"/api/reports/{report_id}",
            }
        )

        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="report.published",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Exception while publishing ReportPublished event for {report_id}")
            if self.error_reporter:
                self.error_reporter.report(e, context={"report_id": report_id, "event_type": "ReportPublished"})
            raise

        logger.info(f"Published ReportPublished event for {report_id}")

    def _publish_delivery_failed(
        self,
        report_id: str,
        thread_id: str,
        channel: str,
        error_message: str,
        error_type: str,
    ):
        """Publish ReportDeliveryFailed event.

        Args:
            report_id: Report identifier
            thread_id: Thread identifier
            channel: Delivery channel that failed
            error_message: Error message
            error_type: Error type
        """
        event = ReportDeliveryFailedEvent(
            data={
                "report_id": report_id,
                "thread_id": thread_id,
                "delivery_channel": channel,
                "error_message": error_message,
                "error_type": error_type,
                "retry_count": 0,
            }
        )

        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="report.delivery.failed",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Exception while publishing ReportDeliveryFailed event for {report_id}")
            if self.error_reporter:
                self.error_reporter.report(e, context={"report_id": report_id, "event_type": "ReportDeliveryFailed"})
            raise

        logger.warning(f"Published ReportDeliveryFailed event for {report_id}")

    def get_reports(
        self,
        thread_id: str | None = None,
        limit: int = 10,
        skip: int = 0,
        message_start_date: str | None = None,
        message_end_date: str | None = None,
        source: str | None = None,
        min_participants: int | None = None,
        max_participants: int | None = None,
        min_messages: int | None = None,
        max_messages: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Get list of reports with optional filters.

        Args:
            thread_id: Filter by thread ID (optional)
            limit: Maximum number of results
            skip: Number of results to skip
            message_start_date: Filter by thread message dates (inclusive overlap) - start of date range (ISO 8601)
            message_end_date: Filter by thread message dates (inclusive overlap) - end of date range (ISO 8601)
            source: Filter by archive source (optional)
            min_participants: Filter by minimum participant count (optional)
            max_participants: Filter by maximum participant count (optional)
            min_messages: Filter by minimum message count (optional)
            max_messages: Filter by maximum message count (optional)
            sort_by: Field to sort by (e.g., 'thread_start_date', 'generated_at')
            sort_order: Sort order ('asc' or 'desc', default 'desc')

        Returns:
            List of report documents with enriched metadata
        """
        # Build filter for summaries
        filter_dict = {}
        if thread_id:
            filter_dict["thread_id"] = thread_id

        # Determine DB-level sorting for summaries.
        # Summaries are denormalized with first_message_date/last_message_date
        # from their thread, so we can sort at the DB level directly.
        db_sort_by = None
        db_sort_order = sort_order or "desc"
        if db_sort_order not in ("asc", "desc"):
            db_sort_order = "desc"
        if sort_by == "generated_at":
            db_sort_by = "generated_at"
        elif sort_by == "thread_start_date":
            db_sort_by = "first_message_date"

        # Fetch summaries (fetch more for skip and filtering)
        summaries = self.document_store.query_documents(
            "summaries",
            filter_dict=filter_dict,
            limit=limit + skip + METADATA_FILTER_BUFFER_SIZE,
            sort_by=db_sort_by,
            sort_order=db_sort_order,
        )

        # Always enrich results with thread/archive data for UI display (thread start date, etc.)
        # This ensures thread_metadata.first_message_date is always available for sorting
        has_filtering = (
            source
            or min_participants is not None
            or max_participants is not None
            or min_messages is not None
            or max_messages is not None
            or message_start_date is not None
            or message_end_date is not None
        )

        # Always enrich summaries with thread metadata for consistent UI experience
        enriched_summaries = []

        # Batch fetch all threads to avoid N+1 query problem
        # Collect unique thread IDs from summaries
        thread_ids = []
        for summary in summaries:
            thread_id_val = summary.get("thread_id")
            if thread_id_val:
                thread_ids.append(thread_id_val)

        # Batch query all threads
        threads_map = {}
        if thread_ids:
            threads = self.document_store.query_documents(
                "threads",
                filter_dict={"thread_id": {"$in": thread_ids}},
                limit=len(thread_ids),
            )
            threads_map = {t.get("thread_id"): t for t in threads if t.get("thread_id")}

        # Collect unique archive IDs for batch fetching
        archive_ids = set()
        for thread in threads_map.values():
            archive_id = thread.get("archive_id")
            if archive_id:
                archive_ids.add(archive_id)

        # Batch query all archives
        archives_map = {}
        if archive_ids:
            archives = self.document_store.query_documents(
                "archives",
                filter_dict={"_id": {"$in": list(archive_ids)}},
                limit=len(archive_ids),
            )
            archives_map = {a.get("_id"): a for a in archives if a.get("_id")}

        # Now process summaries with pre-fetched data
        for summary in summaries:
            thread_id_val = summary.get("thread_id")
            if not thread_id_val:
                continue

            # Get thread metadata from pre-fetched map
            thread = threads_map.get(thread_id_val)
            if not thread:
                continue

            # Calculate counts once for reuse
            participants = thread.get("participants", [])
            participant_count = len(participants)
            message_count = thread.get("message_count", 0)
            archive_id = thread.get("archive_id")

            # Apply message date filters using inclusive overlap (only if filtering is active)
            # A thread is included if its date range [first_message_date, last_message_date]
            # overlaps with the filter range [message_start_date, message_end_date]
            # Overlap condition: first_message_date <= message_end_date AND last_message_date >= message_start_date
            if has_filtering and (message_start_date is not None or message_end_date is not None):
                first_msg_date = thread.get("first_message_date")
                last_msg_date = thread.get("last_message_date")

                # Skip threads without date information
                if not first_msg_date or not last_msg_date:
                    continue

                # Check overlap condition
                if message_end_date is not None and first_msg_date > message_end_date:
                    continue  # Thread starts after filter range ends

                if message_start_date is not None and last_msg_date < message_start_date:
                    continue  # Thread ends before filter range starts

            # Apply thread-based filters (only if filtering is active)
            if has_filtering and min_participants is not None:
                if participant_count < min_participants:
                    continue

            if has_filtering and max_participants is not None:
                if participant_count > max_participants:
                    continue

            if has_filtering and min_messages is not None:
                if message_count < min_messages:
                    continue

            if has_filtering and max_messages is not None:
                if message_count > max_messages:
                    continue

            # Apply source filter using pre-fetched archive (only if filtering is active)
            archive = archives_map.get(archive_id) if archive_id else None
            if has_filtering and source:
                if not archive or archive.get("source") != source:
                    continue

            # Enrich summary with thread and archive metadata
            summary["thread_metadata"] = {
                "subject": thread.get("subject", ""),
                "participants": participants,
                "participant_count": participant_count,
                "message_count": message_count,
                "first_message_date": thread.get("first_message_date"),
                "last_message_date": thread.get("last_message_date"),
            }

            if archive:
                summary["archive_metadata"] = {
                    "source": archive.get("source", ""),
                    "source_url": archive.get("source_url", ""),
                    "ingestion_date": archive.get("ingestion_date"),
                }

            enriched_summaries.append(summary)

        summaries = enriched_summaries

        # Apply sorting if requested
        if sort_by:
            reverse = sort_order == "desc"

            # Helper to parse dates with proper handling of missing values
            def sort_key_with_missing_last(summary: dict[str, Any], field_path: list[str]) -> str:
                """Get sort key with missing values sorted to the end.

                For ascending order, missing values get a high sentinel (zzz...)
                For descending order, missing values get a low sentinel (empty string)
                This ensures missing values always appear at the end regardless of sort direction.
                """
                value = summary
                for key in field_path:
                    value = value.get(key, {}) if isinstance(value, dict) else {}

                # If value is missing or empty, return sentinel
                if not value:
                    return "~~~" if not reverse else ""  # High value for asc, low for desc

                return str(value)

            if sort_by == "thread_start_date":
                # Sort by first_message_date from thread_metadata
                summaries.sort(
                    key=lambda s: sort_key_with_missing_last(s, ["thread_metadata", "first_message_date"]),
                    reverse=reverse,
                )
            elif sort_by == "generated_at":
                # Sort by report generation date
                summaries.sort(key=lambda s: sort_key_with_missing_last(s, ["generated_at"]), reverse=reverse)

        # Apply skip and limit
        return summaries[skip : skip + limit]

    def _get_thread_by_id(self, thread_id: str) -> dict[str, Any] | None:
        """Get thread metadata by ID.

        Args:
            thread_id: Thread identifier

        Returns:
            Thread document or None
        """
        try:
            results = self.document_store.query_documents(
                "threads",
                filter_dict={"thread_id": thread_id},
                limit=1,
            )
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"Failed to fetch thread {thread_id}: {e}")
            return None

    def _get_archive_by_id(self, archive_id: str) -> dict[str, Any] | None:
        """Get archive metadata by ID.

        Args:
            archive_id: Archive identifier

        Returns:
            Archive document or None
        """
        try:
            results = self.document_store.query_documents(
                "archives",
                filter_dict={"_id": archive_id},
                limit=1,
            )
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"Failed to fetch archive {archive_id}: {e}")
            return None

    def search_reports_by_topic(
        self,
        topic: str,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search reports by topic using embedding-based similarity.

        Args:
            topic: Topic or query text to search for
            limit: Maximum number of results
            min_score: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of report documents with relevance scores

        Raises:
            ValueError: If vector store or embedding provider not configured
        """
        if not self.vector_store or not self.embedding_provider:
            raise ValueError("Topic search requires vector store and embedding provider")

        # Generate embedding for the topic query
        try:
            topic_embedding = self.embedding_provider.embed(topic)
        except Exception as e:
            logger.error(f"Failed to generate embedding for topic: {e}", exc_info=True)
            raise ValueError(f"Failed to generate topic embedding: {e}")

        # Search vector store for similar chunks
        try:
            search_results = self.vector_store.query(topic_embedding, top_k=limit * 3)
        except Exception as e:
            logger.error(f"Failed to query vector store: {e}", exc_info=True)
            raise ValueError(f"Vector store query failed: {e}")

        # Extract chunk IDs and group by thread
        thread_scores = {}
        for result in search_results:
            if result.score < min_score:
                continue

            chunk_id = result.id
            metadata = result.metadata
            thread_id = metadata.get("thread_id")

            if thread_id:
                if thread_id not in thread_scores:
                    thread_scores[thread_id] = {
                        "max_score": result.score,
                        "avg_score": result.score,
                        "chunk_count": 1,
                        "chunks": [chunk_id],
                    }
                else:
                    thread_scores[thread_id]["max_score"] = max(thread_scores[thread_id]["max_score"], result.score)
                    thread_scores[thread_id]["avg_score"] = (
                        thread_scores[thread_id]["avg_score"] * thread_scores[thread_id]["chunk_count"] + result.score
                    ) / (thread_scores[thread_id]["chunk_count"] + 1)
                    thread_scores[thread_id]["chunk_count"] += 1
                    thread_scores[thread_id]["chunks"].append(chunk_id)

        # Sort threads by relevance (max score)
        sorted_threads = sorted(
            thread_scores.items(),
            key=lambda x: x[1]["max_score"],
            reverse=True,
        )[:limit]

        # Fetch summaries for the top threads
        enriched_reports = []
        for thread_id, scores in sorted_threads:
            summary = self.get_thread_summary(thread_id)
            if summary:
                summary["relevance_score"] = scores["max_score"]
                summary["avg_relevance_score"] = scores["avg_score"]
                summary["matching_chunks"] = scores["chunk_count"]

                # Enrich with thread metadata
                thread = self._get_thread_by_id(thread_id)
                if thread:
                    summary["thread_metadata"] = {
                        "subject": thread.get("subject", ""),
                        "participants": thread.get("participants", []),
                        "participant_count": len(thread.get("participants", [])),
                        "message_count": thread.get("message_count", 0),
                        "first_message_date": thread.get("first_message_date"),
                        "last_message_date": thread.get("last_message_date"),
                    }

                    # Enrich with archive metadata
                    archive_id = thread.get("archive_id")
                    if archive_id:
                        archive = self._get_archive_by_id(archive_id)
                        if archive:
                            summary["archive_metadata"] = {
                                "source": archive.get("source", ""),
                                "source_url": archive.get("source_url", ""),
                                "ingestion_date": archive.get("ingestion_date"),
                            }

                enriched_reports.append(summary)

        return enriched_reports

    def get_available_sources(self) -> list[str]:
        """Get list of available archive sources.

        Returns:
            List of unique source names
        """
        try:
            # Query all archives to extract unique source names
            # Using a high limit (10000) to ensure we capture all archives in most deployments.
            # TODO: Replace with a distinct query or aggregation pipeline for better scalability
            archives = self.document_store.query_documents(
                "archives",
                filter_dict={},
                limit=10000,
            )

            # Extract unique sources
            sources = set()
            for archive in archives:
                source = archive.get("source")
                if source:
                    sources.add(source)

            return sorted(list(sources))
        except Exception as e:
            logger.error(f"Failed to fetch available sources: {e}", exc_info=True)
            return []

    def get_report_by_id(self, report_id: str) -> dict[str, Any] | None:
        """Get a specific report by ID.

        Args:
            report_id: Report identifier

        Returns:
            Report document or None
        """
        # Backward-compatible lookup by summary_id (tests expect this).
        results = self.document_store.query_documents(
            "summaries",
            filter_dict={"summary_id": report_id},
            limit=1,
        )

        return results[0] if results else None

    def get_thread_summary(self, thread_id: str) -> dict[str, Any] | None:
        """Get the latest summary for a thread.

        Note: Without ordering support in DocumentStore, this returns the first
        matching document. In practice, MongoDB may return documents in insertion
        order, but this is not guaranteed. For true "latest" behavior, consider
        fetching all and sorting by generated_at timestamp.

        Args:
            thread_id: Thread identifier

        Returns:
            Latest report document for thread or None
        """
        results = self.document_store.query_documents(
            "summaries",
            filter_dict={"thread_id": thread_id},
            limit=1,
        )

        return results[0] if results else None

    def get_threads(
        self,
        limit: int = 10,
        skip: int = 0,
        archive_id: str | None = None,
        message_start_date: str | None = None,
        message_end_date: str | None = None,
        source: str | None = None,
        min_participants: int | None = None,
        max_participants: int | None = None,
        min_messages: int | None = None,
        max_messages: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Get list of threads with optional filters.

        Args:
            limit: Maximum number of results
            skip: Number of results to skip
            archive_id: Filter by archive ID (optional)
            message_start_date: Filter by thread message dates (inclusive overlap) - start of date range (ISO 8601)
            message_end_date: Filter by thread message dates (inclusive overlap) - end of date range (ISO 8601)
            source: Filter by archive source (optional)
            min_participants: Filter by minimum participant count (optional)
            max_participants: Filter by maximum participant count (optional)
            min_messages: Filter by minimum message count (optional)
            max_messages: Filter by maximum message count (optional)
            sort_by: Field to sort by ('first_message_date' or 'last_message_date')
            sort_order: Sort order ('asc' or 'desc', default 'desc')

        Returns:
            List of thread documents with enriched archive_source field
        """
        filter_dict = {}
        if archive_id:
            filter_dict["archive_id"] = archive_id

        # Determine DB-level sorting
        db_sort_by = None
        db_sort_order = sort_order or "desc"
        if db_sort_order not in ("asc", "desc"):
            db_sort_order = "desc"
        if sort_by == "first_message_date":
            db_sort_by = "first_message_date"
        elif sort_by == "last_message_date":
            db_sort_by = "last_message_date"

        # Check if we need to apply metadata filtering
        has_filtering = (
            source
            or min_participants is not None
            or max_participants is not None
            or min_messages is not None
            or max_messages is not None
            or message_start_date is not None
            or message_end_date is not None
        )

        # Fetch threads (fetch more for skip and filtering)
        threads = self.document_store.query_documents(
            "threads",
            filter_dict=filter_dict,
            limit=limit + skip + (METADATA_FILTER_BUFFER_SIZE if has_filtering else 0),
            sort_by=db_sort_by,
            sort_order=db_sort_order,
        )

        # Collect unique archive IDs for batch fetching
        archive_ids = set()
        for thread in threads:
            archive_id_val = thread.get("archive_id")
            if archive_id_val:
                archive_ids.add(archive_id_val)

        # Batch query all archives
        archives_map = {}
        if archive_ids:
            archives = self.document_store.query_documents(
                "archives",
                filter_dict={"_id": {"$in": list(archive_ids)}},
                limit=len(archive_ids),
            )
            archives_map = {a.get("_id"): a for a in archives if a.get("_id")}

        # Enrich threads and apply filters
        enriched_threads = []
        for thread in threads:
            # Calculate counts for filtering
            participants = thread.get("participants", [])
            participant_count = len(participants)
            message_count = thread.get("message_count", 0)
            archive_id_val = thread.get("archive_id")
            archive = archives_map.get(archive_id_val) if archive_id_val else None

            # Apply message date filters using inclusive overlap (only if filtering is active)
            # A thread is included if its date range [first_message_date, last_message_date]
            # overlaps with the filter range [message_start_date, message_end_date]
            # Overlap condition: first_message_date <= message_end_date AND last_message_date >= message_start_date
            if has_filtering and (message_start_date is not None or message_end_date is not None):
                first_msg_date = thread.get("first_message_date")
                last_msg_date = thread.get("last_message_date")

                # Skip threads without date information
                if not first_msg_date or not last_msg_date:
                    continue

                # Check overlap condition
                if message_end_date is not None and first_msg_date > message_end_date:
                    continue  # Thread starts after filter range ends

                if message_start_date is not None and last_msg_date < message_start_date:
                    continue  # Thread ends before filter range starts

            # Apply participant count filters (only if filtering is active)
            if has_filtering and min_participants is not None:
                if participant_count < min_participants:
                    continue

            if has_filtering and max_participants is not None:
                if participant_count > max_participants:
                    continue

            # Apply message count filters (only if filtering is active)
            if has_filtering and min_messages is not None:
                if message_count < min_messages:
                    continue

            if has_filtering and max_messages is not None:
                if message_count > max_messages:
                    continue

            # Apply source filter (only if filtering is active)
            if has_filtering and source:
                if not archive or archive.get("source") != source:
                    continue

            # Enrich thread with archive source
            thread["archive_source"] = archive.get("source") if archive else None

            enriched_threads.append(thread)

        # Apply skip and limit
        return enriched_threads[skip : skip + limit]

    def get_thread_by_id(self, thread_id: str) -> dict[str, Any] | None:
        """Get a specific thread by ID.

        Args:
            thread_id: Thread identifier

        Returns:
            Thread document or None
        """
        # Query by _id field which should match thread_id
        results = self.document_store.query_documents(
            "threads",
            filter_dict={"_id": thread_id},
            limit=1,
        )

        return results[0] if results else None

    def get_messages(
        self,
        limit: int = 10,
        skip: int = 0,
        thread_id: str | None = None,
        message_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of messages with optional filters.

        Args:
            limit: Maximum number of results
            skip: Number of results to skip
            thread_id: Filter by thread ID (optional)
            message_id: Filter by RFC 5322 Message-ID (optional)

        Returns:
            List of message documents
        """
        filter_dict = {}
        if thread_id:
            filter_dict["thread_id"] = thread_id
        if message_id:
            filter_dict["message_id"] = message_id

        # TODO: Optimize pagination to use native skip in document store query
        # Currently fetches limit + skip records and discards skip records in memory
        # This matches existing pattern in get_reports but should be improved for scalability
        messages = self.document_store.query_documents(
            "messages",
            filter_dict=filter_dict,
            limit=limit + skip,
        )

        # Apply skip and limit
        return messages[skip : skip + limit]

    def get_message_by_id(self, message_doc_id: str) -> dict[str, Any] | None:
        """Get a specific message by its document ID.

        Args:
            message_doc_id: Message document identifier (_id field)

        Returns:
            Message document or None
        """
        results = self.document_store.query_documents(
            "messages",
            filter_dict={"_id": message_doc_id},
            limit=1,
        )

        return results[0] if results else None

    def get_chunks(
        self,
        limit: int = 10,
        skip: int = 0,
        message_id: str | None = None,
        thread_id: str | None = None,
        message_doc_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of chunks with optional filters.

        Args:
            limit: Maximum number of results
            skip: Number of results to skip
            message_id: Filter by RFC 5322 Message-ID (optional)
            thread_id: Filter by thread ID (optional)
            message_doc_id: Filter by message document ID (optional)

        Returns:
            List of chunk documents
        """
        filter_dict = {}
        if message_id:
            filter_dict["message_id"] = message_id
        if thread_id:
            filter_dict["thread_id"] = thread_id
        if message_doc_id:
            filter_dict["message_doc_id"] = message_doc_id

        # TODO: Optimize pagination to use native skip in document store query
        # Currently fetches limit + skip records and discards skip records in memory
        # This matches existing pattern in get_reports but should be improved for scalability
        chunks = self.document_store.query_documents(
            "chunks",
            filter_dict=filter_dict,
            limit=limit + skip,
        )

        # Apply skip and limit
        return chunks[skip : skip + limit]

    def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get a specific chunk by ID.

        Args:
            chunk_id: Chunk identifier (_id field)

        Returns:
            Chunk document or None
        """
        results = self.document_store.query_documents(
            "chunks",
            filter_dict={"_id": chunk_id},
            limit=1,
        )

        return results[0] if results else None

    def _handle_source_deletion_requested(self, event: dict[str, Any]):
        """Handle SourceDeletionRequested event to clean up reporting-owned data.

        This handler deletes summaries and reports associated with a source.
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
            "Starting cascade cleanup for source in reporting service",
            source_name=source_name,
            correlation_id=correlation_id,
            archive_count=len(archive_ids),
        )

        deletion_counts = {
            "summaries": 0,
        }

        try:
            # Delete summaries for the source
            try:
                # Try querying by source first
                summaries = self.document_store.query_documents(
                    "summaries",
                    {"source": source_name}
                ) or []

                # If no summaries found by source and we have archive_ids, try by archive_id
                if not summaries and archive_ids:
                    for archive_id in archive_ids:
                        archive_summaries = self.document_store.query_documents(
                            "summaries",
                            {"archive_id": archive_id}
                        ) or []
                        summaries.extend(archive_summaries)

                for summary in summaries:
                    summary_id = summary.get("_id")
                    if summary_id:
                        try:
                            self.document_store.delete_document("summaries", summary_id)
                            deletion_counts["summaries"] += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to delete summary during cascade cleanup",
                                summary_id=summary_id,
                                source_name=source_name,
                                error=str(e),
                            )
                logger.info(
                    "Deleted summaries for source",
                    source_name=source_name,
                    count=deletion_counts["summaries"],
                )
            except Exception as e:
                logger.error(
                    "Failed to query/delete summaries during cascade cleanup",
                    source_name=source_name,
                    error=str(e),
                    exc_info=True,
                )

            # Emit metrics
            if self.metrics_collector:
                self.metrics_collector.increment(
                    "reporting_cascade_cleanup_total",
                    tags={"source_name": source_name}
                )
                if deletion_counts["summaries"] > 0:
                    self.metrics_collector.gauge(
                        "reporting_cascade_cleanup_summaries",
                        float(deletion_counts["summaries"]),
                        tags={"source_name": source_name}
                    )

            processing_time = time.time() - start_time
            logger.info(
                "Cascade cleanup completed in reporting service",
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
                        "service_name": "reporting",
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
                "Cascade cleanup failed in reporting service",
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
                        "service_name": "reporting",
                        "status": "failed",
                        "deletion_counts": deletion_counts,
                        "error_summary": f"Reporting cleanup failed: {str(e)[:200]}",
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
                        "service": "reporting",
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
            "reports_stored": self.reports_stored,
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "last_processing_time_seconds": self.last_processing_time,
        }
