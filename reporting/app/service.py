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
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        self.webhook_url = webhook_url
        self.notify_enabled = notify_enabled
        self.webhook_summary_max_length = webhook_summary_max_length
        
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
        logged but not re-raised to prevent message requeue. Error state is
        tracked in metrics and reported to error tracking service.
        
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
                self._publish_delivery_failed(report_id, thread_id, "webhook", str(e), type(e).__name__)
        
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
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="report.published",
            message=event.to_dict(),
        )
        
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
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="report.delivery.failed",
            message=event.to_dict(),
        )
        
        logger.warning(f"Published ReportDeliveryFailed event for {report_id}")

    def get_reports(
        self,
        thread_id: Optional[str] = None,
        limit: int = 10,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get list of reports with optional filters.
        
        Args:
            thread_id: Filter by thread ID (optional)
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of report documents
        """
        filter_dict = {}
        if thread_id:
            filter_dict["thread_id"] = thread_id
        
        # DocumentStore doesn't support skip, so we fetch more and slice
        results = self.document_store.query_documents(
            "summaries",
            filter_dict=filter_dict,
            limit=limit + skip,
        )
        
        # Apply skip by slicing the results
        return results[skip:skip + limit]

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
