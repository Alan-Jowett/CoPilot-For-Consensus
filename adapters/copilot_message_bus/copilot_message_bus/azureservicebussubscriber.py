# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Service Bus event subscriber implementation."""

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_AzureServiceBus

try:
    from azure.identity import DefaultAzureCredential
    from azure.servicebus import AutoLockRenewer, ServiceBusClient, ServiceBusReceiveMode
except ImportError:
    AutoLockRenewer = None  # type: ignore
    ServiceBusClient = None  # type: ignore
    ServiceBusReceiveMode = None  # type: ignore
    DefaultAzureCredential = None  # type: ignore

from .base import EventSubscriber

logger = logging.getLogger(__name__)


class AzureServiceBusSubscriber(EventSubscriber):
    """Azure Service Bus implementation of EventSubscriber.

    Subscribes to events from Azure Service Bus queues or topic subscriptions
    and dispatches them to registered callbacks based on event type.
    """

    def __init__(
        self,
        connection_string: str | None = None,
        fully_qualified_namespace: str | None = None,
        queue_name: str | None = None,
        topic_name: str | None = None,
        subscription_name: str | None = None,
        use_managed_identity: bool = False,
        auto_complete: bool = False,
        max_wait_time: int = 5,
        max_auto_lock_renewal_duration: int = 3600,
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
            max_auto_lock_renewal_duration: Maximum time (seconds) to auto-renew peek-lock messages
                while processing (default: 3600). Set to 0 to disable.

        Raises:
            ValueError: If required parameters are missing (enforced by schema validation)
        """
        self.connection_string = connection_string
        self.fully_qualified_namespace = fully_qualified_namespace
        self.queue_name = queue_name
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self.use_managed_identity = use_managed_identity
        self.auto_complete = auto_complete
        self.max_wait_time = max_wait_time
        self.max_auto_lock_renewal_duration = max_auto_lock_renewal_duration

        self.client: Any = None  # ServiceBusClient after connect()
        self._credential: Any = None  # DefaultAzureCredential if using managed identity
        self.callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._consuming = threading.Event()  # Thread-safe flag for consumption control
        self._last_error_log_time: float = 0  # Rate limiting for error logs
        self._error_log_interval: float = 60.0  # Log errors at most once per minute
        self._rate_limit_lock = threading.Lock()  # Protect rate limiting state

    @classmethod
    def from_config(cls, driver_config: DriverConfig_MessageBus_AzureServiceBus) -> "AzureServiceBusSubscriber":
        """Create subscriber from DriverConfig.

        Args:
            driver_config: DriverConfig instance with configuration fields:
                          - connection_string: Azure Service Bus connection string (optional)
                          - servicebus_fully_qualified_namespace: Namespace hostname (optional)
                          - queue_name: Queue name (optional)
                          - topic_name: Topic name (optional)
                          - subscription_name: Subscription name (optional)
                          - servicebus_use_managed_identity: Use managed identity (optional)
                          - auto_complete: Auto-complete messages (optional)
                          - max_wait_time: Max wait time in seconds (optional)

        Returns:
            AzureServiceBusSubscriber instance

        Raises:
            ValueError: If required parameters are missing
        """
        # Get configuration values from driver_config attributes
        fully_qualified_namespace = driver_config.servicebus_fully_qualified_namespace
        use_managed_identity = driver_config.servicebus_use_managed_identity
        connection_string = driver_config.connection_string
        queue_name = driver_config.queue_name
        topic_name = driver_config.topic_name
        subscription_name = driver_config.subscription_name
        auto_complete = driver_config.auto_complete
        max_wait_time = driver_config.max_wait_time
        max_auto_lock_renewal_duration = driver_config.max_auto_lock_renewal_duration

        # Note: the shared DriverConfig schema is used by both publisher and subscriber.
        # Some subscriber-specific invariants are enforced here to keep behavior stable
        # even if the JSON schema cannot express the conditional requirements.
        if topic_name and not subscription_name:
            raise ValueError("subscription_name parameter is required")
        if not queue_name and not topic_name:
            raise ValueError("Either queue_name or topic_name parameter is required")

        return cls(
            connection_string=connection_string,
            fully_qualified_namespace=fully_qualified_namespace,
            queue_name=queue_name,
            topic_name=topic_name,
            subscription_name=subscription_name,
            use_managed_identity=use_managed_identity,
            auto_complete=auto_complete,
            max_wait_time=max_wait_time,
            max_auto_lock_renewal_duration=max_auto_lock_renewal_duration,
        )

    def connect(self) -> None:
        """Connect to Azure Service Bus.

        Raises:
            ImportError: If azure-servicebus or azure-identity library is not installed
            Exception: If connection fails
        """
        try:
            if self.use_managed_identity:
                if ServiceBusClient is None:
                    raise ImportError("azure-servicebus library is not installed")
                if DefaultAzureCredential is None:
                    raise ImportError("azure-identity library is not installed")

                logger.info("Connecting to Azure Service Bus using managed identity")
                if self.fully_qualified_namespace is None:
                    raise ValueError("fully_qualified_namespace is required when using managed identity")
                self._credential = DefaultAzureCredential()
                self.client = ServiceBusClient(
                    fully_qualified_namespace=self.fully_qualified_namespace,
                    credential=self._credential,
                )
            elif self.connection_string:
                if ServiceBusClient is None:
                    raise ImportError("azure-servicebus library is not installed")

                logger.info("Connecting to Azure Service Bus using connection string")
                self.client = ServiceBusClient.from_connection_string(conn_str=self.connection_string)

            if self.queue_name:
                source = f"queue={self.queue_name}"
            else:
                source = f"topic={self.topic_name}/subscription={self.subscription_name}"
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
        callback: Callable[[dict[str, Any]], None],
        routing_key: str | None = None,
        exchange: str | None = None,
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
        del routing_key, exchange
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        # Register callback
        self.callbacks[event_type] = callback

        logger.info(f"Registered callback for event type: {event_type}")

    def start_consuming(self) -> None:
        """Start consuming events from the queue or subscription.

        This method blocks and processes events as they arrive,
        calling the registered callbacks. If the handler is shut down,
        it will automatically reconnect with exponential backoff.

        Note: This method is NOT thread-safe and must not be called
        concurrently from multiple threads. Use a single consuming
        thread per subscriber instance.

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

        retry_count = 0
        max_retries = 5
        base_backoff = 1.0  # Start with 1 second

        # Main consumption loop with recovery
        while self._consuming.is_set():
            # Check if we have a valid client before attempting to consume
            if not self.client:
                # Client is None (connection failed), perform retry logic
                self._log_rate_limited(
                    "Client not connected after previous reconnection failure. Will retry.",
                    level="warning",
                )
                retry_count = self._attempt_reconnection_with_backoff(retry_count, max_retries, base_backoff)
                continue  # Skip to next iteration

            try:
                self._consume_with_receiver()
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping consumption")
                break
            except Exception as e:
                error_str = str(e).lower()

                # Check if this is a handler shutdown error that requires reconnection
                # Match the specific error message from Azure SDK
                if (
                    "handler has already been shutdown" in error_str
                    or "handler already shutdown" in error_str
                ):
                    self._log_rate_limited(
                        f"Handler shutdown detected: {e}. Will reconnect and retry.",
                        level="warning"
                    )

                    # Close and recreate the client
                    try:
                        if self.client:
                            self.client.close()
                    except Exception as close_error:
                        logger.debug(f"Error closing client during recovery: {close_error}")
                    finally:
                        # Ensure we don't keep a reference to a closed client
                        self.client = None

                    # Reconnect with backoff
                    retry_count = self._attempt_reconnection_with_backoff(retry_count, max_retries, base_backoff)
                else:
                    # Non-recoverable error or unknown error type
                    logger.error(f"Error in start_consuming: {e}", exc_info=True)
                    raise

        self._consuming.clear()
        logger.info("Stopped consuming events")

    def _attempt_reconnection_with_backoff(self, retry_count: int, max_retries: int, base_backoff: float) -> int:
        """Attempt reconnection with exponential backoff.

        Args:
            retry_count: Current retry count
            max_retries: Maximum number of retries before using max backoff
            base_backoff: Base backoff time in seconds

        Returns:
            Updated retry count (0 if reconnection succeeded, incremented otherwise)
        """
        # Exponential backoff before reconnecting
        if retry_count < max_retries:
            backoff = base_backoff * (2 ** retry_count)
            logger.info(f"Reconnecting in {backoff:.1f}s (attempt {retry_count + 1}/{max_retries})")
            time.sleep(backoff)
            retry_count += 1
        else:
            # Cap at max backoff
            logger.error(
                f"Failed to recover after {max_retries} attempts. "
                "Continuing with max backoff."
            )
            backoff = base_backoff * (2 ** max_retries)
            time.sleep(backoff)
            # Keep retry_count at max_retries to maintain max backoff

        # Attempt to reconnect
        try:
            self.connect()
            logger.info("Successfully reconnected")
            # Reset retry count on successful reconnection
            return 0
        except Exception as reconnect_error:
            self._log_rate_limited(
                f"Failed to reconnect: {reconnect_error}",
                level="error"
            )
            # Return current retry count (capped at max_retries)
            return min(retry_count, max_retries)

    def _consume_with_receiver(self) -> None:
        """Consume messages with a receiver instance."""
        renewer: Any | None = None

        try:
            # Choose receive mode based on auto_complete setting
            receive_mode = (
                ServiceBusReceiveMode.RECEIVE_AND_DELETE if self.auto_complete else ServiceBusReceiveMode.PEEK_LOCK
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
                if (
                    not self.auto_complete
                    and AutoLockRenewer is not None
                    and self.max_auto_lock_renewal_duration > 0
                ):
                    renewer = AutoLockRenewer()

                # Continuously receive and process messages
                while self._consuming.is_set():
                    try:
                        # Receive messages with timeout
                        # In peek-lock mode, avoid locking a batch that might expire
                        # before it can be processed.
                        max_message_count = 10 if self.auto_complete else 1
                        messages = receiver.receive_messages(
                            max_message_count=max_message_count,
                            max_wait_time=self.max_wait_time,
                        )

                        for msg in messages:
                            if renewer is not None:
                                try:
                                    renewer.register(
                                        receiver,
                                        msg,
                                        max_lock_renewal_duration=self.max_auto_lock_renewal_duration,
                                    )
                                except AttributeError as e:
                                    # Known azure-servicebus SDK bug: internal handler can become None
                                    # during concurrent operations or connection closure
                                    logger.error(f"AutoLockRenewer AttributeError (likely SDK bug): {e}", exc_info=True)
                                except Exception as e:
                                    logger.warning(f"Failed to register auto-lock renewer: {e}")

                            try:
                                self._process_message(msg, receiver)
                            except AttributeError as e:
                                # Known azure-servicebus SDK bug: receiver._handler can become None
                                # This is a race condition where the handler is closed during message processing
                                logger.error(
                                    f"Receiver AttributeError (likely SDK bug - handler became None): {e}",
                                    exc_info=True,
                                )
                                # INTENTIONALLY NOT RE-RAISED: When the receiver is in an invalid state
                                # (handler is None), we cannot perform any operations on it (complete/abandon).
                                # Re-raising would crash the service. Instead, we continue processing other
                                # messages. This message's lock will expire and it will be retried.
                                # This is graceful degradation from an SDK bug, not masking application errors.
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                # In manual ack mode, abandon the message so it can be retried
                                if not self.auto_complete:
                                    try:
                                        receiver.abandon_message(msg)
                                    except AttributeError as abandon_error:
                                        # Receiver may be in invalid state - log but don't fail
                                        logger.error(
                                            f"Cannot abandon message - receiver AttributeError: {abandon_error}",
                                            exc_info=True,
                                        )
                                    except Exception as abandon_error:
                                        logger.error(f"Error abandoning message: {abandon_error}")

                    except AttributeError as e:
                        # Known azure-servicebus SDK bug: receiver._handler can become None
                        if self._consuming.is_set():
                            self._log_rate_limited(
                                f"Receiver AttributeError during message receive (likely SDK bug): {e}",
                                level="error",
                                exc_info=True
                            )
                        # Continue processing unless explicitly stopped
                    except Exception as e:
                        # Check for handler shutdown error
                        # Match the specific error message from Azure SDK
                        error_str = str(e).lower()
                        if (
                            "handler has already been shutdown" in error_str
                            or "handler already shutdown" in error_str
                        ):
                            # Re-raise to trigger reconnection logic in start_consuming
                            raise

                        # For other exceptions during message receive, log and continue
                        # to maintain existing behavior for transient errors
                        if self._consuming.is_set():
                            self._log_rate_limited(f"Error receiving messages: {e}", level="error")
                        # Continue processing unless explicitly stopped

        finally:
            try:
                if renewer is not None:
                    renewer.close()
            except AttributeError as e:
                logger.debug(f"AutoLockRenewer AttributeError during close: {e}")
            except Exception as e:
                logger.debug(f"Error closing auto-lock renewer: {e}")

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully."""
        if self._consuming.is_set():
            self._consuming.clear()
            logger.info("Stopping event consumption")

    def _log_rate_limited(self, message: str, level: str = "error", exc_info: bool = False) -> None:
        """Log a message with rate limiting to prevent spam.

        Thread-safe implementation using a lock to protect shared state.

        Args:
            message: The log message
            level: Log level (error, warning, info, debug)
            exc_info: Whether to include exception info
        """
        current_time = time.time()
        should_log = False

        with self._rate_limit_lock:
            if current_time - self._last_error_log_time >= self._error_log_interval:
                should_log = True
                self._last_error_log_time = current_time

        if should_log:
            log_func = getattr(logger, level, logger.error)
            log_func(message, exc_info=exc_info)
        else:
            # Log at debug level to avoid spam while still capturing for debugging
            logger.debug(f"[Rate-limited] {message}")

    def _process_message(self, msg: Any, receiver: Any) -> None:
        """Process a received message.

        Args:
            msg: ServiceBusReceivedMessage object
            receiver: ServiceBusReceiver object

        Note:
            This method handles AttributeError gracefully as the azure-servicebus SDK
            has a known bug where internal handlers can become None during message
            processing (see GitHub issues #35618, #36334).
        """
        try:
            # Parse message body from the received message (body is bytes)
            body_bytes = b"".join(section for section in msg.body)  # ServiceBus returns body as sections
            message_body = body_bytes.decode("utf-8")
            event = json.loads(message_body)

            # Extract event type
            event_type = event.get("event_type")

            if not event_type:
                logger.warning("Received message without event_type field")
                if not self.auto_complete:
                    try:
                        receiver.complete_message(msg)
                    except AttributeError as e:
                        logger.error(f"Cannot complete message - receiver AttributeError: {e}", exc_info=True)
                return

            # Find and call registered callback
            callback = self.callbacks.get(event_type)

            if callback:
                # Use callback_error pattern to separate callback exceptions from receiver AttributeErrors.
                # This ensures we can distinguish between:
                # 1. Callback failures (application errors) - should be re-raised
                # 2. Receiver AttributeErrors (SDK bug) - should be handled gracefully
                # Without this separation, a receiver AttributeError during complete_message would
                # incorrectly be caught as a callback error, masking the true cause.
                callback_error = None
                try:
                    callback(event)
                    logger.debug(f"Processed {event_type} event: {event.get('event_id')}")
                except Exception as e:
                    # Save callback error for later handling
                    callback_error = e
                    logger.error(f"Error in callback for {event_type}: {e}")

                # Complete or abandon message based on callback result
                if not self.auto_complete:
                    if callback_error is None:
                        # Callback succeeded - try to complete message
                        try:
                            receiver.complete_message(msg)
                        except AttributeError as e:
                            # Cannot complete - handler is in invalid state
                            # Log but don't re-raise as message was processed successfully
                            logger.error(f"Cannot complete message - receiver AttributeError: {e}", exc_info=True)
                            logger.warning("Message processed but not completed - will be redelivered")
                    else:
                        # Callback failed - try to abandon message for retry
                        try:
                            receiver.abandon_message(msg)
                        except AttributeError as abandon_error:
                            logger.error(
                                f"Cannot abandon message - receiver AttributeError: {abandon_error}", exc_info=True
                            )
                        except Exception as abandon_error:
                            logger.error(f"Error abandoning message: {abandon_error}")

                # Re-raise callback error after attempting to handle the message
                if callback_error is not None:
                    raise callback_error
            else:
                logger.debug(f"No callback registered for {event_type}")
                # Complete message even if no callback (to avoid reprocessing)
                if not self.auto_complete:
                    try:
                        receiver.complete_message(msg)
                    except AttributeError as e:
                        logger.error(f"Cannot complete message - receiver AttributeError: {e}", exc_info=True)

        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode message body as UTF-8: {e}")
            # Complete malformed messages to avoid blocking the queue
            if not self.auto_complete:
                try:
                    receiver.complete_message(msg)
                except AttributeError as complete_error:
                    logger.error(
                        f"Cannot complete malformed message - receiver AttributeError: {complete_error}",
                        exc_info=True,
                    )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
            # Complete malformed messages to avoid blocking the queue
            if not self.auto_complete:
                try:
                    receiver.complete_message(msg)
                except AttributeError as complete_error:
                    logger.error(
                        f"Cannot complete malformed message - receiver AttributeError: {complete_error}",
                        exc_info=True,
                    )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Let the exception propagate to the caller for error handling
            raise
