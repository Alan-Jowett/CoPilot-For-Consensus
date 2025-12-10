# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event publisher implementation."""

import json
import logging
from typing import Dict, Any

from typing import Optional

from .publisher import EventPublisher
from .schema_provider import SchemaProvider
from .file_schema_provider import FileSchemaProvider
from .schema_validator import validate_json

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
        validate_events: bool = True,
        schema_provider: Optional[SchemaProvider] = None,
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
        self.validate_events = validate_events
        self.schema_provider = schema_provider or FileSchemaProvider()
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

        if self.validate_events:
            event_type = event.get("event_type")
            if not event_type:
                logger.error("Event missing 'event_type'; validation failed")
                return False

            schema = self.schema_provider.get_schema(event_type)
            if schema is None:
                logger.error(
                    "No schema found for event_type '%s'; refusing to publish", event_type
                )
                return False

            is_valid, errors = validate_json(event, schema)
            if not is_valid:
                logger.error(
                    "Event validation failed for '%s': %s", event_type, "; ".join(errors)
                )
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
