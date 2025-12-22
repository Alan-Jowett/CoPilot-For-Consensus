# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Events Adapter.

A shared library for event publishing and subscribing across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .publisher import EventPublisher, create_publisher
from .rabbitmq_publisher import RabbitMQPublisher
from .azureservicebuspublisher import AzureServiceBusPublisher
from .noop_publisher import NoopPublisher
from .subscriber import EventSubscriber
from .rabbitmq_subscriber import RabbitMQSubscriber
from .azureservicebussubscriber import AzureServiceBusSubscriber
from .noop_subscriber import NoopSubscriber
from .validating_publisher import ValidatingEventPublisher, ValidationError
from .validating_subscriber import ValidatingEventSubscriber, SubscriberValidationError
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
        message_bus_type: Type of message bus ("rabbitmq", "azureservicebus", or "noop")
        host: Message bus hostname (required for rabbitmq)
        port: Message bus port (optional for rabbitmq)
        username: Authentication username (optional for rabbitmq)
        password: Authentication password (optional for rabbitmq)
        **kwargs: Additional subscriber-specific arguments
            For Azure Service Bus:
                - connection_string: Azure Service Bus connection string
                - fully_qualified_namespace: Namespace hostname (for managed identity)
                - queue_name: Queue name to receive from
                - topic_name: Topic name (for topic/subscription messaging)
                - subscription_name: Subscription name (required if topic_name is provided)
                - use_managed_identity: Use Azure managed identity (default: False)
                - auto_complete: Auto-complete messages (default: False)
                - max_wait_time: Max wait time for messages in seconds (default: 5)
        
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
    elif message_bus_type == "azureservicebus":
        from .azureservicebussubscriber import AzureServiceBusSubscriber
        return AzureServiceBusSubscriber(**kwargs)
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
    "AzureServiceBusPublisher",
    "NoopPublisher",
    "create_publisher",
    "ValidatingEventPublisher",
    "ValidationError",
    # Subscribers
    "EventSubscriber",
    "RabbitMQSubscriber",
    "AzureServiceBusSubscriber",
    "NoopSubscriber",
    "create_subscriber",
    "ValidatingEventSubscriber",
    "SubscriberValidationError",
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
]
