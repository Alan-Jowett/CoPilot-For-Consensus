# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Schema Validation Adapter.

A shared library for JSON schema validation and event models across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .file_schema_provider import create_schema_provider
from .identifier_generator import (
    generate_archive_id_from_bytes,
    generate_chunk_id,
    generate_message_doc_id,
    generate_summary_id,
)
from .models import (
    # Ingestion Service Events
    ArchiveIngestedEvent,
    ArchiveIngestionFailedEvent,
    # Data Models
    ArchiveMetadata,
    BaseEvent,
    ChunkingFailedEvent,
    # Chunking Service Events
    ChunksPreparedEvent,
    # Enums
    DocumentStatus,
    EmbeddingGenerationFailedEvent,
    # Embedding Service Events
    EmbeddingsGeneratedEvent,
    # Parsing Service Events
    JSONParsedEvent,
    OrchestrationFailedEvent,
    ParsingFailedEvent,
    ReportDeliveryFailedEvent,
    # Reporting Service Events
    ReportPublishedEvent,
    SummarizationFailedEvent,
    # Orchestration Service Events
    SummarizationRequestedEvent,
    # Summarization Service Events
    SummaryCompleteEvent,
)
from .schema_provider import SchemaProvider
from .schema_registry import (
    SCHEMA_REGISTRY,
    get_configuration_schema_response,
    get_schema_metadata,
    get_schema_path,
    list_schemas,
    load_schema,
    validate_registry,
)
from .schema_validator import validate_json

__all__ = [
    # Schema validation
    "SchemaProvider",
    "create_schema_provider",
    "validate_json",
    # Schema registry
    "get_schema_path",
    "load_schema",
    "list_schemas",
    "validate_registry",
    "get_schema_metadata",
    "get_configuration_schema_response",
    "SCHEMA_REGISTRY",
    # Enums
    "DocumentStatus",
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
    "generate_summary_id",
]
