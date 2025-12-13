# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main embedding service implementation."""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from copilot_events import (
    EventPublisher,
    EventSubscriber,
    ChunksPreparedEvent,
    EmbeddingsGeneratedEvent,
    EmbeddingGenerationFailedEvent,
)
from copilot_storage import DocumentStore
from copilot_vectorstore import VectorStore
from copilot_embedding import EmbeddingProvider
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter
from copilot_service_base import retry_with_backoff, safe_event_handler

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Main embedding service for generating and storing vector embeddings."""

    def __init__(
        self,
        document_store: DocumentStore,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_backend: str = "sentencetransformers",
        embedding_dimension: int = 384,
        batch_size: int = 32,
        max_retries: int = 3,
        retry_backoff_seconds: int = 5,
        vector_store_collection: str = "message_embeddings",
    ):
        """Initialize embedding service.
        
        Args:
            document_store: Document store for retrieving chunks and updating status
            vector_store: Vector store for storing embeddings
            embedding_provider: Provider for generating embeddings
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            metrics_collector: Metrics collector (optional)
            error_reporter: Error reporter (optional)
            embedding_model: Model name/identifier
            embedding_backend: Backend type (sentencetransformers, azure, etc.)
            embedding_dimension: Embedding vector dimension
            batch_size: Batch size for processing chunks
            max_retries: Maximum retry attempts
            retry_backoff_seconds: Base backoff time for retries
            vector_store_collection: Vector store collection name
        """
        self.document_store = document_store
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        self.embedding_model = embedding_model
        self.embedding_backend = embedding_backend
        self.embedding_dimension = embedding_dimension
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.vector_store_collection = vector_store_collection
        
        # Stats
        self.chunks_processed = 0
        self.embeddings_generated_total = 0
        self.last_processing_time = 0.0
        self.service_start_time = time.time()

    def start(self):
        """Start the embedding service and subscribe to events."""
        logger.info("Starting Embedding Service")
        
        # Subscribe to ChunksPrepared events
        self.subscriber.subscribe(
            event_type="ChunksPrepared",
            exchange="copilot.events",
            routing_key="chunks.prepared",
            callback=self._handle_chunks_prepared,
        )
        
        logger.info("Subscribed to chunks.prepared events")
        logger.info("Embedding service is ready")

    @safe_event_handler("ChunksPrepared")
    def _handle_chunks_prepared(self, event: Dict[str, Any]):
        """Handle ChunksPrepared event.
        
        Args:
            event: Event dictionary
        """
        # Parse event
        chunks_prepared = ChunksPreparedEvent(data=event.get("data", {}))
        
        logger.info(f"Received ChunksPrepared event with {len(chunks_prepared.data.get('chunk_ids', []))} chunks")
        
        # Process the chunks
        self.process_chunks(chunks_prepared.data)

    def process_chunks(self, event_data: Dict[str, Any]):
        """Process chunks and generate embeddings.
        
        Args:
            event_data: Data from ChunksPrepared event
        """
        chunk_ids = event_data.get("chunk_ids", [])
        
        if not chunk_ids:
            logger.warning("No chunk IDs in ChunksPrepared event")
            return
        
        start_time = time.time()
        
        def process_with_retry():
            """Inner function for retry logic."""
            logger.info(f"Processing {len(chunk_ids)} chunks")
            
            # Retrieve chunks from database
            chunks = list(self.document_store.query_documents(
                collection="chunks",
                filter_dict={"chunk_id": {"$in": chunk_ids}}
            ))
            
            if not chunks:
                error_msg = f"No chunks found in database for IDs: {chunk_ids}"
                logger.warning(error_msg)
                self._publish_embedding_failed(
                    chunk_ids,
                    error_msg,
                    "ChunkNotFoundError",
                    0,
                )
                return
            
            # Process chunks in batches
            all_generated_count = 0
            processed_chunk_ids = []
            
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]
                batch_start = time.time()
                
                # Generate embeddings for batch
                embeddings = self._generate_batch_embeddings(batch)
                
                # Store embeddings in vector store
                self._store_embeddings(embeddings)
                
                # Update chunk status in document database
                batch_chunk_ids = [chunk["chunk_id"] for chunk in batch]
                self._update_chunk_status(batch_chunk_ids)
                
                all_generated_count += len(embeddings)
                processed_chunk_ids.extend(batch_chunk_ids)
                
                batch_time = time.time() - batch_start
                logger.info(f"Processed batch of {len(batch)} chunks in {batch_time:.2f}s")
            
            # Calculate metrics
            processing_time = time.time() - start_time
            avg_time_ms = (processing_time / all_generated_count * 1000) if all_generated_count > 0 else 0
            
            # Update stats
            self.chunks_processed += len(processed_chunk_ids)
            self.embeddings_generated_total += all_generated_count
            self.last_processing_time = processing_time
            
            # Publish success event
            self._publish_embeddings_generated(
                processed_chunk_ids,
                all_generated_count,
                avg_time_ms,
            )
            
            logger.info(f"Successfully generated {all_generated_count} embeddings in {processing_time:.2f}s")
            
            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment("embedding_chunks_processed_total", all_generated_count)
                self.metrics_collector.observe("embedding_generation_duration_seconds", processing_time)
        
        # Retry logic with callbacks
        def on_retry(error: Exception, attempt: int):
            """Callback for retry attempts."""
            error_type = type(error).__name__
            logger.error(f"Embedding generation failed (attempt {attempt}/{self.max_retries}): {error}", exc_info=True)
        
        def on_failure(error: Exception, attempt: int):
            """Callback when all retries exhausted."""
            error_msg = str(error)
            error_type = type(error).__name__
            
            # Publish failure event
            self._publish_embedding_failed(
                chunk_ids,
                error_msg,
                error_type,
                attempt,
            )
            
            # Report error
            if self.error_reporter:
                self.error_reporter.report(error, context={"chunk_ids": chunk_ids, "retry_count": attempt})
            
            # Record failure metrics
            if self.metrics_collector:
                self.metrics_collector.increment("embedding_failures_total", 1, labels={"error_type": error_type})
        
        try:
            retry_with_backoff(
                process_with_retry,
                max_attempts=self.max_retries,
                backoff_seconds=self.retry_backoff_seconds,
                max_backoff_seconds=60,
                on_retry=on_retry,
                on_failure=on_failure,
            )
        except Exception:
            # Error already handled by on_failure callback
            pass

    def _generate_batch_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for a batch of chunks.
        
        Args:
            chunks: List of chunk documents from database
            
        Returns:
            List of embedding objects with vectors and metadata
        """
        embeddings = []
        
        for chunk in chunks:
            # Extract text content
            text = chunk.get("text", "")
            
            if not text:
                logger.warning(f"Chunk {chunk.get('chunk_id')} has no text, skipping")
                continue
            
            # Generate embedding
            vector = self.embedding_provider.embed(text)
            
            # Create embedding object with metadata
            embedding = {
                "id": chunk["chunk_id"],
                "vector": vector,
                "metadata": {
                    "chunk_id": chunk["chunk_id"],
                    "message_id": chunk.get("message_id", ""),
                    "thread_id": chunk.get("thread_id", ""),
                    "archive_id": chunk.get("archive_id", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "text": text,
                    "sender": chunk.get("metadata", {}).get("sender", ""),
                    "sender_name": chunk.get("metadata", {}).get("sender_name", ""),
                    "date": chunk.get("metadata", {}).get("date", ""),
                    "subject": chunk.get("metadata", {}).get("subject", ""),
                    "draft_mentions": chunk.get("metadata", {}).get("draft_mentions", []),
                    "token_count": chunk.get("token_count", 0),
                    "embedding_model": self.embedding_model,
                    "embedding_backend": self.embedding_backend,
                    "embedding_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            }
            embeddings.append(embedding)
        
        return embeddings

    def _store_embeddings(self, embeddings: List[Dict[str, Any]]):
        """Store embeddings in vector store.
        
        Args:
            embeddings: List of embedding objects with id, vector, and metadata
        """
        if not embeddings:
            return
        
        # Extract data for batch insert
        ids = [emb["id"] for emb in embeddings]
        vectors = [emb["vector"] for emb in embeddings]
        metadatas = [emb["metadata"] for emb in embeddings]
        
        # Store in vector store
        self.vector_store.add_embeddings(ids, vectors, metadatas)
        
        logger.info(f"Stored {len(embeddings)} embeddings in vector store")

    def _update_chunk_status(self, chunk_ids: List[str]):
        """Update chunk embedding status in document database.
        
        Args:
            chunk_ids: List of chunk IDs to update
        """
        for chunk_id in chunk_ids:
            self.document_store.update_document(
                collection="chunks",
                doc_id=chunk_id,
                patch={"embedding_generated": True},
            )
        
        logger.debug(f"Updated {len(chunk_ids)} chunks with embedding_generated=True")

    def _publish_embeddings_generated(
        self, 
        chunk_ids: List[str], 
        embedding_count: int,
        avg_generation_time_ms: float,
    ):
        """Publish EmbeddingsGenerated event.
        
        Args:
            chunk_ids: List of chunk IDs that were embedded
            embedding_count: Number of embeddings generated
            avg_generation_time_ms: Average generation time per embedding
        """
        event = EmbeddingsGeneratedEvent(
            data={
                "chunk_ids": chunk_ids,
                "embedding_count": embedding_count,
                "embedding_model": self.embedding_model,
                "embedding_backend": self.embedding_backend,
                "embedding_dimension": self.embedding_dimension,
                "vector_store_collection": self.vector_store_collection,
                "vector_store_updated": True,
                "avg_generation_time_ms": avg_generation_time_ms,
            }
        )
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="embeddings.generated",
            event=event.to_dict(),
        )
        
        logger.info(f"Published EmbeddingsGenerated event for {len(chunk_ids)} chunks")

    def _publish_embedding_failed(
        self,
        chunk_ids: List[str],
        error_message: str,
        error_type: str,
        retry_count: int,
    ):
        """Publish EmbeddingGenerationFailed event.
        
        Args:
            chunk_ids: List of chunk IDs that failed
            error_message: Error description
            error_type: Error classification
            retry_count: Number of retry attempts made
        """
        event = EmbeddingGenerationFailedEvent(
            data={
                "chunk_ids": chunk_ids,
                "error_message": error_message,
                "error_type": error_type,
                "embedding_backend": self.embedding_backend,
                "retry_count": retry_count,
                "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        
        self.publisher.publish(
            exchange="copilot.events",
            routing_key="embedding.generation.failed",
            event=event.to_dict(),
        )
        
        logger.error(f"Published EmbeddingGenerationFailed event for {len(chunk_ids)} chunks")

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dictionary of service statistics
        """
        uptime = time.time() - self.service_start_time
        
        return {
            "chunks_processed": self.chunks_processed,
            "embeddings_generated_total": self.embeddings_generated_total,
            "last_processing_time_seconds": self.last_processing_time,
            "embedding_model": self.embedding_model,
            "embedding_backend": self.embedding_backend,
            "embedding_dimension": self.embedding_dimension,
            "batch_size": self.batch_size,
            "uptime_seconds": uptime,
        }
