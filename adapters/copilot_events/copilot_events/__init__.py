# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Events Adapter.

A shared library for event publishing and subscribing across microservices
in the Copilot-for-Consensus system.
"""

from typing import Any

__version__ = "0.1.0"

# Import event models from the schema validation module
from copilot_schema_validation import (  # type: ignore[import-not-found]
    # Ingestion Service Events
    ArchiveIngestedEvent,
    ArchiveIngestionFailedEvent,
    # Data Models
    ArchiveMetadata,
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
    SummarizationFailedEvent,
    # Orchestration Service Events
    SummarizationRequestedEvent,
    # Summarization Service Events
    SummaryCompleteEvent,
)

from .azure_config import get_azure_servicebus_kwargs
from .azureservicebuspublisher import AzureServiceBusPublisher
from .azureservicebussubscriber import AzureServiceBusSubscriber
from .noop_publisher import NoopPublisher
from .noop_subscriber import NoopSubscriber
from .publisher import EventPublisher, create_publisher
from .rabbitmq_publisher import RabbitMQPublisher
from .rabbitmq_subscriber import RabbitMQSubscriber
from .subscriber import EventSubscriber
from .validating_publisher import ValidatingEventPublisher, ValidationError
from .validating_subscriber import SubscriberValidationError, ValidatingEventSubscriber


def create_subscriber(
    message_bus_type: str,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    **kwargs: Any
) -> EventSubscriber:
    """Create an event subscriber based on message bus type.

    Args:
        message_bus_type: Type of message bus ("rabbitmq", "azureservicebus", or "noop")
        host: Message bus hostname (required for rabbitmq)
        port: Message bus port (required for rabbitmq)
        username: Authentication username (required for rabbitmq)
        password: Authentication password (required for rabbitmq)
        **kwargs: Additional subscriber-specific arguments
            For RabbitMQ: exchange_name, exchange_type, queue_name, queue_durable, auto_ack
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
        ValueError: If required parameters for the message bus type are not provided
        ValueError: If message_bus_type is unknown
    """
    if message_bus_type == "rabbitmq":
        return RabbitMQSubscriber(
            host=host,
            port=port,
            username=username,
            password=password,
            **kwargs
        )
    elif message_bus_type == "azureservicebus":
        return AzureServiceBusSubscriber(**kwargs)
    elif message_bus_type == "noop":
        return NoopSubscriber()
    else:
        raise ValueError(f"Unknown message bus type: {message_bus_type}")


__all__ = [
    # Version
    "__version__",
    # Azure Service Bus helpers
    "get_azure_servicebus_kwargs",
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
