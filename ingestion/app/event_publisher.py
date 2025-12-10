# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class EventPublisher(ABC):
    """Abstract base class for event publishers."""

    @abstractmethod
    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> bool:
        """Publish an event to the message bus.
        
        Args:
            exchange: Exchange name (e.g., "copilot.events")
            routing_key: Routing key (e.g., "archive.ingested")
            event: Event data as dictionary
            
        Returns:
            True if published successfully, False otherwise
        """
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the message bus."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass


class RabbitMQPublisher(EventPublisher):
    """RabbitMQ-based event publisher."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
    ):
        """Initialize RabbitMQ publisher.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
        self.channel = None

    def connect(self) -> bool:
        """Connect to RabbitMQ."""
        try:
            import pika

            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=3,
                retry_delay=2,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchange
            self.channel.exchange_declare(
                exchange="copilot.events",
                exchange_type="topic",
                durable=True,
            )

            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")

    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> bool:
        """Publish an event to RabbitMQ."""
        if not self.channel:
            logger.error("Not connected to RabbitMQ")
            return False

        try:
            import pika

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            logger.info(
                f"Published event to {exchange}/{routing_key}: {event.get('event_type')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False


class NoopPublisher(EventPublisher):
    """No-op publisher for testing."""

    def __init__(self):
        """Initialize no-op publisher."""
        self.published_events: list = []

    def connect(self) -> bool:
        """Pretend to connect."""
        logger.debug("NoopPublisher: connected")
        return True

    def disconnect(self) -> None:
        """Pretend to disconnect."""
        logger.debug("NoopPublisher: disconnected")

    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> bool:
        """Store event without publishing."""
        self.published_events.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "event": event,
            }
        )
        logger.debug(
            f"NoopPublisher: published {event.get('event_type')} to {exchange}/{routing_key}"
        )
        return True


def create_publisher(
    message_bus_type: str = "rabbitmq",
    host: str = "localhost",
    port: int = 5672,
    username: str = "guest",
    password: str = "guest",
) -> EventPublisher:
    """Factory function to create an event publisher.
    
    Args:
        message_bus_type: Type of message bus ("rabbitmq" or "noop")
        host: Message bus host
        port: Message bus port
        username: Message bus username
        password: Message bus password
        
    Returns:
        EventPublisher instance
    """
    if message_bus_type == "rabbitmq":
        return RabbitMQPublisher(host=host, port=port, username=username, password=password)
    elif message_bus_type == "noop":
        return NoopPublisher()
    else:
        raise ValueError(f"Unknown message bus type: {message_bus_type}")
