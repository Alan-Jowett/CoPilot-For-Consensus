# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main summarization service implementation."""

import logging
import time
from typing import Optional, Dict, Any, List

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    SummarizationRequestedEvent,
    SummaryCompleteEvent,
    SummarizationFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_vectorstore import VectorStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter
from copilot_summarization import Summarizer, Thread, Citation

logger = logging.getLogger(__name__)


class SummarizationService:
    """Main summarization service for generating citation-rich summaries."""

    def __init__(
        self,
        document_store: DocumentStore,
        vector_store: VectorStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        summarizer: Summarizer,
        top_k: int = 12,
        citation_count: int = 12,
        retry_max_attempts: int = 3,
        retry_backoff_seconds: int = 5,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        """Initialize summarization service.
        
        Args:
            document_store: Document store for retrieving message metadata
            vector_store: Vector store for retrieving relevant chunks
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            summarizer: Summarizer implementation (LLM backend)
            top_k: Number of top chunks to retrieve per thread
            citation_count: Maximum citations per summary
            retry_max_attempts: Maximum retry attempts on failures
            retry_backoff_seconds: Base backoff interval for retries
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
        """
        self.document_store = document_store
        self.vector_store = vector_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.summarizer = summarizer
        self.top_k = top_k
        self.citation_count = citation_count
        self.retry_max_attempts = retry_max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        
        # Stats
        self.summaries_generated = 0
        self.summarization_failures = 0
        self.last_processing_time = 0.0

    def start(self):
        """Start the summarization service and subscribe to events."""
        logger.info("Starting Summarization Service")
        
        # Subscribe to SummarizationRequested events
        self.subscriber.subscribe(
            event_type="SummarizationRequested",
            exchange="copilot.events",
            routing_key="summarization.requested",
            callback=self._handle_summarization_requested,
        )
        
        logger.info("Subscribed to summarization.requested events")
        logger.info("Summarization service is ready")

    def _handle_summarization_requested(self, event: Dict[str, Any]):
        """Handle SummarizationRequested event.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.
        
        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            summarization_requested = SummarizationRequestedEvent(data=event.get("data", {}))
            
            logger.info(f"Received SummarizationRequested event for {len(summarization_requested.data.get('thread_ids', []))} threads")
            
            # Process each thread
            self.process_summarization(summarization_requested.data)
            
        except Exception as e:
            logger.error(f"Error handling SummarizationRequested event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            raise  # Re-raise to trigger message requeue for transient failures

    def process_summarization(self, event_data: Dict[str, Any]):
        """Process summarization request for threads.
        
        Args:
            event_data: Data from SummarizationRequested event
            
        Raises:
            KeyError: If required fields are missing from event_data
            TypeError: If thread_ids is not a list
        """
        # Check for required field
        if "thread_ids" not in event_data:
            error_msg = "thread_ids field missing from event data"
            logger.error(error_msg)
            raise KeyError(error_msg)
            
        thread_ids = event_data["thread_ids"]
        
        # Validate thread_ids is iterable (list/array)
        if not isinstance(thread_ids, list):
            error_msg = f"thread_ids must be a list, got {type(thread_ids).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
            
        top_k = event_data.get("top_k", self.top_k)
        context_window_tokens = event_data.get("context_window_tokens", 3000)
        prompt_template = event_data.get("prompt_template", "Summarize the following discussion thread:")
        
        for thread_id in thread_ids:
            self._process_thread(
                thread_id=thread_id,
                top_k=top_k,
                context_window_tokens=context_window_tokens,
                prompt_template=prompt_template,
            )

    def _process_thread(
        self,
        thread_id: str,
        top_k: int,
        context_window_tokens: int,
        prompt_template: str,
    ):
        """Process a single thread for summarization.
        
        Args:
            thread_id: Thread identifier
            top_k: Number of chunks to retrieve
            context_window_tokens: Token budget for context
            prompt_template: Prompt template to use
        """
        start_time = time.time()
        retry_count = 0
        
        while retry_count < self.retry_max_attempts:
            try:
                logger.info(f"Processing thread {thread_id} (attempt {retry_count + 1})")
                
                # Retrieve context
                context = self._retrieve_context(thread_id, top_k)
                
                if not context or not context.get("messages"):
                    logger.warning(f"No context retrieved for thread {thread_id}")
                    self._publish_summarization_failed(
                        thread_id=thread_id,
                        error_type="NoContextError",
                        error_message="No context retrieved from vector/document stores",
                        retry_count=retry_count,
                    )
                    return
                
                # Build thread object
                thread = Thread(
                    thread_id=thread_id,
                    messages=context["messages"],
                    top_k=top_k,
                    context_window_tokens=context_window_tokens,
                    prompt_template=prompt_template,
                )
                
                # Generate summary
                summary = self.summarizer.summarize(thread)
                
                # Format citations
                formatted_citations = self._format_citations(
                    summary.citations,
                    context.get("chunks", []),
                )
                
                # Calculate duration
                duration = time.time() - start_time
                self.last_processing_time = duration
                
                # Update stats
                self.summaries_generated += 1
                
                # Publish success event
                self._publish_summary_complete(
                    thread_id=thread_id,
                    summary_markdown=summary.summary_markdown,
                    citations=formatted_citations,
                    llm_backend=summary.llm_backend,
                    llm_model=summary.llm_model,
                    tokens_prompt=summary.tokens_prompt,
                    tokens_completion=summary.tokens_completion,
                    latency_ms=summary.latency_ms,
                )
                
                logger.info(
                    f"Successfully summarized thread {thread_id} "
                    f"(tokens: {summary.tokens_prompt}+{summary.tokens_completion}, "
                    f"latency: {summary.latency_ms}ms)"
                )
                
                # Collect metrics
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "summarization_events_total",
                        tags={"event_type": "requested", "outcome": "success"},
                    )
                    self.metrics_collector.observe(
                        "summarization_latency_seconds",
                        duration,
                    )
                    self.metrics_collector.increment(
                        "summarization_llm_calls_total",
                        tags={"backend": summary.llm_backend, "model": summary.llm_model},
                    )
                    self.metrics_collector.increment(
                        "summarization_tokens_total",
                        summary.tokens_prompt,
                        tags={"type": "prompt"},
                    )
                    self.metrics_collector.increment(
                        "summarization_tokens_total",
                        summary.tokens_completion,
                        tags={"type": "completion"},
                    )
                
                return
                
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"Error summarizing thread {thread_id} "
                    f"(attempt {retry_count}/{self.retry_max_attempts}): {e}",
                    exc_info=True,
                )
                
                if retry_count < self.retry_max_attempts:
                    # Exponential backoff with maximum cap
                    backoff = min(
                        self.retry_backoff_seconds * (2 ** (retry_count - 1)),
                        60  # Maximum 60 seconds
                    )
                    logger.info(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                else:
                    # Max retries exceeded
                    self.summarization_failures += 1
                    
                    error_type = type(e).__name__
                    error_message = str(e)
                    
                    self._publish_summarization_failed(
                        thread_id=thread_id,
                        error_type=error_type,
                        error_message=error_message,
                        retry_count=retry_count,
                    )
                    
                    if self.error_reporter:
                        self.error_reporter.report(
                            e,
                            context={"thread_id": thread_id, "retry_count": retry_count},
                        )
                    
                    if self.metrics_collector:
                        self.metrics_collector.increment(
                            "summarization_failures_total",
                            tags={"error_type": error_type},
                        )

    def _retrieve_context(self, thread_id: str, top_k: int) -> Dict[str, Any]:
        """Retrieve context for a thread from vector and document stores.
        
        Args:
            thread_id: Thread identifier
            top_k: Number of chunks to retrieve
            
        Returns:
            Dictionary with 'messages' and 'chunks' keys
        """
        # Query messages from document store
        messages = self.document_store.query_documents(
            collection="messages",
            filter_dict={"thread_id": thread_id},
        )
        
        if not messages:
            logger.warning(f"No messages found for thread {thread_id}")
            return {"messages": [], "chunks": []}
        
        # Extract message text for context
        message_texts = []
        for msg in messages:
            body = msg.get("body_normalized", "")
            if body:
                message_texts.append(body)
        
        # Query chunks from vector store (top-k most relevant)
        # For now, we'll use message texts directly
        # In a real implementation, you'd query the vector store with a query embedding
        chunks = []
        for i, msg in enumerate(messages[:top_k]):
            chunks.append({
                "chunk_id": msg.get("message_id", f"chunk_{i}"),
                "message_id": msg.get("message_id", ""),
                "text": msg.get("body_normalized", ""),
                "offset": 0,
            })
        
        return {
            "messages": message_texts[:top_k],
            "chunks": chunks,
        }

    def _format_citations(
        self,
        citations: List[Citation],
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Format citations for output.
        
        Args:
            citations: List of Citation objects
            chunks: List of chunk dictionaries with metadata
            
        Returns:
            List of formatted citation dictionaries
        """
        formatted = []
        
        # Limit to citation_count
        for citation in citations[:self.citation_count]:
            formatted.append({
                "message_id": citation.message_id,
                "chunk_id": citation.chunk_id,
                "offset": citation.offset,
            })
        
        return formatted

    def _publish_summary_complete(
        self,
        thread_id: str,
        summary_markdown: str,
        citations: List[Dict[str, Any]],
        llm_backend: str,
        llm_model: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: int,
    ):
        """Publish SummaryComplete event.
        
        Args:
            thread_id: Thread identifier
            summary_markdown: Generated summary in Markdown
            citations: List of citation dictionaries
            llm_backend: LLM backend used
            llm_model: Model used
            tokens_prompt: Prompt tokens
            tokens_completion: Completion tokens
            latency_ms: Latency in milliseconds
        """
        event = SummaryCompleteEvent(
            data={
                "thread_id": thread_id,
                "summary_markdown": summary_markdown,
                "citations": citations,
                "llm_backend": llm_backend,
                "llm_model": llm_model,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "latency_ms": latency_ms,
            }
        )
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="summary.complete",
            message=event.to_dict(),
        )
        
        logger.info(f"Published SummaryComplete event for thread {thread_id}")

    def _publish_summarization_failed(
        self,
        thread_id: str,
        error_type: str,
        error_message: str,
        retry_count: int,
    ):
        """Publish SummarizationFailed event.
        
        Args:
            thread_id: Thread identifier
            error_type: Type of error
            error_message: Error message
            retry_count: Number of retry attempts
        """
        event = SummarizationFailedEvent(
            data={
                "thread_id": thread_id,
                "error_type": error_type,
                "error_message": error_message,
                "retry_count": retry_count,
            }
        )
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="summarization.failed",
            message=event.to_dict(),
        )
        
        logger.warning(
            f"Published SummarizationFailed event for thread {thread_id}: "
            f"{error_type} - {error_message}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "summaries_generated": self.summaries_generated,
            "summarization_failures": self.summarization_failures,
            "last_processing_time_seconds": self.last_processing_time,
        }
