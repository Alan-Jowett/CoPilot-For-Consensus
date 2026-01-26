# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Service Bus event publisher implementation."""

import json
import logging
import time
from typing import Any

from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_AzureServiceBus

try:
    from azure.identity import DefaultAzureCredential
    from azure.servicebus import ServiceBusClient, ServiceBusMessage, TransportType
    from azure.servicebus.exceptions import ServiceBusConnectionError, ServiceBusError
except ImportError:
    ServiceBusClient = None  # type: ignore
    ServiceBusMessage = None  # type: ignore
    ServiceBusError = None  # type: ignore
    ServiceBusConnectionError = None  # type: ignore
    TransportType = None  # type: ignore
    DefaultAzureCredential = None  # type: ignore

from .base import EventPublisher

logger = logging.getLogger(__name__)


class AzureServiceBusPublisher(EventPublisher):
    """Azure Service Bus-based event publisher with persistent messages."""

    def __init__(
        self,
        connection_string: str | None = None,
        fully_qualified_namespace: str | None = None,
        queue_name: str | None = None,
        topic_name: str | None = None,
        use_managed_identity: bool = False,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
        transport_type: str = "amqp",
    ):
        """Initialize Azure Service Bus publisher.

        Args:
            connection_string: Azure Service Bus connection string
            fully_qualified_namespace: Namespace hostname (e.g., "namespace.servicebus.windows.net")
                Required if using managed identity
            queue_name: Default queue name (for queue-based messaging)
            topic_name: Default topic name (for topic/subscription-based messaging)
            use_managed_identity: Use Azure managed identity for authentication
            retry_attempts: Number of retry attempts for transient connection errors (default: 3)
            retry_backoff_seconds: Initial backoff delay in seconds before retry (default: 1.0)
            transport_type: Transport protocol - "amqp" or "websockets" (default: "amqp")

        Raises:
            ValueError: If required parameters are missing (enforced by schema validation)
        """
        self.connection_string = connection_string
        self.fully_qualified_namespace = fully_qualified_namespace
        self.queue_name = queue_name
        self.topic_name = topic_name
        self.use_managed_identity = use_managed_identity
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.transport_type = transport_type

        self.client: Any = None  # ServiceBusClient after connect()
        self._credential: Any = None  # DefaultAzureCredential if using managed identity

    @classmethod
    def from_config(cls, driver_config: DriverConfig_MessageBus_AzureServiceBus) -> "AzureServiceBusPublisher":
        """Create publisher from DriverConfig.

        Args:
            driver_config: DriverConfig instance with configuration fields:
                          - connection_string: Azure Service Bus connection string (optional)
                          - servicebus_fully_qualified_namespace: Namespace hostname (optional)
                          - queue_name: Default queue name (optional)
                          - topic_name: Default topic name (optional)
                          - servicebus_use_managed_identity: Use managed identity (optional)
                          - retry_attempts: Number of retry attempts (default: 3)
                          - retry_backoff_seconds: Initial backoff delay (default: 1.0)
                          - transport_type: Transport protocol - "amqp" or "websockets" (default: "amqp")

        Returns:
            AzureServiceBusPublisher instance

        Raises:
            ValueError: If required parameters are missing
        """
        # Get configuration values from driver_config attributes
        fully_qualified_namespace = driver_config.servicebus_fully_qualified_namespace
        use_managed_identity = driver_config.servicebus_use_managed_identity
        connection_string = driver_config.connection_string
        queue_name = driver_config.queue_name
        topic_name = driver_config.topic_name
        retry_attempts = driver_config.retry_attempts
        retry_backoff_seconds = driver_config.retry_backoff_seconds
        transport_type = driver_config.transport_type

        return cls(
            connection_string=connection_string,
            fully_qualified_namespace=fully_qualified_namespace,
            queue_name=queue_name,
            topic_name=topic_name,
            use_managed_identity=use_managed_identity,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            transport_type=transport_type,
        )

    def connect(self) -> None:
        """Connect to Azure Service Bus with retry logic for transient errors.

        Raises:
            ImportError: If azure-servicebus or azure-identity library is not installed
            Exception: If connection fails after all retry attempts
        """
        # Determine transport type
        transport = None
        if TransportType is not None and self.transport_type == "websockets":
            transport = TransportType.AmqpOverWebsocket
            logger.info("Using WebSockets transport for Azure Service Bus connection")
        elif self.transport_type == "websockets":
            logger.warning("WebSockets transport requested but TransportType not available in SDK")

        attempt = 0
        last_exception = None
        
        while attempt <= self.retry_attempts:
            try:
                if self.use_managed_identity:
                    if ServiceBusClient is None:
                        raise ImportError("azure-servicebus library is not installed")
                    if DefaultAzureCredential is None:
                        raise ImportError("azure-identity library is not installed")

                    logger.info(
                        f"Connecting to Azure Service Bus using managed identity (attempt {attempt + 1}/{self.retry_attempts + 1})"
                    )
                    if self.fully_qualified_namespace is None:
                        raise ValueError("fully_qualified_namespace is required when using managed identity")
                    self._credential = DefaultAzureCredential()
                    
                    if transport:
                        self.client = ServiceBusClient(
                            fully_qualified_namespace=self.fully_qualified_namespace,
                            credential=self._credential,
                            transport_type=transport,
                        )
                    else:
                        self.client = ServiceBusClient(
                            fully_qualified_namespace=self.fully_qualified_namespace,
                            credential=self._credential,
                        )
                elif self.connection_string:
                    if ServiceBusClient is None:
                        raise ImportError("azure-servicebus library is not installed")

                    logger.info(
                        f"Connecting to Azure Service Bus using connection string (attempt {attempt + 1}/{self.retry_attempts + 1})"
                    )
                    
                    if transport:
                        self.client = ServiceBusClient.from_connection_string(
                            conn_str=self.connection_string,
                            transport_type=transport,
                        )
                    else:
                        self.client = ServiceBusClient.from_connection_string(conn_str=self.connection_string)

                logger.info("Connected to Azure Service Bus")
                return  # Success - exit retry loop

            except Exception as e:
                last_exception = e
                
                # Check if this is a transient connection error worth retrying
                is_transient = self._is_transient_error(e)
                
                if is_transient and attempt < self.retry_attempts:
                    backoff = self.retry_backoff_seconds * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Transient error connecting to Azure Service Bus: {e}. "
                        f"Retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.retry_attempts})"
                    )
                    time.sleep(backoff)
                    attempt += 1
                else:
                    # Non-transient error or exhausted retries
                    if is_transient:
                        logger.error(
                            f"Failed to connect to Azure Service Bus after {self.retry_attempts + 1} attempts: {e}"
                        )
                    else:
                        logger.error(f"Failed to connect to Azure Service Bus (non-transient error): {e}")
                    raise
        
        # If we get here, we exhausted retries
        if last_exception:
            raise last_exception

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient and should be retried.

        Args:
            error: Exception to check

        Returns:
            True if error is transient (connection/SSL errors), False otherwise
        """
        error_str = str(error).lower()
        
        # Check for ServiceBusConnectionError (includes SSL EOF errors)
        if ServiceBusConnectionError is not None and isinstance(error, ServiceBusConnectionError):
            return True
        
        # Check for SSL/connection-related error messages
        transient_patterns = [
            "ssl",
            "eof",
            "connection reset",
            "connection refused",
            "timeout",
            "temporary failure",
            "socket",
        ]
        
        return any(pattern in error_str for pattern in transient_patterns)

    def disconnect(self) -> None:
        """Disconnect from Azure Service Bus."""
        try:
            if self.client:
                self.client.close()
                self.client = None
                logger.info("Disconnected from Azure Service Bus")
        except Exception as e:
            logger.error(f"Error disconnecting from Azure Service Bus: {e}")

    def _determine_publish_target(self, exchange: str, routing_key: str) -> tuple[str | None, str | None]:
        """Determine the target queue or topic for publishing.

        Topic takes precedence over queue. If both queue_name and topic_name
        are configured, the topic is used. Otherwise, prefer queue-based routing
        using the routing_key as the queue name (aligns with queue-per-event
        deployments), and finally fall back to using the exchange as the topic
        name.

        Args:
            exchange: Exchange name (used as topic name if topic_name not set)
            routing_key: Routing key (used as queue name if queue_name not set)

        Returns:
            Tuple of (topic_name, queue_name). One will be None.
        """
        # Topic takes precedence if topic_name is configured
        if self.topic_name:
            return (self.topic_name, None)

        # If queue_name is configured, use it
        if self.queue_name:
            return (None, self.queue_name)

        # Fall back to using routing_key as queue name (queue-per-event default)
        if routing_key:
            return (None, routing_key)

        # Final fallback to using the exchange name as a topic
        return (exchange, None)

    def publish(self, exchange: str, routing_key: str, event: dict[str, Any]) -> None:
        """Publish an event to Azure Service Bus with retry logic for transient errors.

        For Azure Service Bus compatibility:
        - exchange parameter maps to topic name (if topic_name is set)
        - routing_key parameter maps to queue name (if queue_name is set) or is used as message label
        - If both topic and queue are configured, topic takes precedence

        Args:
            exchange: Exchange name (used as topic name if topic_name not set)
            routing_key: Routing key (used as queue name if queue_name not set, or as message label)
            event: Event data as dictionary

        Raises:
            ConnectionError: If not connected to Azure Service Bus
            RuntimeError: If azure-servicebus library is not installed
            ServiceBusError: If message publishing fails after all retry attempts
            Exception: For other publishing failures
        """
        if ServiceBusClient is None or ServiceBusMessage is None:
            error_msg = "azure-servicebus library is not installed"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        if not self.client:
            error_msg = "Not connected to Azure Service Bus"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        attempt = 0
        last_exception = None
        
        while attempt <= self.retry_attempts:
            try:
                # Serialize event to JSON
                message_body = json.dumps(event)

                # Create Service Bus message with application properties for routing
                message = ServiceBusMessage(
                    body=message_body,
                    content_type="application/json",
                    subject=routing_key,  # Use subject for message filtering in subscriptions
                )

                # Add custom properties for compatibility with event-driven patterns
                message.application_properties = {
                    "event_type": event.get("event_type", ""),
                    "routing_key": routing_key,
                    "exchange": exchange,
                }

                # Determine target: topic or queue
                target_topic, target_queue = self._determine_publish_target(exchange, routing_key)

                if target_topic:
                    # Publish to topic
                    with self.client.get_topic_sender(topic_name=target_topic) as sender:
                        sender.send_messages(message)
                        logger.info(
                            f"Published event to topic {target_topic} with subject {routing_key}: "
                            f"{event.get('event_type')}"
                        )
                elif target_queue:
                    # Publish to queue
                    with self.client.get_queue_sender(queue_name=target_queue) as sender:
                        sender.send_messages(message)
                        logger.info(f"Published event to queue {target_queue}: {event.get('event_type')}")
                else:
                    error_msg = "No topic or queue configured for publishing"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                return  # Success - exit retry loop

            except Exception as e:
                last_exception = e
                
                # Check if this is a transient error worth retrying
                is_transient = self._is_transient_error(e)
                
                if is_transient and attempt < self.retry_attempts:
                    backoff = self.retry_backoff_seconds * (2 ** attempt)  # Exponential backoff
                    
                    # Log with appropriate level based on error type
                    if ServiceBusError is not None and isinstance(e, ServiceBusError):
                        logger.warning(
                            f"Azure Service Bus transient error while publishing: {e}. "
                            f"Retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.retry_attempts})"
                        )
                    else:
                        logger.warning(
                            f"Transient error publishing event: {e}. "
                            f"Retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.retry_attempts})"
                        )
                    
                    time.sleep(backoff)
                    attempt += 1
                else:
                    # Non-transient error or exhausted retries - log and raise
                    if ServiceBusError is not None and isinstance(e, ServiceBusError):
                        if is_transient:
                            logger.error(
                                f"Azure Service Bus error while publishing after {self.retry_attempts + 1} attempts: {e}"
                            )
                        else:
                            logger.error(f"Azure Service Bus error while publishing (non-transient): {e}")
                    else:
                        if is_transient:
                            logger.error(f"Failed to publish event after {self.retry_attempts + 1} attempts: {e}")
                        else:
                            logger.error(f"Failed to publish event (non-transient error): {e}")
                    raise
        
        # If we get here, we exhausted retries
        if last_exception:
            raise last_exception
