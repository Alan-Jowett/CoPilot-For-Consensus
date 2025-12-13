# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main orchestration service implementation."""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    EmbeddingsGeneratedEvent,
    SummarizationRequestedEvent,
    OrchestrationFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter

logger = logging.getLogger(__name__)


class OrchestrationService:
    """Main orchestration service for coordinating summarization workflows."""

    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        top_k: int = 12,
        context_window_tokens: int = 3000,
        llm_backend: str = "ollama",
        llm_model: str = "mistral",
        llm_temperature: float = 0.2,
        llm_max_tokens: int = 2048,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        """Initialize orchestration service.

        Args:
            document_store: Document store for retrieving chunk metadata
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            top_k: Number of top chunks to retrieve per thread
            context_window_tokens: Token budget for prompt context
            llm_backend: LLM backend (ollama, azure, openai)
            llm_model: Model identifier
            llm_temperature: Sampling temperature
            llm_max_tokens: Maximum tokens for response
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
        """
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.top_k = top_k
        self.context_window_tokens = context_window_tokens
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.llm_max_tokens = llm_max_tokens
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter

        # Stats
        self.events_processed = 0
        self.threads_orchestrated = 0
        self.failures_count = 0
        self.last_processing_time = 0.0

    def start(self):
        """Start the orchestration service and subscribe to events."""
        logger.info("Starting Orchestration Service")

        # Subscribe to EmbeddingsGenerated events
        self.subscriber.subscribe(
            event_type="EmbeddingsGenerated",
            callback=self._handle_embeddings_generated,
            routing_key="embeddings.generated",
            exchange="copilot.events",
        )

        logger.info("Subscribed to embeddings.generated events")
        logger.info("Orchestration service is ready")

    def _handle_embeddings_generated(self, event: Dict[str, Any]):
        """Handle EmbeddingsGenerated event.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.

        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            embeddings_event = EmbeddingsGeneratedEvent(data=event.get("data", {}))

            chunk_count = len(embeddings_event.data.get('chunk_ids', []))
            logger.info(f"Received EmbeddingsGenerated event with {chunk_count} chunks")

            # Process the embeddings
            self.process_embeddings(embeddings_event.data)

            self.events_processed += 1

        except Exception as e:
            logger.error(f"Error handling EmbeddingsGenerated event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            self.failures_count += 1
            raise  # Re-raise to trigger message requeue for transient failures

    def process_embeddings(self, event_data: Dict[str, Any]):
        """Process embeddings and orchestrate summarization.

        Args:
            event_data: Data from EmbeddingsGenerated event
        """
        start_time = time.time()

        try:
            chunk_ids = event_data.get("chunk_ids", [])
            if not chunk_ids:
                logger.warning("No chunk_ids in EmbeddingsGenerated event")
                return

            # Resolve affected threads
            logger.info(f"Resolving threads for {len(chunk_ids)} chunks...")
            thread_ids = self._resolve_threads(chunk_ids)

            if not thread_ids:
                logger.warning("No threads resolved from chunks")
                return

            logger.info(f"Resolved {len(thread_ids)} threads: {thread_ids}")

            # Orchestrate summarization for each thread
            for thread_id in thread_ids:
                try:
                    self._orchestrate_thread(thread_id)
                    self.threads_orchestrated += 1
                except Exception as e:
                    logger.error(f"Error orchestrating thread {thread_id}: {e}", exc_info=True)
                    self._publish_orchestration_failed([thread_id], str(e), type(e).__name__)

        finally:
            self.last_processing_time = time.time() - start_time
            logger.info(f"Processing completed in {self.last_processing_time:.2f}s")

    def _resolve_threads(self, chunk_ids: List[str]) -> List[str]:
        """Resolve thread IDs from chunk IDs.

        Args:
            chunk_ids: List of chunk IDs

        Returns:
            List of unique thread IDs
        """
        thread_ids: Set[str] = set()

        try:
            # Query document store for chunks
            chunks = self.document_store.query_documents(
                "chunks",
                {"chunk_id": {"$in": chunk_ids}},
                limit=len(chunk_ids)
            )

            for chunk in chunks:
                thread_id = chunk.get("thread_id")
                if thread_id:
                    thread_ids.add(thread_id)

            logger.info(f"Resolved {len(thread_ids)} unique threads from {len(chunk_ids)} chunks")

        except Exception as e:
            logger.error(f"Error resolving threads: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"chunk_ids": chunk_ids})
            raise

        return list(thread_ids)

    def _orchestrate_thread(self, thread_id: str):
        """Orchestrate summarization for a single thread.

        Args:
            thread_id: Thread ID to orchestrate
        """
        logger.info(f"Orchestrating thread: {thread_id}")

        try:
            # Retrieve top-k chunks for this thread
            context = self._retrieve_context(thread_id)

            if not context:
                logger.warning(f"No context retrieved for thread {thread_id}")
                return

            # Publish SummarizationRequested event
            self._publish_summarization_requested(
                thread_ids=[thread_id],
                context=context
            )

            logger.info(f"Published SummarizationRequested for thread {thread_id}")

        except Exception as e:
            logger.error(f"Error in _orchestrate_thread for {thread_id}: {e}", exc_info=True)
            raise

    def _retrieve_context(self, thread_id: str) -> Dict[str, Any]:
        """Retrieve top-k chunks and metadata for a thread.

        Args:
            thread_id: Thread ID

        Returns:
            Context dictionary with chunks and metadata
        """
        try:
            # Get chunks for this thread from document store
            chunks = self.document_store.query_documents(
                "chunks",
                {"thread_id": thread_id, "embedding_generated": True},
                limit=self.top_k
            )

            if not chunks:
                logger.warning(f"No chunks found for thread {thread_id}")
                return {}

            # Get message metadata
            message_ids = list(set(chunk.get("message_id") for chunk in chunks if chunk.get("message_id")))
            messages = []

            if message_ids:
                messages = self.document_store.query_documents(
                    "messages",
                    {"message_id": {"$in": message_ids}},
                    limit=len(message_ids)
                )

            context = {
                "thread_id": thread_id,
                "chunk_count": len(chunks),
                "chunks": chunks[:self.top_k],  # Limit to top_k
                "messages": messages,
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Retrieved {len(chunks)} chunks and {len(messages)} messages for thread {thread_id}")

            return context

        except Exception as e:
            logger.error(f"Error retrieving context for thread {thread_id}: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_id": thread_id})
            raise

    def _publish_summarization_requested(self, thread_ids: List[str], context: Dict[str, Any]):
        """Publish SummarizationRequested event.

        Args:
            thread_ids: List of thread IDs
            context: Retrieved context
        """
        try:
            event_data = {
                "thread_ids": thread_ids,
                "top_k": self.top_k,
                "llm_backend": self.llm_backend,
                "llm_model": self.llm_model,
                "context_window_tokens": self.context_window_tokens,
                "prompt_template": "consensus-summary-v1",
                "chunk_count": context.get("chunk_count", 0),
                "message_count": len(context.get("messages", [])),
            }

            event = SummarizationRequestedEvent(data=event_data)

            self.publisher.publish(
                exchange="copilot.events",
                routing_key="summarization.requested",
                event=event.to_dict()
            )

            logger.info(f"Published SummarizationRequested for threads: {thread_ids}")

            if self.metrics_collector:
                self.metrics_collector.increment(
                    "orchestration_events_total",
                    labels={"event_type": "summarization_requested", "outcome": "success"}
                )

        except Exception as e:
            logger.error(f"Error publishing SummarizationRequested: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_ids": thread_ids})
            raise

    def _publish_orchestration_failed(self, thread_ids: List[str], error_message: str, error_type: str):
        """Publish OrchestrationFailed event.

        Args:
            thread_ids: List of thread IDs
            error_message: Error message
            error_type: Error type
        """
        try:
            event_data = {
                "thread_ids": thread_ids,
                "error_type": error_type,
                "error_message": error_message,
                "retry_count": 0
            }

            event = OrchestrationFailedEvent(data=event_data)

            self.publisher.publish(
                exchange="copilot.events",
                routing_key="orchestration.failed",
                event=event.to_dict()
            )

            logger.info(f"Published OrchestrationFailed for threads: {thread_ids}")

            if self.metrics_collector:
                self.metrics_collector.increment(
                    "orchestration_events_total",
                    labels={"event_type": "orchestration_failed", "outcome": "failure"}
                )
                self.metrics_collector.increment(
                    "orchestration_failures_total",
                    labels={"error_type": error_type}
                )

        except Exception as e:
            logger.error(f"Error publishing OrchestrationFailed: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_ids": thread_ids})
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "events_processed": self.events_processed,
            "threads_orchestrated": self.threads_orchestrated,
            "failures_count": self.failures_count,
            "last_processing_time_seconds": self.last_processing_time,
            "config": {
                "top_k": self.top_k,
                "context_window_tokens": self.context_window_tokens,
                "llm_backend": self.llm_backend,
                "llm_model": self.llm_model,
            }
        }
