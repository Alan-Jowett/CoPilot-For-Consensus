# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Service Bus event publisher implementation."""

import json
import logging
from typing import Any

try:
    from azure.identity import DefaultAzureCredential
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.servicebus.exceptions import ServiceBusError
except ImportError:
    ServiceBusClient = None  # type: ignore
    ServiceBusMessage = None  # type: ignore
    ServiceBusError = None  # type: ignore
    DefaultAzureCredential = None  # type: ignore

from .publisher import EventPublisher

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
    ):
        """Initialize Azure Service Bus publisher.

        Args:
            connection_string: Azure Service Bus connection string
            fully_qualified_namespace: Namespace hostname (e.g., "namespace.servicebus.windows.net")
                Required if using managed identity
            queue_name: Default queue name (for queue-based messaging)
            topic_name: Default topic name (for topic/subscription-based messaging)
            use_managed_identity: Use Azure managed identity for authentication

        Raises:
            ValueError: If neither connection_string nor fully_qualified_namespace is provided
            ValueError: If use_managed_identity is True but fully_qualified_namespace is not provided
        """
        if not connection_string and not fully_qualified_namespace:
            raise ValueError(
                "Either connection_string or fully_qualified_namespace must be provided"
            )

        if use_managed_identity and not fully_qualified_namespace:
            raise ValueError(
                "fully_qualified_namespace is required when using managed identity"
            )

        self.connection_string = connection_string
        self.fully_qualified_namespace = fully_qualified_namespace
        self.queue_name = queue_name
        self.topic_name = topic_name
        self.use_managed_identity = use_managed_identity

        self.client: Any = None  # ServiceBusClient after connect()
        self._credential: Any = None  # DefaultAzureCredential if using managed identity

    def connect(self) -> None:
        """Connect to Azure Service Bus.

        Raises:
            ImportError: If azure-servicebus or azure-identity library is not installed
            Exception: If connection fails
        """
        if ServiceBusClient is None:
            raise ImportError("azure-servicebus library is not installed")

        if self.use_managed_identity and DefaultAzureCredential is None:
            raise ImportError("azure-identity library is not installed")

        try:
            if self.use_managed_identity:
                logger.info("Connecting to Azure Service Bus using managed identity")
                if self.fully_qualified_namespace is None:
                    raise ValueError("fully_qualified_namespace is required when using managed identity")
                self._credential = DefaultAzureCredential()  # type: ignore[misc]
                self.client = ServiceBusClient(
                    fully_qualified_namespace=self.fully_qualified_namespace,
                    credential=self._credential,
                )
            elif self.connection_string:
                logger.info("Connecting to Azure Service Bus using connection string")
                self.client = ServiceBusClient.from_connection_string(
                    conn_str=self.connection_string
                )

            logger.info("Connected to Azure Service Bus")

        except Exception as e:
            logger.error(f"Failed to connect to Azure Service Bus: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from Azure Service Bus."""
        try:
            if self.client:
                self.client.close()
                self.client = None
                logger.info("Disconnected from Azure Service Bus")
        except Exception as e:
            logger.error(f"Error disconnecting from Azure Service Bus: {e}")

    def _determine_publish_target(
        self, exchange: str, routing_key: str
    ) -> tuple[str | None, str | None]:
        """Determine the target queue or topic for publishing.

        Topic takes precedence over queue. If both queue_name and topic_name
        are configured, the topic is used. Otherwise, the exchange parameter
        is used as the topic name, or the routing_key is used as the queue name.

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

        # Fall back to using exchange as topic or routing_key as queue
        # Prefer topic (exchange) over queue (routing_key) for consistency with RabbitMQ
        return (exchange, None)

    def publish(self, exchange: str, routing_key: str, event: dict[str, Any]) -> None:
        """Publish an event to Azure Service Bus.

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
            ServiceBusError: If message publishing fails
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
                    logger.info(
                        f"Published event to queue {target_queue}: {event.get('event_type')}"
                    )
            else:
                error_msg = "No topic or queue configured for publishing"
                logger.error(error_msg)
                raise ValueError(error_msg)

        except Exception as e:
            # Check if it's a ServiceBusError (if the module is available)
            if ServiceBusError is not None and isinstance(e, ServiceBusError):
                logger.error(f"Azure Service Bus error while publishing: {e}")
            else:
                logger.error(f"Failed to publish event: {e}")
            raise
