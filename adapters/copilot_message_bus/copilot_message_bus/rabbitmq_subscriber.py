# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event subscriber implementation."""

import json
import logging
import random
import re
import time
from collections.abc import Callable
from typing import Any

from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_Rabbitmq

from .base import EventSubscriber

try:
    import pika
except ImportError:
    pika = None

pika_exceptions: Any = getattr(pika, "exceptions", None)

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
        heartbeat: int = 300,
        blocked_connection_timeout: int = 600,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 60.0,
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
            heartbeat: Heartbeat interval in seconds (default: 300). Higher values reduce
                       network overhead and prevent disconnects during CPU-intensive tasks.
                       Set to 0 to disable heartbeats (not recommended).
            blocked_connection_timeout: Timeout in seconds for blocked connections due to
                                       TCP backpressure (default: 600). Should be at least
                                       2x the heartbeat interval.
            max_reconnect_attempts: Maximum number of reconnection attempts per cycle
            reconnect_delay: Base delay between reconnection attempts in seconds
            max_reconnect_delay: Maximum delay between reconnection attempts (default: 60.0)

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
        self.heartbeat = heartbeat
        self.blocked_connection_timeout = blocked_connection_timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        self.connection: Any = None  # pika.BlockingConnection after connect()
        self.channel: Any = None  # pika.channel.Channel after connect()
        self.callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._consuming = False
        self._subscriptions: list[tuple[str, str, str | None]] = []  # (event_type, routing_key, exchange)
        self._last_reconnect_time = 0.0
        self._reconnect_count = 0
        self._shutdown_requested = False
        self._consumer_tag: str | None = None
        self._consume_channel_id: int | None = None

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
                          - heartbeat: Heartbeat interval (optional)
                          - blocked_connection_timeout: Blocked connection timeout (optional)

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
        heartbeat = driver_config.heartbeat
        blocked_connection_timeout = driver_config.blocked_connection_timeout

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
            heartbeat=heartbeat,
            blocked_connection_timeout=blocked_connection_timeout,
        )

    def connect(self) -> None:
        """Connect to RabbitMQ server.

        Raises:
            ImportError: If pika library is not installed
            Exception: If connection or setup fails
        """
        if pika is None:
            raise ImportError("pika library is not installed")

        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=self.heartbeat,
            blocked_connection_timeout=self.blocked_connection_timeout,
        )

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

    def _is_connected(self) -> bool:
        """Check if connection and channel are open.

        Returns:
            True if both connection and channel are open, False otherwise
        """
        try:
            # NOTE: some unit tests mock only the channel; allow connection to be None
            # as long as the channel is open.
            return (
                self.channel is not None
                and self.channel.is_open
                and (self.connection is None or not self.connection.is_closed)
            )
        except Exception:
            return False

    def _reconnect(self) -> bool:
        """Attempt to reconnect to RabbitMQ with circuit breaker logic.

        Implements exponential backoff with jitter to prevent reconnection storms.
        Resets reconnect count after successful reconnection.
        Re-establishes all subscriptions after successful reconnection.

        Returns:
            True if reconnection succeeded, False otherwise
        """
        current_time = time.time()

        # Circuit breaker with exponential backoff: prevent rapid reconnection attempts
        time_since_last_reconnect = current_time - self._last_reconnect_time
        # Exponential backoff with jitter and reasonable cap
        backoff_delay = min(self.reconnect_delay * (2 ** self._reconnect_count), self.max_reconnect_delay)
        # Add jitter (±20%) to prevent thundering herd
        jitter = backoff_delay * 0.2 * (random.random() * 2 - 1)
        backoff_with_jitter = max(0.0, backoff_delay + jitter)

        if time_since_last_reconnect < backoff_with_jitter:
            remaining = max(0.0, backoff_with_jitter - time_since_last_reconnect)
            logger.debug(f"Reconnection throttled, {remaining:.1f}s remaining (backoff {backoff_with_jitter:.1f}s)")
            return False

        # Check reconnection limit
        if self._reconnect_count >= self.max_reconnect_attempts:
            logger.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) exceeded in this cycle")
            # Reset count to allow future reconnection attempts
            self._reconnect_count = 0
            return False

        # Record attempt time only when we are actually going to attempt reconnect.
        self._last_reconnect_time = current_time

        # Close existing connections gracefully
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
        except Exception as e:
            logger.debug(f"Error closing channel during reconnect: {e}")

        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except Exception as e:
            logger.debug(f"Error closing connection during reconnect: {e}")

        # Reset state
        self.channel = None
        self.connection = None

        # Attempt reconnection
        self._reconnect_count += 1
        logger.info(f"Attempting reconnection {self._reconnect_count}/{self.max_reconnect_attempts}...")

        try:
            self.connect()
            logger.info("Reconnection successful")

            # Re-establish all subscriptions
            if self._subscriptions:
                logger.info(f"Re-establishing {len(self._subscriptions)} subscription(s)...")
                for event_type, routing_key, exchange in self._subscriptions:
                    try:
                        self.channel.queue_bind(
                            exchange=exchange or self.exchange_name,
                            queue=self.queue_name,
                            routing_key=routing_key,
                        )
                        logger.info(f"Re-subscribed to {event_type} with routing key: {routing_key}")
                    except Exception as e:
                        logger.error(f"Failed to re-subscribe to {event_type}: {e}")
                        raise

            self._reconnect_count = 0  # Reset count on success
            return True
        except Exception as e:
            logger.error(f"Reconnection attempt {self._reconnect_count} failed: {e}")
            return False

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
            exchange: Exchange to subscribe to (defaults to self.exchange_name)
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

        # Store subscription for reconnection
        subscription = (event_type, routing_key, target_exchange)
        if subscription not in self._subscriptions:
            self._subscriptions.append(subscription)

        # Bind queue to exchange with routing key
        self.channel.queue_bind(exchange=target_exchange, queue=self.queue_name, routing_key=routing_key)

        logger.info(
            f"Subscribed to {event_type} events on exchange {target_exchange} " f"with routing key: {routing_key}"
        )

    def start_consuming(self) -> None:
        """Start consuming events from the queue with automatic reconnection.

        This method will automatically reconnect and resume consuming if the
        connection or channel is closed by the broker (e.g., due to ack timeout).
        The reconnection loop can be stopped by calling stop_consuming() or via KeyboardInterrupt.

        Raises:
            RuntimeError: If not connected to RabbitMQ initially
        """
        if not self.channel:
            raise RuntimeError("Not connected. Call connect() first.")

        self._shutdown_requested = False

        while not self._shutdown_requested:
            if not self._is_connected():
                logger.warning("Not connected, attempting to reconnect...")
                if not self._reconnect():
                    # Avoid a tight spin-loop; backoff is enforced by _reconnect().
                    time.sleep(0.1)
                    continue

            # Ensure we only register a consumer once per channel instance.
            channel_id = id(self.channel)
            if self._consume_channel_id != channel_id:
                self._consume_channel_id = channel_id
                self._consumer_tag = None

            if self._consumer_tag is None:
                self._consumer_tag = self.channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._on_message,
                    auto_ack=self.auto_ack,
                )

            self._consuming = True
            logger.info("Started consuming events")

            try:
                self.channel.start_consuming()
                # start_consuming normally only returns after stop_consuming() is called.
                if self._shutdown_requested:
                    break
                logger.warning("RabbitMQ consumption stopped unexpectedly; will attempt to reconnect")
                # Force reconnect path on next loop.
                self.channel = None
                self.connection = None
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping consumer")
                self.stop_consuming()
                break
            except AssertionError as e:
                # Handle pika internal transport state errors gracefully.
                # NOTE: pika has a typo in the error message - "_initate" instead of "_initiate".
                error_str = str(e)
                if "_AsyncTransportBase" in error_str or "_STATE_COMPLETED" in error_str:
                    logger.warning(
                        f"Pika transport state assertion: {e}. This is a known pika issue during cleanup."
                    )
                    # Exit the loop so a supervising service can restart the subscriber thread.
                    return
                logger.error(f"Unexpected assertion error: {e}")
                raise
            except Exception as e:
                # Connection/channel errors - log and reconnect.
                if pika_exceptions is None:
                    logger.warning(f"Error during consuming (pika exceptions unavailable): {e}; will reconnect")
                elif isinstance(
                    e,
                    (
                        pika_exceptions.ChannelClosedByBroker,
                        pika_exceptions.ChannelWrongStateError,
                        pika_exceptions.ConnectionClosedByBroker,
                        pika_exceptions.AMQPConnectionError,
                        pika_exceptions.StreamLostError,
                    ),
                ):
                    logger.warning(f"Connection/channel error during consuming: {e}; will reconnect")
                else:
                    logger.error(f"Unexpected error during consuming: {e}; will reconnect")

                # Force reconnect path on next loop.
                self.channel = None
                self.connection = None
                self._consumer_tag = None
                self._consume_channel_id = None
            finally:
                self._consuming = False

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully.

        Sets the shutdown flag to exit the reconnection loop and stops
        the current consuming operation if active.
        Handles potential exceptions during stop to prevent
        shutdown race conditions.
        """
        self._shutdown_requested = True
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
                    self._safe_ack(channel, method.delivery_tag)
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
                        self._safe_nack(channel, method.delivery_tag, requeue=True)
                    return
            else:
                logger.debug(f"No callback registered for {event_type}")

            # Acknowledge message if not auto-ack
            if not self.auto_ack:
                self._safe_ack(channel, method.delivery_tag)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode event JSON: {e}")
            # Ack malformed messages so they don't block the queue
            if not self.auto_ack:
                self._safe_ack(channel, method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if not self.auto_ack:
                self._safe_nack(
                    channel,
                    method.delivery_tag,
                    requeue=False,  # Don't requeue unexpected errors
                )

    def _safe_ack(self, channel: Any, delivery_tag: int) -> None:
        """Safely acknowledge a message, catching channel closure errors.

        Args:
            channel: Channel object
            delivery_tag: Delivery tag to acknowledge
        """
        try:
            channel.basic_ack(delivery_tag=delivery_tag)
        except Exception as e:
            # If channel is closed, log but don't propagate - the reconnection loop will handle it
            if pika_exceptions and isinstance(
                e,
                (
                    pika_exceptions.ChannelClosedByBroker,
                    pika_exceptions.ChannelWrongStateError,
                    pika_exceptions.ConnectionClosedByBroker,
                    pika_exceptions.StreamLostError,
                ),
            ):
                logger.warning(f"Channel closed during ack (delivery_tag={delivery_tag}): {e}")
            elif pika_exceptions is None:
                logger.warning(
                    f"Error during ack (delivery_tag={delivery_tag}) but pika exceptions unavailable: {e}"
                )
            else:
                logger.error(f"Unexpected error during ack (delivery_tag={delivery_tag}): {e}")

    def _safe_nack(self, channel: Any, delivery_tag: int, requeue: bool = True) -> None:
        """Safely negative-acknowledge a message, catching channel closure errors.

        Args:
            channel: Channel object
            delivery_tag: Delivery tag to negative-acknowledge
            requeue: Whether to requeue the message
        """
        try:
            channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
        except Exception as e:
            # If channel is closed, log but don't propagate - the reconnection loop will handle it
            if pika_exceptions and isinstance(
                e,
                (
                    pika_exceptions.ChannelClosedByBroker,
                    pika_exceptions.ChannelWrongStateError,
                    pika_exceptions.ConnectionClosedByBroker,
                    pika_exceptions.StreamLostError,
                ),
            ):
                logger.warning(f"Channel closed during nack (delivery_tag={delivery_tag}): {e}")
            elif pika_exceptions is None:
                logger.warning(
                    f"Error during nack (delivery_tag={delivery_tag}) but pika exceptions unavailable: {e}"
                )
            else:
                logger.error(f"Unexpected error during nack (delivery_tag={delivery_tag}): {e}")

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
