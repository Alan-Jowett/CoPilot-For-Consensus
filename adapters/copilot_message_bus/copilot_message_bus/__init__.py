# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Message Bus Adapter.

A shared library for message bus publishing and subscribing across microservices
in the Copilot-for-Consensus system. Provides abstractions for RabbitMQ and
Azure Service Bus backends.
"""

from typing import Any

__version__ = "0.1.0"

# Import event models from the schema validation module
from copilot_schema_validation import (  # type: ignore[import-not-found]
    # Ingestion Service Events
    ArchiveIngestedEvent,
    ArchiveIngestionFailedEvent,
    # Data Models
    BaseEvent,
    ChunkingFailedEvent,
    # Chunking Service Events
    ChunksPreparedEvent,
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
    # Source Cascade Cleanup Events
    SourceCleanupCompletedEvent,
    SourceCleanupProgressEvent,
    SourceDeletionRequestedEvent,
    SummarizationFailedEvent,
    # Orchestration Service Events
    SummarizationRequestedEvent,
    # Summarization Service Events
    SummaryCompleteEvent,
)

from .base import EventPublisher, EventSubscriber
from .factory import create_publisher, create_subscriber

# Import validation exceptions (needed for error handling)
from .validating_publisher import ValidationError
from .validating_subscriber import SubscriberValidationError

__all__ = [
    # Version
    "__version__",
    # Factories (primary public API - use these)
    "create_publisher",
    "create_subscriber",
    # Base interfaces (for type hints)
    "EventPublisher",
    "EventSubscriber",
    # Validation exceptions (for error handling)
    "ValidationError",
    "SubscriberValidationError",
    # Event Models (re-exported from schema validation)
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
    "SourceDeletionRequestedEvent",
    "SourceCleanupProgressEvent",
    "SourceCleanupCompletedEvent",
]
