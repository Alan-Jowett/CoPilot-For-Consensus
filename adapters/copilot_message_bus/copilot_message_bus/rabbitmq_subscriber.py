# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event subscriber implementation."""

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_Rabbitmq

from .base import EventSubscriber

logger = logging.getLogger(__name__)


class RabbitMQSubscriber(EventSubscriber):
    """RabbitMQ implementation of EventSubscriber.

    Subscribes to events from a RabbitMQ exchange and dispatches them
    to registered callbacks based on event type.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        exchange_name: str = "copilot.events",
        exchange_type: str = "topic",
        queue_name: str | None = None,
        queue_durable: bool = True,
        auto_ack: bool = False,
    ):
        """Initialize RabbitMQ subscriber.

        Args:
            host: RabbitMQ server hostname (required)
            port: RabbitMQ server port (required)
            username: Authentication username (required)
            password: Authentication password (required)
            exchange_name: Name of the exchange to subscribe to
            exchange_type: Type of exchange (topic, direct, fanout)
            queue_name: Name of the queue (generated if None)
            queue_durable: Whether the queue survives broker restart
            auto_ack: Whether to automatically acknowledge messages

        Raises:
            ValueError: For invalid initialization parameters
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

        self.connection: Any = None  # pika.BlockingConnection after connect()
        self.channel: Any = None  # pika.channel.Channel after connect()
        self.callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._consuming = False

    @classmethod
    def from_config(cls, driver_config: DriverConfig_MessageBus_Rabbitmq) -> "RabbitMQSubscriber":
        """Create subscriber from DriverConfig.

        Args:
            driver_config: DriverConfig instance with configuration fields:
                          - rabbitmq_host: RabbitMQ host
                          - rabbitmq_port: RabbitMQ port
                          - rabbitmq_username: RabbitMQ username
                          - rabbitmq_password: RabbitMQ password
                          - exchange_name: Exchange name (optional)
                          - exchange_type: Exchange type (optional)
                          - queue_name: Queue name (optional)
                          - queue_durable: Queue durable flag (optional)
                          - auto_ack: Auto-ack messages (optional)

        Returns:
            RabbitMQSubscriber instance

        Raises:
            ValueError: If required parameters are missing
        """
        # Get configuration values from driver_config attributes
        host = driver_config.rabbitmq_host
        port = driver_config.rabbitmq_port
        username = driver_config.rabbitmq_username
        password = driver_config.rabbitmq_password
        exchange_name = driver_config.exchange_name
        exchange_type = driver_config.exchange_type
        queue_name = driver_config.queue_name
        queue_durable = driver_config.queue_durable
        auto_ack = driver_config.auto_ack

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            exchange_name=exchange_name,
            exchange_type=exchange_type,
            queue_name=queue_name,
            queue_durable=queue_durable,
            auto_ack=auto_ack,
        )

    def connect(self) -> None:
        """Connect to RabbitMQ server.

        Raises:
            ImportError: If pika library is not installed
            Exception: If connection or setup fails
        """
        import pika

        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(host=self.host, port=self.port, credentials=credentials)

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # Declare exchange
        self.channel.exchange_declare(exchange=self.exchange_name, exchange_type=self.exchange_type, durable=True)

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
            result = self.channel.queue_declare(queue="", exclusive=True)
            self.queue_name = result.method.queue

        logger.info(
            f"Connected to RabbitMQ: {self.host}:{self.port}, "
            f"exchange={self.exchange_name}, queue={self.queue_name}"
        )

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
        callback: Callable[[dict[str, Any]], None],
        routing_key: str | None = None,
        exchange: str | None = None,
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

        # Choose exchange (allow override for compatibility/testing)
        target_exchange = exchange or self.exchange_name

        # Bind queue to exchange with routing key
        self.channel.queue_bind(exchange=target_exchange, queue=self.queue_name, routing_key=routing_key)

        logger.info(
            f"Subscribed to {event_type} events on exchange {target_exchange} " f"with routing key: {routing_key}"
        )

    def start_consuming(self) -> None:
        """Start consuming events from the queue.

        Raises:
            RuntimeError: If not connected to RabbitMQ
            AssertionError: Re-raised for non-transport-related assertions
            Exception: Re-raised for unexpected errors
        """
        if not self.channel:
            raise RuntimeError("Not connected. Call connect() first.")

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self._on_message, auto_ack=self.auto_ack)

        self._consuming = True
        logger.info("Started consuming events")

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop_consuming()
        except AssertionError as e:
            # Handle pika internal transport state errors gracefully
            # These are typically race conditions during shutdown/cleanup
            error_str = str(e)
            if "_AsyncTransportBase" in error_str or "_STATE_COMPLETED" in error_str:
                logger.warning(
                    f"Pika transport state assertion: {e}. " "This is a known pika issue during connection cleanup."
                )
                # Don't re-raise - this is a benign shutdown race condition
            else:
                # Other assertion errors should be re-raised
                logger.error(f"Unexpected assertion error in start_consuming: {e}")
                raise
        finally:
            # Ensure consuming flag is reset when start_consuming exits
            # This handles cases where exceptions occur that aren't caught above
            self._consuming = False

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully.

        Handles potential exceptions during stop to prevent
        shutdown race conditions.
        """
        if self.channel and self._consuming:
            try:
                self.channel.stop_consuming()
                logger.info("Stopped consuming events")
            except (AssertionError, ConnectionError, AttributeError) as e:
                # Expected exceptions during shutdown:
                # - AssertionError: transport state issues
                # - ConnectionError: already disconnected
                # - AttributeError: channel/connection already closed
                logger.debug(f"Expected exception during stop_consuming: {e}")
            except Exception as e:
                # Unexpected exceptions should be logged at warning level
                logger.warning(f"Unexpected exception during stop_consuming: {e}")
            finally:
                # Always reset the flag
                self._consuming = False

    def _on_message(self, channel: Any, method: Any, properties: Any, body: bytes) -> None:
        """Handle incoming message from RabbitMQ.

        Args:
            channel: Channel object
            method: Method frame with delivery info
            properties: Message properties
            body: Message body (bytes)
        """
        del properties
        try:
            # Decode and parse message
            message_str = body.decode("utf-8")
            event = json.loads(message_str)

            # Extract event type
            event_type = event.get("event_type")

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
                        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
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
                    requeue=False,  # Don't requeue unexpected errors
                )

    def _event_type_to_routing_key(self, event_type: str) -> str:
        """Convert event type to routing key.

        Args:
            event_type: Event type in PascalCase (e.g., "ArchiveIngested")

        Returns:
            Routing key in dot notation (e.g., "archive.ingested")
        """
        # Handle consecutive uppercase blocks (e.g., JSON) before standard casing
        key = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1.\2", event_type)
        # Handle remaining transitions from lower/number to upper
        key = re.sub(r"([a-z\d])([A-Z])", r"\1.\2", key)
        return key.lower()
