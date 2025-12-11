# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event publisher implementation."""

import json
import logging
from typing import Dict, Any, List, Optional

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
        enable_publisher_confirms: bool = True,
    ):
        """Initialize RabbitMQ publisher.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            exchange: Default exchange name
            exchange_type: Exchange type (topic, direct, fanout, headers)
            enable_publisher_confirms: Enable publisher confirms for guaranteed delivery
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.enable_publisher_confirms = enable_publisher_confirms
        self.connection = None
        self.channel = None
        self._declared_queues = set()

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

            # Enable publisher confirms for guaranteed delivery
            if self.enable_publisher_confirms:
                self.channel.confirm_delivery()
                logger.info("Publisher confirms enabled")

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

    def declare_queue(
        self,
        queue_name: str,
        routing_key: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> bool:
        """Declare a durable queue and bind it to an exchange.
        
        This ensures the queue exists before publishing messages to it.
        Per RabbitMQ guidance, queues must be created before messages are sent.
        
        Args:
            queue_name: Name of the queue to declare
            routing_key: Routing key to bind (defaults to queue_name)
            exchange: Exchange to bind to (defaults to self.exchange)
            
        Returns:
            True if queue declared successfully, False otherwise
        """
        if not self.channel:
            logger.error("Not connected to RabbitMQ")
            return False

        try:
            # Use provided values or defaults
            routing_key = routing_key or queue_name
            exchange = exchange or self.exchange

            # Declare queue as durable with proper flags
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                auto_delete=False,
                exclusive=False,
            )

            # Bind queue to exchange
            self.channel.queue_bind(
                exchange=exchange,
                queue=queue_name,
                routing_key=routing_key,
            )

            self._declared_queues.add(queue_name)
            logger.info(
                f"Declared durable queue '{queue_name}' and bound to "
                f"{exchange}/{routing_key}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to declare queue '{queue_name}': {e}")
            return False

    def declare_queues(self, queues: List[Dict[str, str]]) -> bool:
        """Declare multiple queues at once.
        
        Args:
            queues: List of queue configurations, each with:
                - queue_name: Name of the queue
                - routing_key: Routing key (optional)
                - exchange: Exchange name (optional)
                
        Returns:
            True if all queues declared successfully, False otherwise
        """
        success = True
        for queue_config in queues:
            queue_name = queue_config.get("queue_name")
            if not queue_name:
                logger.error("Queue configuration missing 'queue_name'")
                success = False
                continue

            result = self.declare_queue(
                queue_name=queue_name,
                routing_key=queue_config.get("routing_key"),
                exchange=queue_config.get("exchange"),
            )
            if not result:
                success = False

        return success

    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> bool:
        """Publish an event to RabbitMQ with message persistence.
        
        Messages are published with:
        - delivery_mode=2 for persistence
        - mandatory=True to detect unroutable messages
        - Publisher confirms (if enabled) for guaranteed delivery
        
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

            # Publish with persistence and mandatory flag
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make messages persistent
                    content_type="application/json",
                ),
                mandatory=True,  # Return unroutable messages
            )
            
            logger.info(
                f"Published event to {exchange}/{routing_key}: {event.get('event_type')}"
            )
            return True
        except Exception as e:
            # Handle pika-specific exceptions if pika is available
            error_type = type(e).__name__
            
            if "UnroutableError" in error_type:
                logger.error(
                    f"Message unroutable - no queue bound for {exchange}/{routing_key}. "
                    "Ensure queues are declared before publishing."
                )
            elif "NackError" in error_type:
                logger.error(
                    f"Message rejected (NACK) by broker for {exchange}/{routing_key}"
                )
            else:
                logger.error(f"Failed to publish event: {e}")
            
            return False
