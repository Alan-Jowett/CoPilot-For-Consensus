# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event publisher implementation."""

import json
import logging
from typing import Dict, Any

from .publisher import EventPublisher

logger = logging.getLogger(__name__)


class RabbitMQPublisher(EventPublisher):
    """RabbitMQ-based event publisher with persistent messages."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        exchange: str = "copilot.events",
        exchange_type: str = "topic",
    ):
        """Initialize RabbitMQ publisher.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            exchange: Default exchange name
            exchange_type: Exchange type (topic, direct, fanout, headers)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.connection = None
        self.channel = None

    def connect(self) -> bool:
        """Connect to RabbitMQ and declare exchange.
        
        Returns:
            True if connection succeeded, False otherwise
        """
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
                exchange=self.exchange,
                exchange_type=self.exchange_type,
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
        """Publish an event to RabbitMQ with message persistence.
        
        Args:
            exchange: Exchange name
            routing_key: Routing key
            event: Event data as dictionary
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.channel:
            logger.error("Not connected to RabbitMQ")
            return False

        try:
            import pika

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make messages persistent
                    content_type="application/json",
                ),
            )
            logger.info(
                f"Published event to {exchange}/{routing_key}: {event.get('event_type')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False
