# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event subscriber implementation."""

import json
import logging
import re
from typing import Callable, Dict, Any

from .subscriber import EventSubscriber


logger = logging.getLogger(__name__)


class RabbitMQSubscriber(EventSubscriber):
    """RabbitMQ implementation of EventSubscriber.
    
    Subscribes to events from a RabbitMQ exchange and dispatches them
    to registered callbacks based on event type.
    """

    def __init__(
        self,
        host: str,
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        exchange_name: str = "copilot.events",
        exchange_type: str = "topic",
        queue_name: str = None,
        queue_durable: bool = True,
        auto_ack: bool = False,
    ):
        """Initialize RabbitMQ subscriber.
        
        Args:
            host: RabbitMQ server hostname
            port: RabbitMQ server port
            username: Authentication username
            password: Authentication password
            exchange_name: Name of the exchange to subscribe to
            exchange_type: Type of exchange (topic, direct, fanout)
            queue_name: Name of the queue (generated if None)
            queue_durable: Whether the queue survives broker restart
            auto_ack: Whether to automatically acknowledge messages
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        self.queue_name = queue_name
        self.queue_durable = queue_durable
        self.auto_ack = auto_ack
        
        self.connection = None
        self.channel = None
        self.callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._consuming = False

    def connect(self) -> bool:
        """Connect to RabbitMQ server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            import pika
            
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type=self.exchange_type,
                durable=True
            )
            
            # Declare queue
            if self.queue_name:
                # Named queue - must be durable with correct persistence flags
                self.channel.queue_declare(
                    queue=self.queue_name,
                    durable=self.queue_durable,
                    auto_delete=False,
                    exclusive=False,
                )
            else:
                # Let RabbitMQ generate a unique queue name (temporary queue)
                result = self.channel.queue_declare(
                    queue='',
                    exclusive=True
                )
                self.queue_name = result.method.queue
            
            logger.info(
                f"Connected to RabbitMQ: {self.host}:{self.port}, "
                f"exchange={self.exchange_name}, queue={self.queue_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from RabbitMQ server."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        routing_key: str = None
    ) -> None:
        """Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when an event is received
            routing_key: Routing key pattern (defaults to event_type in snake_case)
        """
        if not self.channel:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Register callback
        self.callbacks[event_type] = callback
        
        # Determine routing key
        if routing_key is None:
            # Convert event_type to routing key (e.g., "ArchiveIngested" -> "archive.ingested")
            routing_key = self._event_type_to_routing_key(event_type)
        
        # Bind queue to exchange with routing key
        self.channel.queue_bind(
            exchange=self.exchange_name,
            queue=self.queue_name,
            routing_key=routing_key
        )
        
        logger.info(
            f"Subscribed to {event_type} events with routing key: {routing_key}"
        )

    def start_consuming(self) -> None:
        """Start consuming events from the queue."""
        if not self.channel:
            raise RuntimeError("Not connected. Call connect() first.")
        
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self._on_message,
            auto_ack=self.auto_ack
        )
        
        self._consuming = True
        logger.info("Started consuming events")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop_consuming()

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully."""
        if self.channel and self._consuming:
            self.channel.stop_consuming()
            self._consuming = False
            logger.info("Stopped consuming events")

    def _on_message(self, channel, method, properties, body) -> None:
        """Handle incoming message from RabbitMQ.
        
        Args:
            channel: Channel object
            method: Method frame with delivery info
            properties: Message properties
            body: Message body (bytes)
        """
        try:
            # Decode and parse message
            message_str = body.decode('utf-8')
            event = json.loads(message_str)
            
            # Extract event type
            event_type = event.get('event_type')
            
            if not event_type:
                logger.warning("Received event without event_type field")
                if not self.auto_ack:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Find and call registered callback
            callback = self.callbacks.get(event_type)
            
            if callback:
                try:
                    callback(event)
                    logger.debug(f"Processed {event_type} event: {event.get('event_id')}")
                except Exception as e:
                    logger.error(f"Error in callback for {event_type}: {e}")
                    # Don't ack if callback fails (for retry)
                    if not self.auto_ack:
                        channel.basic_nack(
                            delivery_tag=method.delivery_tag,
                            requeue=True
                        )
                    return
            else:
                logger.debug(f"No callback registered for {event_type}")
            
            # Acknowledge message if not auto-ack
            if not self.auto_ack:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode event JSON: {e}")
            # Ack malformed messages so they don't block the queue
            if not self.auto_ack:
                channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if not self.auto_ack:
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=False  # Don't requeue unexpected errors
                )

    def _event_type_to_routing_key(self, event_type: str) -> str:
        """Convert event type to routing key.
        
        Args:
            event_type: Event type in PascalCase (e.g., "ArchiveIngested")
            
        Returns:
            Routing key in dot notation (e.g., "archive.ingested")
        """
        # Handle consecutive uppercase blocks (e.g., JSON) before standard casing
        key = re.sub(r'([A-Z]+)([A-Z][a-z])', r"\1.\2", event_type)
        # Handle remaining transitions from lower/number to upper
        key = re.sub(r'([a-z\d])([A-Z])', r"\1.\2", key)
        return key.lower()
