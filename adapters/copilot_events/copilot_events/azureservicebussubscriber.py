# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Service Bus event subscriber implementation."""

import json
import logging
import threading
from typing import Callable, Dict, Any, Optional

try:
    from azure.servicebus import ServiceBusClient, ServiceBusReceiveMode
    from azure.servicebus.exceptions import ServiceBusError
    from azure.identity import DefaultAzureCredential
except ImportError:
    ServiceBusClient = None  # type: ignore
    ServiceBusReceiveMode = None  # type: ignore
    ServiceBusError = None  # type: ignore
    DefaultAzureCredential = None  # type: ignore

from .subscriber import EventSubscriber

logger = logging.getLogger(__name__)


class AzureServiceBusSubscriber(EventSubscriber):
    """Azure Service Bus implementation of EventSubscriber.
    
    Subscribes to events from Azure Service Bus queues or topic subscriptions
    and dispatches them to registered callbacks based on event type.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        fully_qualified_namespace: Optional[str] = None,
        queue_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        subscription_name: Optional[str] = None,
        use_managed_identity: bool = False,
        auto_complete: bool = False,
        max_wait_time: int = 5,
    ):
        """Initialize Azure Service Bus subscriber.
        
        Args:
            connection_string: Azure Service Bus connection string
            fully_qualified_namespace: Namespace hostname (e.g., "namespace.servicebus.windows.net")
                Required if using managed identity
            queue_name: Queue name to receive from (for queue-based messaging)
            topic_name: Topic name (for topic/subscription-based messaging)
            subscription_name: Subscription name (required if topic_name is provided)
            use_managed_identity: Use Azure managed identity for authentication
            auto_complete: Whether to automatically complete messages (default: False for manual ack)
            max_wait_time: Maximum time to wait for messages in seconds (default: 5)
            
        Raises:
            ValueError: If neither connection_string nor fully_qualified_namespace is provided
            ValueError: If topic_name is provided but subscription_name is not
            ValueError: If neither queue_name nor topic_name is provided
        """
        if not connection_string and not fully_qualified_namespace:
            raise ValueError(
                "Either connection_string or fully_qualified_namespace must be provided"
            )
        
        if use_managed_identity and not fully_qualified_namespace:
            raise ValueError(
                "fully_qualified_namespace is required when using managed identity"
            )
        
        if topic_name and not subscription_name:
            raise ValueError(
                "subscription_name is required when topic_name is provided"
            )
        
        if not queue_name and not topic_name:
            raise ValueError(
                "Either queue_name or topic_name must be provided"
            )
        
        self.connection_string = connection_string
        self.fully_qualified_namespace = fully_qualified_namespace
        self.queue_name = queue_name
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self.use_managed_identity = use_managed_identity
        self.auto_complete = auto_complete
        self.max_wait_time = max_wait_time
        
        self.client: Optional[ServiceBusClient] = None
        self._credential = None
        self.callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._consuming = threading.Event()  # Thread-safe flag for consumption control

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
                self._credential = DefaultAzureCredential()
                self.client = ServiceBusClient(
                    fully_qualified_namespace=self.fully_qualified_namespace,
                    credential=self._credential,
                )
            elif self.connection_string:
                logger.info("Connecting to Azure Service Bus using connection string")
                self.client = ServiceBusClient.from_connection_string(
                    conn_str=self.connection_string
                )
            
            source = f"queue={self.queue_name}" if self.queue_name else f"topic={self.topic_name}/subscription={self.subscription_name}"
            logger.info(f"Connected to Azure Service Bus: {source}")
            
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

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        routing_key: str = None,
        exchange: str = None,
    ) -> None:
        """Subscribe to events of a specific type.
        
        For Azure Service Bus, the subscription is message-based rather than
        routing-key based. This method registers a callback for a specific event type.
        Messages are filtered by event_type field in the message body.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when an event is received
            routing_key: Not used for Azure Service Bus (kept for interface compatibility)
            exchange: Not used for Azure Service Bus (kept for interface compatibility)
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Register callback
        self.callbacks[event_type] = callback
        
        logger.info(f"Registered callback for event type: {event_type}")

    def start_consuming(self) -> None:
        """Start consuming events from the queue or subscription.
        
        This method blocks and processes events as they arrive,
        calling the registered callbacks.
        
        Raises:
            RuntimeError: If not connected to Azure Service Bus
            Exception: For unexpected errors during message processing
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")
        
        if ServiceBusReceiveMode is None:
            raise RuntimeError("azure-servicebus library is not installed")
        
        self._consuming.set()
        logger.info("Started consuming events")
        
        try:
            # Choose receive mode based on auto_complete setting
            receive_mode = (
                ServiceBusReceiveMode.RECEIVE_AND_DELETE
                if self.auto_complete
                else ServiceBusReceiveMode.PEEK_LOCK
            )
            
            # Get receiver based on queue or topic/subscription
            if self.queue_name:
                receiver = self.client.get_queue_receiver(
                    queue_name=self.queue_name,
                    receive_mode=receive_mode,
                )
            else:
                receiver = self.client.get_subscription_receiver(
                    topic_name=self.topic_name,
                    subscription_name=self.subscription_name,
                    receive_mode=receive_mode,
                )
            
            with receiver:
                # Continuously receive and process messages
                while self._consuming.is_set():
                    try:
                        # Receive messages with timeout
                        messages = receiver.receive_messages(
                            max_message_count=10,
                            max_wait_time=self.max_wait_time,
                        )
                        
                        for msg in messages:
                            try:
                                self._process_message(msg, receiver)
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                # In manual ack mode, abandon the message so it can be retried
                                if not self.auto_complete:
                                    try:
                                        receiver.abandon_message(msg)
                                    except Exception as abandon_error:
                                        logger.error(f"Error abandoning message: {abandon_error}")
                                        
                    except KeyboardInterrupt:
                        logger.info("Received keyboard interrupt, stopping consumption")
                        break
                    except Exception as e:
                        if self._consuming.is_set():
                            logger.error(f"Error receiving messages: {e}")
                        # Continue processing unless explicitly stopped
                        
        except Exception as e:
            logger.error(f"Error in start_consuming: {e}")
            raise
        finally:
            self._consuming.clear()
            logger.info("Stopped consuming events")

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully."""
        if self._consuming.is_set():
            self._consuming.clear()
            logger.info("Stopping event consumption")

    def _process_message(self, msg, receiver) -> None:
        """Process a received message.
        
        Args:
            msg: ServiceBusReceivedMessage object
            receiver: ServiceBusReceiver object
        """
        try:
            # Parse message body
            message_body = str(msg)
            event = json.loads(message_body)
            
            # Extract event type
            event_type = event.get("event_type")
            
            if not event_type:
                logger.warning("Received message without event_type field")
                if not self.auto_complete:
                    receiver.complete_message(msg)
                return
            
            # Find and call registered callback
            callback = self.callbacks.get(event_type)
            
            if callback:
                try:
                    callback(event)
                    logger.debug(f"Processed {event_type} event: {event.get('event_id')}")
                    
                    # Complete message if not auto-complete
                    if not self.auto_complete:
                        receiver.complete_message(msg)
                        
                except Exception as e:
                    logger.error(f"Error in callback for {event_type}: {e}")
                    # Abandon message for retry if not auto-complete
                    if not self.auto_complete:
                        receiver.abandon_message(msg)
                    raise
            else:
                logger.debug(f"No callback registered for {event_type}")
                # Complete message even if no callback (to avoid reprocessing)
                if not self.auto_complete:
                    receiver.complete_message(msg)
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
            # Complete malformed messages to avoid blocking the queue
            if not self.auto_complete:
                receiver.complete_message(msg)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Let the exception propagate to the caller for error handling
            raise
