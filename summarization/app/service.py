# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main summarization service implementation."""

import hashlib
import time
from typing import Any
from string import Formatter

from copilot_message_bus import (
    EventPublisher,
    EventSubscriber,
    SummarizationFailedEvent,
    SummarizationRequestedEvent,
    SummaryCompleteEvent,
)
from copilot_logging import get_logger
from copilot_metrics import MetricsCollector
from copilot_error_reporting import ErrorReporter
from copilot_storage import DocumentStore
from copilot_summarization import Citation, Summarizer, Thread
from copilot_vectorstore import VectorStore

logger = get_logger(__name__)


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
        metrics_collector: MetricsCollector | None = None,
        error_reporter: ErrorReporter | None = None,
        llm_backend: str = "local",
        llm_model: str = "mistral",
        context_window_tokens: int = 4096,
        prompt_template: str = "",
        batch_mode_enabled: bool = False,
        batch_max_threads: int = 50,
        batch_poll_interval_seconds: int = 60,
        batch_timeout_hours: int = 24,
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
            llm_backend: LLM backend name (default: local)
            llm_model: LLM model name (default: mistral)
            context_window_tokens: LLM context window size (default: 4096)
            prompt_template: Prompt template for summarization (default: empty)
            batch_mode_enabled: Enable batch mode for OpenAI/Azure (default: False)
            batch_max_threads: Maximum threads per batch (default: 50)
            batch_poll_interval_seconds: Polling interval for batch status (default: 60)
            batch_timeout_hours: Maximum wait time for batch completion in hours (default: 24)
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
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.context_window_tokens = context_window_tokens
        self.prompt_template = prompt_template
        self.batch_mode_enabled = batch_mode_enabled
        self.batch_max_threads = batch_max_threads
        self.batch_poll_interval_seconds = batch_poll_interval_seconds
        self.batch_timeout_hours = batch_timeout_hours

        # Stats
        self.summaries_generated = 0
        self.summarization_failures = 0
        self.last_processing_time = 0.0

        # Batch processing state
        self._pending_batch_threads: list[tuple[str, int, int, str]] = []  # (thread_id, top_k, context_window_tokens, prompt_template)

    def start(self, enable_startup_requeue: bool = True):
        """Start the summarization service and subscribe to events.

        Args:
            enable_startup_requeue: Whether to requeue incomplete documents on startup (default: True)
        """
        logger.info("Starting Summarization Service")

        # Requeue incomplete threads on startup
        if enable_startup_requeue:
            self._requeue_incomplete_threads()

        # Subscribe to SummarizationRequested events
        self.subscriber.subscribe(
            event_type="SummarizationRequested",
            exchange="copilot.events",
            routing_key="summarization.requested",
            callback=self._handle_summarization_requested,
        )

        logger.info("Subscribed to summarization.requested events")
        logger.info("Summarization service is ready")

    def _requeue_incomplete_threads(self):
        """Requeue threads without summaries on startup for forward progress."""
        try:
            from copilot_startup import StartupRequeue

            logger.info("Scanning for threads without summaries to requeue on startup...")

            requeue = StartupRequeue(
                document_store=self.document_store,
                publisher=self.publisher,
                metrics_collector=self.metrics_collector,
            )

            # Requeue threads that don't have summaries yet
            count = requeue.requeue_incomplete(
                collection="threads",
                query={"summary_id": None},
                event_type="SummarizationRequested",
                routing_key="summarization.requested",
                id_field="thread_id",
                build_event_data=lambda doc: {
                    "thread_ids": [doc.get("thread_id")],
                    "top_k": self.top_k,
                    "llm_backend": self.llm_backend,
                    "llm_model": self.llm_model,
                    "context_window_tokens": self.context_window_tokens,
                    "prompt_template": self.prompt_template,
                },
                limit=500,
            )

            logger.info(f"Startup requeue: {count} threads without summaries requeued")

        except ImportError:
            logger.warning("copilot_startup module not available, skipping startup requeue")
        except Exception as e:
            logger.error(f"Startup requeue failed: {e}", exc_info=True)
            # Don't fail service startup on requeue errors

    def _handle_summarization_requested(self, event: dict[str, Any]):
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

    def process_summarization(self, event_data: dict[str, Any]):
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
        prompt_template = event_data.get("prompt_template", self.prompt_template)

        # Use batch mode if enabled and summarizer supports it (OpenAI/Azure only)
        if self.batch_mode_enabled and len(thread_ids) > 1 and hasattr(self.summarizer, 'create_batch'):
            logger.info(f"Processing {len(thread_ids)} threads in batch mode")
            self._process_threads_batch(
                thread_ids=thread_ids,
                top_k=top_k,
                context_window_tokens=self.context_window_tokens,
                prompt_template=prompt_template,
            )
        else:
            # Process threads individually (original behavior)
            for thread_id in thread_ids:
                self._process_thread(
                    thread_id=thread_id,
                    top_k=top_k,
                    context_window_tokens=self.context_window_tokens,
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

        Generates a summary for the requested thread. The orchestrator service is
        responsible for deciding whether a summary needs to be generated or regenerated.
        This service executes the summarization request without checking for existing
        summaries, allowing the orchestrator to control regeneration policy.

        Args:
            thread_id: Thread identifier
            top_k: Number of chunks to retrieve
            context_window_tokens: Token budget for context
            prompt_template: Prompt template with placeholders to substitute
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

                # Substitute template variables with actual context data
                # The prompt_template contains {email_chunks} which will be replaced with formatted messages
                complete_prompt = self._substitute_prompt_template(
                    prompt_template=prompt_template,
                    thread_id=thread_id,
                    context=context,
                )

                messages = context["messages"]

                # Build thread object with complete prompt
                thread = Thread(
                    thread_id=thread_id,
                    messages=messages,
                    top_k=top_k,
                    context_window_tokens=context_window_tokens,
                    prompt=complete_prompt,
                )

                # Generate summary
                summary = self.summarizer.summarize(thread)

                # Generate citations from chunks (since LLMs can hallucinate, we use actual chunks)
                # Create a citation for each chunk that was used as context
                chunks = context.get("chunks", [])
                citations_from_chunks = [
                    Citation(
                        message_id=chunk.get("message_id", ""),
                        chunk_id=chunk.get("_id", ""),
                        offset=chunk.get("offset", 0),
                    )
                    for chunk in chunks
                ]

                # Format citations
                formatted_citations = self._format_citations(
                    citations_from_chunks,
                    chunks,
                )

                # Generate deterministic summary ID based on thread and chunks
                summary_id = self._generate_summary_id(thread_id, formatted_citations)

                # Calculate duration
                duration = time.time() - start_time
                self.last_processing_time = duration

                # Update stats
                self.summaries_generated += 1

                # Publish success event
                self._publish_summary_complete(
                    summary_id=summary_id,
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
                    # Push metrics to Pushgateway
                    self.metrics_collector.safe_push()

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

                    try:
                        self._publish_summarization_failed(
                            thread_id=thread_id,
                            error_type=error_type,
                            error_message=error_message,
                            retry_count=retry_count,
                        )
                    except Exception as publish_error:
                        # Event publishing failed but summarization definitely failed too
                        # Log both errors to ensure visibility
                        logger.error(
                            f"Failed to publish SummarizationFailed event for {thread_id}",
                            exc_info=True,
                            extra={"original_error": str(e), "publish_error": str(publish_error)}
                        )
                        if self.error_reporter:
                            self.error_reporter.report(publish_error, context={"thread_id": thread_id, "publish_failed": True})
                        # Re-raise the original exception to trigger message requeue
                        raise e from publish_error

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
                        # Push metrics to Pushgateway
                        self.metrics_collector.safe_push()

    def _process_threads_batch(
        self,
        thread_ids: list[str],
        top_k: int,
        context_window_tokens: int,
        prompt_template: str,
    ):
        """Process multiple threads using batch mode.

        This method uses the OpenAI Batch API to process multiple threads
        in a single batch job, which is approximately 50% cheaper than
        interactive mode.

        Args:
            thread_ids: List of thread identifiers
            top_k: Number of chunks to retrieve per thread
            context_window_tokens: Token budget for context
            prompt_template: Prompt template with placeholders to substitute
        """
        from copilot_summarization import Thread

        start_time = time.time()
        logger.info(f"Creating batch job for {len(thread_ids)} threads")

        try:
            # Prepare Thread objects for all threads
            threads = []
            thread_contexts = {}  # Store contexts for later citation generation

            for thread_id in thread_ids:
                # Retrieve context
                context = self._retrieve_context(thread_id, top_k)

                if not context or not context.get("messages"):
                    logger.warning(f"No context retrieved for thread {thread_id}, skipping in batch")
                    self._publish_summarization_failed(
                        thread_id=thread_id,
                        error_type="NoContextError",
                        error_message="No context retrieved from vector/document stores",
                        retry_count=0,
                    )
                    continue

                # Substitute template variables
                complete_prompt = self._substitute_prompt_template(
                    prompt_template=prompt_template,
                    thread_id=thread_id,
                    context=context,
                )

                # Build Thread object
                thread = Thread(
                    thread_id=thread_id,
                    messages=context["messages"],
                    top_k=top_k,
                    context_window_tokens=context_window_tokens,
                    prompt=complete_prompt,
                )
                threads.append(thread)
                thread_contexts[thread_id] = context

            if not threads:
                logger.warning("No valid threads to process in batch")
                return

            # Create batch job
            batch_id = self.summarizer.create_batch(threads)
            logger.info(f"Created batch job {batch_id} for {len(threads)} threads")

            # Poll for completion
            max_wait_seconds = self.batch_timeout_hours * 3600
            elapsed = 0
            while elapsed < max_wait_seconds:
                time.sleep(self.batch_poll_interval_seconds)
                elapsed += self.batch_poll_interval_seconds

                status_info = self.summarizer.get_batch_status(batch_id)
                status = status_info["status"]
                completed = status_info["request_counts"]["completed"]
                total = status_info["request_counts"]["total"]

                logger.info(f"Batch {batch_id} status: {status}, completed: {completed}/{total}")

                if status == "completed":
                    break
                elif status in ["failed", "expired", "cancelled"]:
                    raise RuntimeError(f"Batch job {batch_id} ended with status: {status}")

            if status != "completed":
                raise RuntimeError(f"Batch job {batch_id} did not complete within {max_wait_seconds}s")

            # Retrieve results
            summaries = self.summarizer.retrieve_batch_results(batch_id)

            # Process and publish each summary
            for summary in summaries:
                thread_id = summary.thread_id
                context = thread_contexts.get(thread_id)

                if not context:
                    logger.error(f"No context found for thread {thread_id} in batch results")
                    continue

                # Generate citations from chunks
                chunks = context.get("chunks", [])
                citations_from_chunks = [
                    Citation(
                        message_id=chunk.get("message_id", ""),
                        chunk_id=chunk.get("_id", ""),
                        offset=chunk.get("offset", 0),
                    )
                    for chunk in chunks
                ]

                # Format citations
                formatted_citations = self._format_citations(
                    citations_from_chunks,
                    chunks,
                )

                # Generate deterministic summary ID
                summary_id = self._generate_summary_id(thread_id, formatted_citations)

                # Update stats
                self.summaries_generated += 1

                # Publish success event
                self._publish_summary_complete(
                    summary_id=summary_id,
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
                    f"Successfully summarized thread {thread_id} in batch "
                    f"(tokens: {summary.tokens_prompt}+{summary.tokens_completion})"
                )

                # Collect metrics
                if self.metrics_collector:
                    self.metrics_collector.increment(
                        "summarization_events_total",
                        tags={"event_type": "requested", "outcome": "success", "mode": "batch"},
                    )
                    self.metrics_collector.increment(
                        "summarization_llm_calls_total",
                        tags={"backend": summary.llm_backend, "model": summary.llm_model, "mode": "batch"},
                    )
                    self.metrics_collector.increment(
                        "summarization_tokens_total",
                        summary.tokens_prompt,
                        tags={"type": "prompt", "mode": "batch"},
                    )
                    self.metrics_collector.increment(
                        "summarization_tokens_total",
                        summary.tokens_completion,
                        tags={"type": "completion", "mode": "batch"},
                    )

            # Calculate total duration
            duration = time.time() - start_time
            self.last_processing_time = duration

            if self.metrics_collector:
                self.metrics_collector.observe(
                    "summarization_batch_latency_seconds",
                    duration,
                )
                self.metrics_collector.safe_push()

            logger.info(f"Batch job {batch_id} completed successfully in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)

            # Publish failure events for all threads
            for thread_id in thread_ids:
                try:
                    self._publish_summarization_failed(
                        thread_id=thread_id,
                        error_type=type(e).__name__,
                        error_message=f"Batch processing failed: {str(e)}",
                        retry_count=0,
                    )
                except Exception as publish_error:
                    logger.error(f"Failed to publish batch failure for {thread_id}: {publish_error}")

            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_ids": thread_ids, "mode": "batch"})

            if self.metrics_collector:
                self.metrics_collector.increment(
                    "summarization_failures_total",
                    tags={"error_type": type(e).__name__, "mode": "batch"},
                )
                self.metrics_collector.safe_push()

            # Re-raise to trigger message requeue
            raise

    def _substitute_prompt_template(self, prompt_template: str, thread_id: str, context: dict[str, Any]) -> str:
        """Substitute placeholder variables in prompt template with actual context data.

        Replaces template placeholders with values from the thread context:
        - {thread_id}: Thread identifier
        - {message_count}: Number of messages in context
        - {date_range}: Date range of messages (if available)
        - {participants}: List of message participants/senders
        - {draft_mentions}: Referenced RFCs/draft identifiers
        - {email_chunks}: Message text excerpts

        Args:
            prompt_template: Template string with placeholders
            thread_id: Thread identifier
            context: Retrieved context with messages and metadata

        Returns:
            Prompt string with placeholders substituted with actual values
        """
        messages = context.get("messages", [])
        chunks = context.get("chunks", [])

        # Extract message count
        message_count = len(messages)

        # Extract participants (senders) from chunks if available
        participants = set()
        for chunk in chunks:
            sender = chunk.get("from", {})
            if isinstance(sender, dict) and sender.get("email"):
                participants.add(f"{sender.get('name', sender.get('email'))} <{sender.get('email')}>")
            elif isinstance(sender, str):
                participants.add(sender)
        participants_str = ", ".join(sorted(participants)) if participants else "Multiple participants"

        # Extract draft mentions from chunks if available
        draft_mentions = set()
        for chunk in chunks:
            mentions = chunk.get("draft_mentions", [])
            if isinstance(mentions, list):
                draft_mentions.update(mentions)
        draft_mentions_str = "\n".join(sorted(draft_mentions)) if draft_mentions else "No specific drafts mentioned"

        # Extract date range from chunks if available
        dates = []
        for chunk in chunks:
            date = chunk.get("date")
            if date:
                dates.append(date)
        if dates:
            # Dates are expected in ISO 8601; string sort preserves chronological order
            dates.sort()
            date_range = f"{dates[0]} to {dates[-1]}"
        else:
            date_range = "Unknown"

        # Format email chunks (all available messages, respecting natural chunking)
        email_chunks_text = "\n\n".join(
            f"Message {i+1}:\n{msg}" for i, msg in enumerate(messages)
        )
        if not email_chunks_text:
            email_chunks_text = "(No messages available)"

        # Substitute placeholders with error handling for template mismatches
        allowed_placeholders = {
            "thread_id",
            "message_count",
            "date_range",
            "participants",
            "draft_mentions",
            "email_chunks",
        }

        # Validate template placeholders before formatting to surface clear errors
        parsed_placeholders = {
            field_name
            for _, field_name, _, _ in Formatter().parse(prompt_template)
            if field_name
        }
        unexpected = parsed_placeholders - allowed_placeholders
        if unexpected:
            error_msg = (
                f"Prompt template contains unexpected placeholders: {sorted(unexpected)}. "
                f"Expected placeholders: {', '.join(sorted(allowed_placeholders))}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Placeholders are validated above; format should not raise KeyError here
        substituted = prompt_template.format(
            thread_id=thread_id,
            message_count=message_count,
            date_range=date_range,
            participants=participants_str,
            draft_mentions=draft_mentions_str,
            email_chunks=email_chunks_text,
        )

        logger.debug(f"Substituted prompt template for thread {thread_id}")
        return substituted

    def _retrieve_context(self, thread_id: str, top_k: int) -> dict[str, Any]:
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
                "_id": msg.get("_id", msg.get("message_id", f"chunk_{i}")),
                "message_id": msg.get("message_id", ""),
                "text": msg.get("body_normalized", ""),
                "offset": 0,
                # Include metadata for template substitution
                "from": msg.get("from", {}),
                "date": msg.get("date", ""),
                "draft_mentions": msg.get("draft_mentions", []),
            })

        return {
            "messages": message_texts[:top_k],
            "chunks": chunks,
        }

    def _format_citations(
        self,
        citations: list[Citation],
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format citations for output.

        Args:
            citations: List of Citation objects
            chunks: List of chunk dictionaries with metadata

        Returns:
            List of formatted citation dictionaries
        """
        # Create a lookup map for chunks by _id, skipping invalid IDs
        chunk_map = {
            chunk["_id"]: chunk
            for chunk in chunks
            if chunk.get("_id") is not None
        }

        formatted: list[dict[str, Any]] = []

        # Limit to citation_count
        for citation in citations[:self.citation_count]:
            chunk = chunk_map.get(citation.chunk_id)
            
            # Always include the citation, even if chunk is missing
            # If chunk exists, use its _id and text; otherwise use empty text
            chunk_id = chunk.get("_id") if chunk else citation.chunk_id
            text = chunk.get("text", "") if chunk else ""

            formatted.append({
                "message_id": citation.message_id,
                "chunk_id": chunk_id,
                "offset": citation.offset,
                "text": text,
            })

        return formatted

    def _generate_summary_id(self, thread_id: str, citations: list[dict[str, Any]]) -> str:
        """Generate deterministic summary ID from thread and chunk IDs.

        Creates a SHA256 hash of the thread_id combined with sorted chunk_ids
        from citations. This ensures:
        - Same thread + same chunks = same summary_id (deduplication)
        - Different chunks = different summary_id (allows regeneration)

        Args:
            thread_id: Thread identifier
            citations: List of citation dictionaries containing chunk_id

        Returns:
            Hex string of SHA256 hash (64 characters)
        """
        # Extract and sort chunk IDs to ensure consistent ordering, ignoring missing/empty IDs
        chunk_id_set: set[str] = set()
        for citation in citations:
            chunk_id_value = citation.get("chunk_id")
            if isinstance(chunk_id_value, str) and chunk_id_value:
                chunk_id_set.add(chunk_id_value)
        chunk_ids = sorted(chunk_id_set)

        # Combine thread_id and canonical _ids into a single string
        id_input = f"{thread_id}:{','.join(chunk_ids)}"

        # Generate SHA256 hash
        hash_obj = hashlib.sha256(id_input.encode("utf-8"))
        return hash_obj.hexdigest()

    def _publish_summary_complete(
        self,
        summary_id: str,
        thread_id: str,
        summary_markdown: str,
        citations: list[dict[str, Any]],
        llm_backend: str,
        llm_model: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: int,
    ):
        """Publish SummaryComplete event.

        Args:
            summary_id: Deterministic summary identifier
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
                "summary_id": summary_id,
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

        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="summary.complete",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Exception while publishing SummaryComplete event for {thread_id}")
            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_id": thread_id})
            raise

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

        try:
            self.publisher.publish(
                exchange="copilot.events",
                routing_key="summarization.failed",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Exception while publishing SummarizationFailed event for {thread_id}")
            if self.error_reporter:
                self.error_reporter.report(e, context={"thread_id": thread_id, "error_type": error_type})
            raise

        logger.warning(
            f"Published SummarizationFailed event for thread {thread_id}: "
            f"{error_type} - {error_message}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "summaries_generated": self.summaries_generated,
            "summarization_failures": self.summarization_failures,
            "last_processing_time_seconds": self.last_processing_time,
        }
