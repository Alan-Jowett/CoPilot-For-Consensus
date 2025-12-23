# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Common event models for Copilot-for-Consensus services.

This module defines all event types used in the Copilot-for-Consensus event-driven
architecture. All events inherit from BaseEvent and follow a consistent structure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4


@dataclass
class BaseEvent:
    """Base class for all event types.

    All events follow the event envelope format with common fields.
    Subclasses set event_type to their specific event name.

    Schema: documents/schemas/events/event-envelope.schema.json

    Attributes:
        event_type: Type of event (set by subclass)
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp of event creation
        version: Event schema version
        data: Event-specific payload
    """
    event_type: str
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for event_id and timestamp."""
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.

        Returns:
            Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


# ============================================================================
# Ingestion Service Events
# ============================================================================

@dataclass
class ArchiveIngestedEvent(BaseEvent):
    """Event published when an archive is successfully ingested.

    Schema: documents/schemas/events/ArchiveIngested.schema.json

    Published by: Ingestion Service
    Consumed by: Parsing Service
    Routing Key: archive.ingested

    Data fields:
        archive_id: Unique identifier for the archive
        source_name: Source identifier (e.g., "ietf-quic")
        source_type: Archive source type (e.g., "rsync")
        source_url: URL or path to original archive
        file_path: Storage path for raw archive
        file_size_bytes: Size of archive file in bytes
        file_hash_sha256: SHA256 hash of archive file
        ingestion_started_at: When ingestion began (ISO 8601)
        ingestion_completed_at: When ingestion completed (ISO 8601)
    """
    event_type: str = field(default="ArchiveIngested", init=False)


@dataclass
class ArchiveIngestionFailedEvent(BaseEvent):
    """Event published when archive ingestion fails.

    Schema: documents/schemas/events/ArchiveIngestionFailed.schema.json

    Published by: Ingestion Service
    Routing Key: archive.ingestion.failed

    Data fields:
        source_name: Source identifier
        source_type: Archive source type
        source_url: URL or path attempted
        error_message: Human-readable error description
        error_type: Error classification (e.g., "TimeoutError")
        retry_count: Number of retry attempts made
        ingestion_started_at: When ingestion began (ISO 8601)
        failed_at: When failure occurred (ISO 8601)
    """
    event_type: str = field(default="ArchiveIngestionFailed", init=False)


# ============================================================================
# Parsing Service Events
# ============================================================================


@dataclass
class JSONParsedEvent(BaseEvent):
    """Event published when an archive has been successfully parsed.

    Schema: documents/schemas/events/JSONParsed.schema.json

    Published by: Parsing Service
    Consumed by: Chunking Service, Orchestration Service
    Routing Key: json.parsed

    Data fields:
        archive_id: Archive that was parsed (archives._id)
        message_count: Number of messages parsed
        message_doc_ids: Deterministic message document identifiers (messages._id)
        thread_count: Number of threads identified
        thread_ids: Deterministic thread identifiers (threads._id)
        parsing_duration_seconds: Time taken to parse
    """
    event_type: str = field(default="JSONParsed", init=False)


@dataclass
class ParsingFailedEvent(BaseEvent):
    """Event published when archive parsing fails.

    Schema: documents/schemas/events/ParsingFailed.schema.json

    Published by: Parsing Service
    Routing Key: parsing.failed

    Data fields:
        archive_id: Archive that failed to parse
        file_path: Path to the archive file
        error_message: Human-readable error description
        error_type: Error classification (e.g., "MboxParseError")
        messages_parsed_before_failure: Partial progress count
        retry_count: Number of retry attempts made
        failed_at: When failure occurred (ISO 8601)
    """
    event_type: str = field(default="ParsingFailed", init=False)


# ============================================================================
# Chunking Service Events
# ============================================================================

@dataclass
class ChunksPreparedEvent(BaseEvent):
    """Event published when messages have been chunked.

    Schema: documents/schemas/events/ChunksPrepared.schema.json

    Published by: Chunking Service
    Consumed by: Embedding Service
    Routing Key: chunks.prepared

    Data fields:
        message_doc_ids: Message document identifiers chunked (messages._id)
        chunk_count: Total number of chunks created
        chunk_ids: Deterministic chunk identifiers (chunks._id)
        chunks_ready: Whether chunks are ready for embedding
        chunking_strategy: Strategy used (e.g., "recursive")
        avg_chunk_size_tokens: Average chunk size in tokens
    """
    event_type: str = field(default="ChunksPrepared", init=False)


@dataclass
class ChunkingFailedEvent(BaseEvent):
    """Event published when chunking fails.

    Schema: documents/schemas/events/ChunkingFailed.schema.json

    Published by: Chunking Service
    Routing Key: chunks.failed

    Data fields:
        message_doc_ids: Message document identifiers that failed (messages._id)
        error_message: Human-readable error description
        error_type: Error classification
        retry_count: Number of retry attempts made
        failed_at: When failure occurred (ISO 8601)
    """
    event_type: str = field(default="ChunkingFailed", init=False)


# ============================================================================
# Embedding Service Events
# ============================================================================

@dataclass
class EmbeddingsGeneratedEvent(BaseEvent):
    """Event published when embeddings have been generated.

    Schema: documents/schemas/events/EmbeddingsGenerated.schema.json

    Published by: Embedding Service
    Consumed by: Orchestration Service
    Routing Key: embeddings.generated

    Data fields:
        chunk_ids: Chunk document identifiers embedded (chunks._id)
        embedding_count: Number of embeddings generated
        embedding_model: Model used (e.g., "all-MiniLM-L6-v2")
        embedding_backend: Backend used (e.g., "sentencetransformers")
        embedding_dimension: Dimension of embedding vectors
        vector_store_collection: Collection name in vector store
        vector_store_updated: Whether vector store was updated
        avg_generation_time_ms: Average generation time per embedding
    """
    event_type: str = field(default="EmbeddingsGenerated", init=False)


@dataclass
class EmbeddingGenerationFailedEvent(BaseEvent):
    """Event published when embedding generation fails.

    Schema: documents/schemas/events/EmbeddingGenerationFailed.schema.json

    Published by: Embedding Service
    Routing Key: embeddings.failed

    Data fields:
        chunk_ids: Chunks that failed to be embedded
        error_message: Human-readable error description
        error_type: Error classification (e.g., "TimeoutError")
        embedding_backend: Backend that failed
        retry_count: Number of retry attempts made
        failed_at: When failure occurred (ISO 8601)
    """
    event_type: str = field(default="EmbeddingGenerationFailed", init=False)


# ============================================================================
# Orchestration Service Events
# ============================================================================

@dataclass
class SummarizationRequestedEvent(BaseEvent):
    """Event published when summarization is requested.

    Schema: documents/schemas/events/SummarizationRequested.schema.json

    Published by: Orchestration Service
    Consumed by: Summarization Service
    Routing Key: summarization.requested

    Data fields:
        thread_ids: Thread identifiers to summarize (threads._id)
        top_k: Number of top relevant chunks to retrieve
        llm_backend: LLM backend to use (e.g., "ollama")
        llm_model: Model name (e.g., "mistral")
        context_window_tokens: Maximum context window size
        prompt_template: Prompt template to use
    """
    event_type: str = field(default="SummarizationRequested", init=False)


@dataclass
class OrchestrationFailedEvent(BaseEvent):
    """Event published when orchestration fails.

    Schema: documents/schemas/events/OrchestrationFailed.schema.json

    Published by: Orchestration Service
    Routing Key: orchestration.failed

    Data fields:
        thread_ids: Threads that failed (threads._id)
        error_type: Error classification
        error_message: Human-readable error description
        retry_count: Number of retry attempts made
    """
    event_type: str = field(default="OrchestrationFailed", init=False)


# ============================================================================
# Summarization Service Events
# ============================================================================

@dataclass
class SummaryCompleteEvent(BaseEvent):
    """Event published when a summary has been generated.

    Schema: documents/schemas/events/SummaryComplete.schema.json

    Published by: Summarization Service
    Consumed by: Reporting Service
    Routing Key: summary.complete

    Data fields:
        summary_id: Summary identifier (summaries._id)
        thread_id: Thread that was summarized (threads._id)
        summary_markdown: Generated summary in Markdown format
        citations: List of citation objects with message_id, chunk_id, offset
        llm_backend: LLM backend used
        llm_model: Model used
        tokens_prompt: Number of prompt tokens
        tokens_completion: Number of completion tokens
        latency_ms: Generation latency in milliseconds
    """
    event_type: str = field(default="SummaryComplete", init=False)


@dataclass
class SummarizationFailedEvent(BaseEvent):
    """Event published when summarization fails.

    Schema: documents/schemas/events/SummarizationFailed.schema.json

    Published by: Summarization Service
    Routing Key: summarization.failed

    Data fields:
        thread_id: Thread that failed summarization (threads._id)
        error_type: Error classification (e.g., "LLMTimeout")
        error_message: Human-readable error description
        retry_count: Number of retry attempts made
    """
    event_type: str = field(default="SummarizationFailed", init=False)


# ============================================================================
# Reporting Service Events
# ============================================================================

@dataclass
class ReportPublishedEvent(BaseEvent):
    """Event published when a report is published.

    Schema: documents/schemas/events/ReportPublished.schema.json

    Published by: Reporting Service
    Routing Key: report.published

    Data fields:
        thread_id: Thread the report is for (threads._id)
        report_id: Unique report identifier
        format: Report format (e.g., "markdown")
        notified: Whether notifications were sent
        delivery_channels: List of delivery channels used
        summary_url: API endpoint for the report
    """
    event_type: str = field(default="ReportPublished", init=False)


@dataclass
class ReportDeliveryFailedEvent(BaseEvent):
    """Event published when report delivery fails.

    Schema: documents/schemas/events/ReportDeliveryFailed.schema.json

    Published by: Reporting Service
    Routing Key: report.delivery_failed

    Data fields:
        report_id: Report that failed delivery
        thread_id: Associated thread (threads._id)
        delivery_channel: Channel that failed (e.g., "webhook")
        error_message: Human-readable error description
        error_type: Error classification
        retry_count: Number of retry attempts made
    """
    event_type: str = field(default="ReportDeliveryFailed", init=False)


# ============================================================================
# Data Models (used internally by services)
# ============================================================================

@dataclass
class ArchiveMetadata:
    """Metadata for an archived file during ingestion.

    This is an internal data model used by the Ingestion Service to track
    information about ingested archives.

    Attributes:
        archive_id: Unique identifier for the archive
        source_name: Source identifier (e.g., "ietf-quic")
        source_type: Archive source type (e.g., "rsync")
        source_url: URL or path to original archive
        file_path: Storage path for raw archive
        file_size_bytes: Size of archive file in bytes
        file_hash_sha256: SHA256 hash of archive file
        ingestion_started_at: When ingestion began (ISO 8601)
        ingestion_completed_at: When ingestion completed (ISO 8601)
        status: Status of ingestion ("success" or "failed")
    """
    archive_id: str
    source_name: str
    source_type: str
    source_url: str
    file_path: str
    file_size_bytes: int
    file_hash_sha256: str
    ingestion_started_at: str
    ingestion_completed_at: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary.

        Returns:
            Dictionary representation of metadata
        """
        return {
            "archive_id": self.archive_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "file_hash_sha256": self.file_hash_sha256,
            "ingestion_started_at": self.ingestion_started_at,
            "ingestion_completed_at": self.ingestion_completed_at,
            "status": self.status,
        }
