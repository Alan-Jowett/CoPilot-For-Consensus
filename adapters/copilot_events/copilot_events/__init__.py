# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Events SDK.

A shared library for event publishing and subscribing across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .publisher import EventPublisher, create_publisher
from .rabbitmq_publisher import RabbitMQPublisher
from .noop_publisher import NoopPublisher
from .subscriber import EventSubscriber
from .rabbitmq_subscriber import RabbitMQSubscriber
from .noop_subscriber import NoopSubscriber
# Import event models from the schema validation module
from copilot_schema_validation import (
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
from .thread import Thread, Message
from .consensus import (
    ConsensusDetector,
    ConsensusSignal,
    ConsensusLevel,
    HeuristicConsensusDetector,
    MockConsensusDetector,
    MLConsensusDetector,
    create_consensus_detector,
)

def create_subscriber(
    message_bus_type: str,
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
    **kwargs
) -> EventSubscriber:
    """Create an event subscriber based on message bus type.
    
    Args:
        message_bus_type: Type of message bus ("rabbitmq", "noop")
        host: Message bus hostname (required for rabbitmq)
        port: Message bus port (optional)
        username: Authentication username (optional)
        password: Authentication password (optional)
        **kwargs: Additional subscriber-specific arguments
        
    Returns:
        EventSubscriber instance
        
    Raises:
        ValueError: If message_bus_type is unknown
    """
    if message_bus_type == "rabbitmq":
        if not host:
            raise ValueError("host is required for rabbitmq subscriber")
        return RabbitMQSubscriber(
            host=host,
            port=port or 5672,
            username=username or "guest",
            password=password or "guest",
            **kwargs
        )
    elif message_bus_type == "noop":
        return NoopSubscriber()
    else:
        raise ValueError(f"Unknown message bus type: {message_bus_type}")


__all__ = [
    # Version
    "__version__",
    # Publishers
    "EventPublisher",
    "RabbitMQPublisher",
    "NoopPublisher",
    "create_publisher",
    # Subscribers
    "EventSubscriber",
    "RabbitMQSubscriber",
    "NoopSubscriber",
    "create_subscriber",
    # Event Models
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
    # Thread Models
    "Thread",
    "Message",
    # Consensus Detection
    "ConsensusDetector",
    "ConsensusSignal",
    "ConsensusLevel",
    "HeuristicConsensusDetector",
    "MockConsensusDetector",
    "MLConsensusDetector",
    "create_consensus_detector",
]
