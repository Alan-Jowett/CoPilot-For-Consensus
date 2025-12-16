# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main reporting service implementation."""

import logging
import time
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    SummaryCompleteEvent,
    ReportPublishedEvent,
    ReportDeliveryFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter
from copilot_vectorstore import VectorStore
from copilot_embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class ReportingService:
    """Main reporting service for storing and serving summaries."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
        webhook_url: Optional[str] = None,
        notify_enabled: bool = False,
        webhook_summary_max_length: int = 500,
        vector_store: Optional[VectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
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
        
        logger.info("Subscribed to summary.complete events")
        logger.info("Reporting service is ready")

    def _handle_summary_complete(self, event: Dict[str, Any]):
        """Handle SummaryComplete event.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.
        
        Args:
            event: Event dictionary
        """
        start_time = time.time()
        
        try:
            # Parse event
            summary_complete = SummaryCompleteEvent(data=event.get("data", {}))
            
            logger.info(f"Received SummaryComplete event: {summary_complete.data.get('thread_id')}")
            
            # Process the summary
            self.process_summary(summary_complete.data, event)
            
            # Record processing time
            self.last_processing_time = time.time() - start_time
            
            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment("reporting_events_total", tags={"event_type": "summary_complete", "outcome": "success"})
                self.metrics_collector.observe("reporting_latency_seconds", self.last_processing_time)
            
        except Exception as e:
            logger.error(f"Error handling SummaryComplete event: {e}", exc_info=True)
            
            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment("reporting_events_total", tags={"event_type": "summary_complete", "outcome": "error"})
                self.metrics_collector.increment("reporting_failures_total", tags={"error_type": type(e).__name__})
            
            # Report error
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_summary(self, event_data: Dict[str, Any], full_event: Dict[str, Any]) -> str:
        """Process and store a summary.
        
        Args:
            event_data: Data from SummaryComplete event
            full_event: Full event envelope
            
        Returns:
            Report ID
        """
        # Generate report ID
        report_id = str(uuid.uuid4())
        
        # Extract data from event
        thread_id = event_data.get("thread_id")
        summary_markdown = event_data.get("summary_markdown", "")
        citations = event_data.get("citations", [])
        llm_backend = event_data.get("llm_backend", "")
        llm_model = event_data.get("llm_model", "")
        tokens_prompt = event_data.get("tokens_prompt", 0)
        tokens_completion = event_data.get("tokens_completion", 0)
        latency_ms = event_data.get("latency_ms", 0)
        
        # Create summary document
        now = datetime.now(timezone.utc).isoformat()
        summary_doc = {
            "summary_id": report_id,
            "thread_id": thread_id,
            "summary_type": "thread",
            "title": f"Summary for {thread_id}",
            "content_markdown": summary_markdown,
            "citations": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "message_id": c.get("message_id", ""),
                    "quote": "",  # Not provided in SummaryComplete event
                    "relevance_score": 1.0,  # Default score; not provided in event
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
                # Store original event citations with offset for reference
                "original_citations": citations,
            },
        }
        
        # Store summary
        logger.info(f"Storing summary {report_id} for thread {thread_id}")
        self.document_store.insert_document("summaries", summary_doc)
        self.reports_stored += 1
        
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
                    self.metrics_collector.increment("reporting_delivery_total", tags={"channel": "webhook", "status": "success"})
                    
            except Exception as e:
                # Webhook notifications are best-effort - log and publish failure event but continue
                logger.warning(f"Failed to send webhook notification: {e}", exc_info=True)
                self.notifications_failed += 1
                
                if self.metrics_collector:
                    self.metrics_collector.increment("reporting_delivery_total", tags={"channel": "webhook", "status": "failed"})
                
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
                        self.error_reporter.capture_exception()
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
            "summary": summary[:self.webhook_summary_max_length],  # Truncate for webhook
            "url": f"/api/reports/{report_id}",
        }
        
        response = requests.post(
            self.webhook_url,
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
        delivery_channels: List[str],
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
        except Exception:
            logger.exception(f"Exception while publishing ReportPublished event for {report_id}")
            if self.error_reporter:
                self.error_reporter.capture_exception()
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
        except Exception:
            logger.exception(f"Exception while publishing ReportDeliveryFailed event for {report_id}")
            if self.error_reporter:
                self.error_reporter.capture_exception()
            raise
        
        logger.warning(f"Published ReportDeliveryFailed event for {report_id}")

    def get_reports(
        self,
        thread_id: Optional[str] = None,
        limit: int = 10,
        skip: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source: Optional[str] = None,
        min_participants: Optional[int] = None,
        max_participants: Optional[int] = None,
        min_messages: Optional[int] = None,
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of reports with optional filters.
        
        Args:
            thread_id: Filter by thread ID (optional)
            limit: Maximum number of results
            skip: Number of results to skip
            start_date: Filter reports generated after this date (ISO 8601)
            end_date: Filter reports generated before this date (ISO 8601)
            source: Filter by archive source (optional)
            min_participants: Filter by minimum participant count (optional)
            max_participants: Filter by maximum participant count (optional)
            min_messages: Filter by minimum message count (optional)
            max_messages: Filter by maximum message count (optional)
            
        Returns:
            List of report documents with enriched metadata
        """
        # Build filter for summaries
        filter_dict = {}
        if thread_id:
            filter_dict["thread_id"] = thread_id
        
        # Add date filters
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            if date_filter:
                filter_dict["generated_at"] = date_filter
        
        # Fetch summaries (fetch more for skip and filtering)
        summaries = self.document_store.query_documents(
            "summaries",
            filter_dict=filter_dict,
            limit=limit + skip + 100,  # Buffer for filtering
        )
        
        # If we have filters that require thread/archive data, enrich the results
        if source or min_participants is not None or max_participants is not None or \
           min_messages is not None or max_messages is not None:
            enriched_summaries = []
            
            for summary in summaries:
                thread_id_val = summary.get("thread_id")
                if not thread_id_val:
                    continue
                
                # Get thread metadata
                thread = self._get_thread_by_id(thread_id_val)
                if not thread:
                    continue
                
                # Apply thread-based filters
                if min_participants is not None:
                    participant_count = len(thread.get("participants", []))
                    if participant_count < min_participants:
                        continue
                
                if max_participants is not None:
                    participant_count = len(thread.get("participants", []))
                    if participant_count > max_participants:
                        continue
                
                if min_messages is not None:
                    message_count = thread.get("message_count", 0)
                    if message_count < min_messages:
                        continue
                
                if max_messages is not None:
                    message_count = thread.get("message_count", 0)
                    if message_count > max_messages:
                        continue
                
                # Apply source filter
                if source:
                    archive_id = thread.get("archive_id")
                    if archive_id:
                        archive = self._get_archive_by_id(archive_id)
                        if not archive or archive.get("source") != source:
                            continue
                    else:
                        continue
                
                # Enrich summary with thread and archive metadata
                archive_id = thread.get("archive_id")
                archive = self._get_archive_by_id(archive_id) if archive_id else None
                
                summary["thread_metadata"] = {
                    "subject": thread.get("subject", ""),
                    "participants": thread.get("participants", []),
                    "participant_count": len(thread.get("participants", [])),
                    "message_count": thread.get("message_count", 0),
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
        
        # Apply skip and limit
        return summaries[skip:skip + limit]
    
    def _get_thread_by_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
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
    
    def _get_archive_by_id(self, archive_id: str) -> Optional[Dict[str, Any]]:
        """Get archive metadata by ID.
        
        Args:
            archive_id: Archive identifier
            
        Returns:
            Archive document or None
        """
        try:
            results = self.document_store.query_documents(
                "archives",
                filter_dict={"archive_id": archive_id},
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
    ) -> List[Dict[str, Any]]:
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
                    thread_scores[thread_id]["max_score"] = max(
                        thread_scores[thread_id]["max_score"], result.score
                    )
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
    
    def get_available_sources(self) -> List[str]:
        """Get list of available archive sources.
        
        Returns:
            List of unique source names
        """
        try:
            archives = self.document_store.query_documents(
                "archives",
                filter_dict={},
                limit=1000,  # Should be enough for most use cases
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

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific report by ID.
        
        Args:
            report_id: Report identifier
            
        Returns:
            Report document or None
        """
        results = self.document_store.query_documents(
            "summaries",
            filter_dict={"summary_id": report_id},
            limit=1,
        )
        
        return results[0] if results else None

    def get_thread_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
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

    def get_stats(self) -> Dict[str, Any]:
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
