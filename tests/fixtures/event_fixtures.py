# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test fixtures for creating schema-compliant event messages.

This module provides helper functions to generate valid test data for event
messages that conform to the JSON schemas defined in docs/schemas/events/.

These fixtures ensure that tests use schema-validated events rather than
bypassing validation through mocks or incomplete test data.
"""

import uuid
from datetime import datetime, timezone
from typing import Any


def create_valid_event(
    event_type: str,
    data: dict[str, Any],
    event_id: str | None = None,
    timestamp: str | None = None,
    version: str = "1.0",
    **kwargs: Any
) -> dict[str, Any]:
    """Create a schema-compliant event message for testing.
    
    This function generates a valid event that conforms to the event envelope
    schema. All required fields are provided with sensible defaults.
    
    Args:
        event_type: Type of event (e.g., "ArchiveIngested", "JSONParsed")
        data: Event-specific data payload
        event_id: Unique event identifier (auto-generated UUID if None)
        timestamp: ISO 8601 timestamp (current time if None)
        version: Event schema version (default: "1.0")
        **kwargs: Additional fields to include in the event
        
    Returns:
        Dictionary containing a valid event message
        
    Example:
        >>> event = create_valid_event(
        ...     event_type="ArchiveIngested",
        ...     data={"archive_id": "abc123def4567890"}
        ... )
        >>> assert event["event_type"] == "ArchiveIngested"
        >>> assert "event_id" in event
    """
    if event_id is None:
        # Generate UUID in string format as required by event schema
        event_id = str(uuid.uuid4())
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    event = {
        "event_type": event_type,
        "event_id": event_id,
        "timestamp": timestamp,
        "version": version,
        "data": data,
    }
    
    event.update(kwargs)
    return event


def create_archive_ingested_event(
    archive_id: str = "abc123def4567890",
    source_name: str = "test-source",
    source_type: str = "local",
    source_url: str = "/test/archive.mbox",
    file_path: str = "/test/archive.mbox",
    file_size_bytes: int = 1024,
    file_hash_sha256: str | None = None,
    ingestion_started_at: str | None = None,
    ingestion_completed_at: str | None = None,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid ArchiveIngested event for testing.
    
    Args:
        archive_id: 16-char hex archive identifier
        source_name: Name of the archive source
        source_type: Type of source (rsync, imap, http, local)
        source_url: URL or path to the source
        file_path: Path to the ingested archive file
        file_size_bytes: Size of the file in bytes
        file_hash_sha256: SHA256 hash of the file (auto-generated if None)
        ingestion_started_at: ISO 8601 timestamp (current time if None)
        ingestion_completed_at: ISO 8601 timestamp (current time if None)
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid ArchiveIngested event
    """
    import hashlib
    if file_hash_sha256 is None:
        file_hash_sha256 = hashlib.sha256(file_path.encode()).hexdigest()
    
    now = datetime.now(timezone.utc).isoformat()
    if ingestion_started_at is None:
        ingestion_started_at = now
    if ingestion_completed_at is None:
        ingestion_completed_at = now
    
    data = {
        "archive_id": archive_id,
        "source_name": source_name,
        "source_type": source_type,
        "source_url": source_url,
        "file_path": file_path,
        "file_size_bytes": file_size_bytes,
        "file_hash_sha256": file_hash_sha256,
        "ingestion_started_at": ingestion_started_at,
        "ingestion_completed_at": ingestion_completed_at,
    }
    
    return create_valid_event("ArchiveIngested", data, **kwargs)


def create_json_parsed_event(
    archive_id: str = "abc123def4567890",
    message_count: int = 10,
    thread_count: int = 5,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid JSONParsed event for testing.
    
    Args:
        archive_id: 16-char hex archive identifier
        message_count: Number of messages parsed
        thread_count: Number of threads created
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid JSONParsed event
    """
    data = {
        "archive_id": archive_id,
        "message_count": message_count,
        "thread_count": thread_count,
    }
    
    return create_valid_event("JSONParsed", data, **kwargs)


def create_chunks_prepared_event(
    message_doc_id: str = "fedcba9876543210",
    chunk_ids: list[str] | None = None,
    chunk_count: int = 3,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid ChunksPrepared event for testing.
    
    Args:
        message_doc_id: 16-char hex message document identifier
        chunk_ids: List of chunk IDs (auto-generated if None)
        chunk_count: Number of chunks (used if chunk_ids is None)
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid ChunksPrepared event
    """
    if chunk_ids is None:
        import hashlib
        chunk_ids = [
            hashlib.sha256(f"{message_doc_id}|{i}".encode()).hexdigest()[:16]
            for i in range(chunk_count)
        ]
    
    data = {
        "message_doc_id": message_doc_id,
        "chunk_ids": chunk_ids,
        "chunk_count": len(chunk_ids),
    }
    
    return create_valid_event("ChunksPrepared", data, **kwargs)


def create_embeddings_generated_event(
    chunk_ids: list[str] | None = None,
    embedding_count: int = 5,
    embedding_model: str = "all-MiniLM-L6-v2",
    embedding_backend: str = "sentencetransformers",
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid EmbeddingsGenerated event for testing.
    
    Args:
        chunk_ids: List of chunk IDs (auto-generated if None)
        embedding_count: Number of embeddings (used if chunk_ids is None)
        embedding_model: Name of the embedding model used
        embedding_backend: Backend used for embedding generation
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid EmbeddingsGenerated event
    """
    if chunk_ids is None:
        import hashlib
        chunk_ids = [
            hashlib.sha256(f"chunk-{i}".encode()).hexdigest()[:16]
            for i in range(embedding_count)
        ]
    
    data = {
        "chunk_ids": chunk_ids,
        "embedding_count": len(chunk_ids),
        "embedding_model": embedding_model,
        "embedding_backend": embedding_backend,
    }
    
    return create_valid_event("EmbeddingsGenerated", data, **kwargs)


def create_summary_complete_event(
    thread_id: str = "fedcba9876543210",
    summary_id: str = "summary123456789",
    summary_type: str = "extractive",
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid SummaryComplete event for testing.
    
    Args:
        thread_id: 16-char hex thread identifier
        summary_id: Unique summary identifier
        summary_type: Type of summary (e.g., "extractive", "abstractive")
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid SummaryComplete event
    """
    data = {
        "thread_id": thread_id,
        "summary_id": summary_id,
        "summary_type": summary_type,
    }
    
    return create_valid_event("SummaryComplete", data, **kwargs)


def create_failure_event(
    event_type: str,
    error_message: str,
    context: dict[str, Any] | None = None,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a valid failure event for testing.
    
    Failure events typically have event types ending in "Failed" (e.g.,
    "ParsingFailed", "ChunkingFailed", "EmbeddingGenerationFailed").
    
    Args:
        event_type: Type of failure event
        error_message: Description of the error
        context: Additional context about the failure
        **kwargs: Additional fields for the event
        
    Returns:
        Dictionary containing a valid failure event
    """
    if context is None:
        context = {}
    
    data = {
        "error_message": error_message,
        **context
    }
    
    return create_valid_event(event_type, data, **kwargs)
