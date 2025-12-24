# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract event publisher interface."""

from abc import ABC, abstractmethod
from typing import Any


class EventPublisher(ABC):
    """Abstract base class for event publishers."""

    @abstractmethod
    def publish(self, exchange: str, routing_key: str, event: dict[str, Any]) -> None:
        """Publish an event to the message bus.

        Args:
            exchange: Exchange name (e.g., "copilot.events")
            routing_key: Routing key (e.g., "archive.ingested")
            event: Event data as dictionary

        Raises:
            Exception: If publishing fails for any reason
        """
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the message bus.

        Raises:
            Exception: If connection fails for any reason
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass


def create_publisher(
    message_bus_type: str = "rabbitmq",
    host: str = "localhost",
    port: int = 5672,
    username: str = "guest",
    password: str = "guest",
    **kwargs: Any
) -> EventPublisher:
    """Factory function to create an event publisher.

    Args:
        message_bus_type: Type of message bus ("rabbitmq", "azureservicebus", or "noop")
        host: Message bus host (for RabbitMQ)
        port: Message bus port (for RabbitMQ)
        username: Message bus username (for RabbitMQ)
        password: Message bus password (for RabbitMQ)
        **kwargs: Additional publisher-specific arguments
            For Azure Service Bus:
                - connection_string: Azure Service Bus connection string
                - fully_qualified_namespace: Namespace hostname (for managed identity)
                - queue_name: Default queue name
                - topic_name: Default topic name
                - use_managed_identity: Use Azure managed identity (default: False)

    Returns:
        EventPublisher instance

    Raises:
        ValueError: If message_bus_type is not recognized
    """
    if message_bus_type == "rabbitmq":
        from .rabbitmq_publisher import RabbitMQPublisher
        return RabbitMQPublisher(
            host=host,
            port=port,
            username=username,
            password=password,
        )
    elif message_bus_type == "azureservicebus":
        from .azureservicebuspublisher import AzureServiceBusPublisher
        return AzureServiceBusPublisher(**kwargs)
    elif message_bus_type == "noop":
        from .noop_publisher import NoopPublisher
        return NoopPublisher()
    else:
        raise ValueError(f"Unknown message_bus_type: {message_bus_type}")
