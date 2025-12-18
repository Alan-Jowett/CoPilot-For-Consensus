# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""RabbitMQ event publisher implementation."""

import json
import logging
import time
from typing import Dict, Any, List, Optional

try:
    import pika
except ImportError:
    pika = None  # type: ignore

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
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 2.0,
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
            max_reconnect_attempts: Maximum number of reconnection attempts
            reconnect_delay: Delay between reconnection attempts in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.enable_publisher_confirms = enable_publisher_confirms
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.connection = None
        self.channel = None
        self._declared_queues = set()
        self._last_reconnect_time = 0.0
        self._reconnect_count = 0

    def connect(self) -> bool:
        """Connect to RabbitMQ and declare exchange.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        if pika is None:
            logger.error("pika library is not installed")
            return False
            
        try:
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

    def _is_connected(self) -> bool:
        """Check if connection and channel are open.
        
        Returns:
            True if both connection and channel are open, False otherwise
        """
        try:
            return (
                self.connection is not None
                and not self.connection.is_closed
                and self.channel is not None
                and self.channel.is_open
            )
        except Exception:
            return False

    def _reconnect(self) -> bool:
        """Attempt to reconnect to RabbitMQ with circuit breaker logic.
        
        Implements exponential backoff to prevent reconnection storms.
        Resets reconnect count after successful reconnection.
        
        Returns:
            True if reconnection succeeded, False otherwise
        """
        current_time = time.time()
        
        # Circuit breaker: prevent rapid reconnection attempts
        time_since_last_reconnect = current_time - self._last_reconnect_time
        if time_since_last_reconnect < self.reconnect_delay:
            logger.warning(
                f"Reconnection throttled, {self.reconnect_delay - time_since_last_reconnect:.1f}s remaining"
            )
            return False
        
        self._last_reconnect_time = current_time
        
        # Check reconnection limit
        if self._reconnect_count >= self.max_reconnect_attempts:
            logger.error(
                f"Maximum reconnection attempts ({self.max_reconnect_attempts}) exceeded"
            )
            return False
        
        # Close existing connections
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
        logger.info(
            f"Attempting reconnection {self._reconnect_count}/{self.max_reconnect_attempts}..."
        )
        
        if self.connect():
            logger.info("Reconnection successful")
            self._reconnect_count = 0  # Reset count on success
            
            # Re-declare queues that were previously declared
            if self._declared_queues:
                logger.info(f"Re-declaring {len(self._declared_queues)} queues...")
                queues_to_redeclare = list(self._declared_queues)
                self._declared_queues.clear()
                for queue_name in queues_to_redeclare:
                    self.declare_queue(queue_name)
            
            return True
        else:
            logger.error(f"Reconnection attempt {self._reconnect_count} failed")
            return False

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

    def declare_queues(self, queues: List[Dict[str, Optional[str]]]) -> bool:
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

    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> None:
        """Publish an event to RabbitMQ with message persistence and automatic reconnection.
        
        Messages are published with:
        - delivery_mode=2 for persistence
        - mandatory=True to detect unroutable messages
        - Publisher confirms (if enabled) for guaranteed delivery
        - Automatic reconnection on channel/connection errors
        
        Args:
            exchange: Exchange name
            routing_key: Routing key
            event: Event data as dictionary
            
        Raises:
            ConnectionError: If not connected and reconnection fails
            RuntimeError: If pika library is not installed
            pika.exceptions.UnroutableError: If message is unroutable
            pika.exceptions.NackError: If message is rejected by broker
            Exception: For other publishing failures
        """
        if pika is None:
            error_msg = "pika library is not installed"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Check connection and attempt reconnection if needed
        if not self._is_connected():
            logger.warning("Channel closed, attempting reconnection...")
            if not self._reconnect():
                error_msg = "Not connected to RabbitMQ and reconnection failed"
                logger.error(error_msg)
                raise ConnectionError(error_msg)

        try:
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
        except (
            pika.exceptions.ChannelWrongStateError,
            pika.exceptions.ChannelClosedByBroker,
            pika.exceptions.ConnectionClosedByBroker,
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.StreamLostError,
        ) as e:
            # Connection/channel errors - attempt reconnection and retry once
            logger.warning(f"Connection error during publish: {e}, attempting reconnection...")
            if self._reconnect():
                logger.info("Retrying publish after reconnection...")
                try:
                    self.channel.basic_publish(
                        exchange=exchange,
                        routing_key=routing_key,
                        body=json.dumps(event),
                        properties=pika.BasicProperties(
                            delivery_mode=2,
                            content_type="application/json",
                        ),
                        mandatory=True,
                    )
                    logger.info(
                        f"Successfully published event after reconnection: {event.get('event_type')}"
                    )
                except Exception as retry_error:
                    logger.error(f"Retry publish failed after reconnection: {retry_error}")
                    raise
            else:
                logger.error("Reconnection failed, cannot publish event")
                raise ConnectionError(f"Failed to publish after connection error: {e}")
        except pika.exceptions.UnroutableError:
            error_msg = (
                f"Message unroutable - no queue bound for {exchange}/{routing_key}. "
                "Ensure queues are declared before publishing."
            )
            logger.error(error_msg)
            raise
        except pika.exceptions.NackError:
            error_msg = f"Message rejected (NACK) by broker for {exchange}/{routing_key}"
            logger.error(error_msg)
            raise
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise
