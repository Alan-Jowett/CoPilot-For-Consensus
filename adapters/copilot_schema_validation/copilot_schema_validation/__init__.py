# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Schema Validation Adapter.

A shared library for JSON schema validation and event models across microservices 
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .schema_provider import SchemaProvider
from .file_schema_provider import FileSchemaProvider
from .schema_validator import validate_json
from .identifier_generator import (
    generate_archive_id_from_bytes,
    generate_message_doc_id,
    generate_chunk_id,
    generate_thread_id,
    generate_summary_id,
)
from .models import (
    BaseEvent,
    # Ingestion Service Events
    ArchiveIngestedEvent,
    ArchiveIngestionFailedEvent,
    # Parsing Service Events
    JSONParsedEvent,
    ParsingFailedEvent,
    # Chunking Service Events
    ChunksPreparedEvent,
    ChunkingFailedEvent,
    # Embedding Service Events
    EmbeddingsGeneratedEvent,
    EmbeddingGenerationFailedEvent,
    # Orchestration Service Events
    SummarizationRequestedEvent,
    OrchestrationFailedEvent,
    # Summarization Service Events
    SummaryCompleteEvent,
    SummarizationFailedEvent,
    # Reporting Service Events
    ReportPublishedEvent,
    ReportDeliveryFailedEvent,
    # Data Models
    ArchiveMetadata,
)

__all__ = [
    # Schema validation
    "SchemaProvider",
    "FileSchemaProvider",
    "validate_json",
    # Event models
    "BaseEvent",
    "ArchiveIngestedEvent",
    "ArchiveIngestionFailedEvent",
    "JSONParsedEvent",
    "ParsingFailedEvent",
    "ChunksPreparedEvent",
    "ChunkingFailedEvent",
    "EmbeddingsGeneratedEvent",
    "EmbeddingGenerationFailedEvent",
    "SummarizationRequestedEvent",
    "OrchestrationFailedEvent",
    "SummaryCompleteEvent",
    "SummarizationFailedEvent",
    "ReportPublishedEvent",
    "ReportDeliveryFailedEvent",
    "ArchiveMetadata",
    # Identifier generators
    "generate_archive_id_from_bytes",
    "generate_message_doc_id",
    "generate_chunk_id",
    "generate_thread_id",
    "generate_summary_id",
]
