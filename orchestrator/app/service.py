# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main orchestration service implementation."""

import hashlib
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
from copilot_logging import create_logger

logger = create_logger(name="orchestrator")


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

    def start(self, enable_startup_requeue: bool = True):
        """Start the orchestration service and subscribe to events.
        
        Args:
            enable_startup_requeue: Whether to requeue incomplete documents on startup (default: True)
        """
        logger.info("Starting Orchestration Service")

        # Requeue incomplete threads on startup
        if enable_startup_requeue:
            self._requeue_incomplete_threads()

        # Subscribe to EmbeddingsGenerated events
        self.subscriber.subscribe(
            event_type="EmbeddingsGenerated",
            callback=self._handle_embeddings_generated,
            routing_key="embeddings.generated",
            exchange="copilot.events",
        )

        logger.info("Subscribed to embeddings.generated events")
        logger.info("Orchestration service is ready")
    
    def _requeue_incomplete_threads(self):
        """Requeue threads ready for summarization on startup for forward progress."""
        try:
            from copilot_startup import StartupRequeue
            
            logger.info("Scanning for threads ready for summarization to requeue on startup...")
            
            requeue = StartupRequeue(
                document_store=self.document_store,
                publisher=self.publisher,
                metrics_collector=self.metrics_collector,
            )
            
            # Find threads that don't have summaries and have all chunks embedded
            # This requires verifying embeddings are complete before triggering summarization
            try:
                # Get threads without summaries
                threads = self.document_store.query_documents(
                    collection="threads",
                    filter_dict={"summary_id": None},
                    limit=500,
                )
                
                if not threads:
                    logger.info("No threads without summaries found")
                    return
                
                # Collect all thread IDs to batch-fetch chunks for all threads at once
                thread_ids = [
                    thread.get("thread_id")
                    for thread in threads
                    if thread.get("thread_id") is not None
                ]
                
                if not thread_ids:
                    logger.info("No valid thread IDs found for threads without summaries")
                    return
                
                # Batch query: fetch chunks for all relevant threads in a single call
                logger.debug(
                    f"Batch querying chunks for {len(thread_ids)} threads to check embedding status"
                )
                chunks = self.document_store.query_documents(
                    collection="chunks",
                    filter_dict={"thread_id": {"$in": thread_ids}},
                    limit=len(thread_ids) * 1000,
                )
                
                # Group chunks by thread_id for efficient per-thread checks
                chunks_by_thread = {}
                for chunk in chunks:
                    chunk_thread_id = chunk.get("thread_id")
                    if chunk_thread_id is None:
                        continue
                    chunks_by_thread.setdefault(chunk_thread_id, []).append(chunk)
                
                # For each thread, verify all chunks have embeddings
                ready_threads = []
                for thread in threads:
                    thread_id = thread.get("thread_id")
                    if thread_id is None:
                        logger.debug(f"Skipping thread without thread_id: {thread}")
                        continue
                    
                    thread_chunks = chunks_by_thread.get(thread_id, [])
                    
                    if not thread_chunks:
                        logger.debug(f"Thread {thread_id} has no chunks, skipping")
                        continue
                    
                    # Check if all chunks have embeddings
                    all_embedded = all(
                        chunk.get("embedding_generated", False) for chunk in thread_chunks
                    )
                    
                    if all_embedded:
                        ready_threads.append(thread)
                    else:
                        logger.debug(
                            f"Thread {thread_id} has {len(thread_chunks)} chunks but not all have embeddings"
                        )
                
                if not ready_threads:
                    logger.info("No threads with complete embeddings found")
                    return
                
                logger.info(f"Found {len(ready_threads)} threads ready for summarization")
                
                # Requeue each ready thread
                requeued = 0
                for thread in ready_threads:
                    thread_id = thread.get("thread_id")
                    archive_id = thread.get("archive_id")
                    
                    event_data = {
                        "thread_ids": [thread_id],
                        "archive_id": archive_id,
                    }
                    
                    try:
                        self.publisher.publish(
                            event_type="SummarizationRequested",
                            data=event_data,
                            routing_key="summarization.requested",
                            exchange="copilot.events",
                        )
                        requeued += 1
                        logger.debug(f"Requeued thread {thread_id} for summarization")
                    except Exception as e:
                        logger.error(f"Failed to requeue thread {thread_id}: {e}")
                
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "startup_requeue_documents_total",
                        requeued,
                        tags={"collection": "threads"}
                    )
                
                logger.info(f"Startup requeue: {requeued} threads ready for summarization requeued")
                
            except Exception as e:
                logger.error(f"Error querying for ready threads: {e}", exc_info=True)
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "startup_requeue_errors_total",
                        1,
                        tags={"collection": "threads", "error_type": type(e).__name__}
                    )
            
        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

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
            
        Raises:
            ValueError: If required fields are missing
            TypeError: If fields have invalid types
        """
        # Validate chunk_ids field exists
        if "chunk_ids" not in event_data:
            error_msg = "chunk_ids field missing from event data"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        chunk_ids = event_data["chunk_ids"]
        
        # Validate chunk_ids is a list
        if not isinstance(chunk_ids, list):
            error_msg = f"chunk_ids must be a list, got {type(chunk_ids).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        # Empty list is valid - nothing to process
        if not chunk_ids:
            logger.info("Empty chunk list in EmbeddingsGenerated event, nothing to process")
            return
        
        start_time = time.time()

        try:
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
            chunk_ids: List of chunk IDs (_id values)

        Returns:
            List of unique thread IDs
        """
        thread_ids: Set[str] = set()

        try:
            # Query document store for chunks by _id
            chunks = self.document_store.query_documents(
                "chunks",
                {"_id": {"$in": chunk_ids}},
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
        
        Checks if a summary already exists for the same set of chunks. Only triggers
        summarization if the chunks have changed (different top-k selection) to avoid
        duplicate work and ensure summaries are regenerated when content changes.

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

            # Calculate expected summary_id based on chunks that would be used
            chunks = context.get("chunks", [])
            expected_summary_id = self._calculate_summary_id(thread_id, chunks)
            
            # Check if a summary already exists with this exact set of chunks
            if self._summary_exists(expected_summary_id):
                logger.info(f"Summary already exists for thread {thread_id} with current chunks (summary_id={expected_summary_id[:16]}), skipping")
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "orchestrator_summary_skipped_total",
                        tags={"reason": "summary_already_exists"}
                    )
                return

            # Publish SummarizationRequested event
            self._publish_summarization_requested(
                thread_ids=[thread_id],
                context=context
            )

            if self.metrics_collector:
                self.metrics_collector.increment(
                    "orchestrator_summary_triggered_total",
                    tags={"reason": "chunks_changed"}
                )

            logger.info(f"Published SummarizationRequested for thread {thread_id} (expected summary_id={expected_summary_id[:16]})")

        except Exception as e:
            logger.error(f"Error in _orchestrate_thread for {thread_id}: {e}", exc_info=True)
            raise
    
    def _calculate_summary_id(self, thread_id: str, chunks: List[Dict[str, Any]]) -> str:
        """Calculate deterministic summary ID from thread and chunks.
        
        Uses the same algorithm as the summarization service to predict what
        the summary_id will be. This allows checking if a summary already exists
        before triggering regeneration.
        
        Args:
            thread_id: Thread identifier
            chunks: List of chunk documents that will be used for summarization
            
        Returns:
            Hex string of SHA256 hash (64 characters)
        """
        # Extract and sort chunk IDs (_id field) to ensure consistent ordering
        chunk_ids = sorted({chunk.get("_id") for chunk in chunks if chunk.get("_id")})
        
        # Combine thread_id and canonical _ids into a single string (matches summarization service)
        id_input = f"{thread_id}:{','.join(chunk_ids)}"
        
        # Generate SHA256 hash
        hash_obj = hashlib.sha256(id_input.encode("utf-8"))
        return hash_obj.hexdigest()
    
    def _summary_exists(self, summary_id: str) -> bool:
        """Check if a summary exists for the given summary_id.
        
        Queries the summaries collection using the truncated 16-char ID that
        matches the reporting service's storage format.
        
        Args:
            summary_id: Full 64-character SHA256 summary_id
            
        Returns:
            True if summary exists, False otherwise
        """
        try:
            # Generate 16-char ID (matches reporting service's truncation logic)
            truncated_id = hashlib.sha256(summary_id.encode()).hexdigest()[:16]
            
            # Check if summary document exists
            summaries = self.document_store.query_documents(
                "summaries",
                {"_id": truncated_id},
                limit=1
            )
            
            return len(summaries) > 0
            
        except Exception as e:
            logger.error(f"Error checking if summary exists: {e}", exc_info=True)
            # On error, assume summary doesn't exist to avoid blocking summarization
            return False

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
            message_doc_ids = list(set(chunk.get("message_doc_id") for chunk in chunks if chunk.get("message_doc_id")))
            messages = []

            if message_doc_ids:
                messages = self.document_store.query_documents(
                    "messages",
                    {"_id": {"$in": message_doc_ids}},
                    limit=len(message_doc_ids)
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
                    tags={"event_type": "summarization_requested", "outcome": "success"}
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
                    tags={"event_type": "orchestration_failed", "outcome": "failure"}
                )
                self.metrics_collector.increment(
                    "orchestration_failures_total",
                    tags={"error_type": error_type}
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
