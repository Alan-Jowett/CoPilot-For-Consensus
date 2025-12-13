# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validating event subscriber that enforces schema validation."""

from typing import Dict, Any, Optional, Callable, List, Tuple
import logging

from .subscriber import EventSubscriber

logger = logging.getLogger(__name__)


class SubscriberValidationError(Exception):
    """Exception raised when received event validation fails.

    Attributes:
        event_type: The event type that failed validation
        errors: List of validation error messages
    """

    def __init__(self, event_type: str, errors: List[str]):
        self.event_type = event_type
        self.errors = errors
        error_msg = f"Received event validation failed for type '{event_type}': {'; '.join(errors)}"
        super().__init__(error_msg)


class ValidatingEventSubscriber(EventSubscriber):
    """Event subscriber that validates received events against schemas.

    This is a decorator/wrapper around any EventSubscriber implementation that
    adds schema validation. It uses a SchemaProvider to retrieve schemas and
    validates events before passing them to the registered callbacks.

    Example:
        >>> from copilot_events import create_subscriber
        >>> from copilot_schema_validation import FileSchemaProvider
        >>>
        >>> base_subscriber = create_subscriber("rabbitmq", host="localhost")
        >>> schema_provider = FileSchemaProvider()
        >>> validating_subscriber = ValidatingEventSubscriber(
        ...     subscriber=base_subscriber,
        ...     schema_provider=schema_provider
        ... )
        >>>
        >>> def on_archive_ingested(event):
        ...     print(f"Archive ingested: {event['data']['archive_id']}")
        >>>
        >>> validating_subscriber.subscribe(
        ...     event_type="ArchiveIngested",
        ...     callback=on_archive_ingested
        ... )
        >>> validating_subscriber.start_consuming()
    """

    def __init__(
        self,
        subscriber: EventSubscriber,
        schema_provider: Optional[Any] = None,
        strict: bool = True,
    ):
        """Initialize the validating subscriber.

        Args:
            subscriber: Underlying EventSubscriber to delegate to
            schema_provider: SchemaProvider for retrieving schemas (optional)
            strict: If True, raise SubscriberValidationError on validation failure.
                   If False, log error and skip callback invocation.
        """
        self._subscriber = subscriber
        self._schema_provider = schema_provider
        self._strict = strict
        self._callbacks: Dict[str, Callable] = {}

    def _validate_event(self, event: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a received event against its schema.

        Args:
            event: Event dictionary to validate

        Returns:
            Tuple of (is_valid, errors). is_valid is True if event conforms
            to schema or if no schema provider is configured. errors is a list
            of validation error messages.
        """
        # If no schema provider, skip validation
        if self._schema_provider is None:
            logger.debug("No schema provider configured, skipping validation")
            return True, []

        # Get event type
        event_type = event.get("event_type")
        if not event_type:
            return False, ["Event missing required 'event_type' field"]

        # Get schema for event type
        try:
            schema = self._schema_provider.get_schema(event_type)
            if schema is None:
                logger.warning("No schema found for event type '%s'", event_type)
                # If schema not found, allow event to pass in non-strict mode
                if not self._strict:
                    return True, []
                return False, [f"No schema found for event type '{event_type}'"]
        except Exception as exc:
            logger.error(
                "Failed to retrieve schema for event type '%s': %s",
                event_type, exc
            )
            return False, [f"Schema retrieval failed: {exc}"]

        # Validate event against schema
        try:
            from copilot_schema_validation import validate_json  # pylint: disable=import-outside-toplevel
            is_valid, errors = validate_json(event, schema, schema_provider=self._schema_provider)
            return is_valid, errors
        except Exception as exc:
            logger.error("Validation failed with exception: %s", exc)
            return False, [f"Validation exception: {exc}"]

    def _validating_callback_wrapper(self, event_type: str, original_callback: Callable) -> Callable:
        """Create a wrapper callback that validates events before invoking the original callback.

        Args:
            event_type: The event type being subscribed to
            original_callback: The original callback function

        Returns:
            A wrapper function that validates and then calls the original callback
        """
        def wrapper(event: Dict[str, Any]) -> None:
            # Validate event
            is_valid, errors = self._validate_event(event)

            if not is_valid:
                if self._strict:
                    # In strict mode, raise exception
                    raise SubscriberValidationError(event_type, errors)

                # In non-strict mode, log warning and skip callback
                logger.warning(
                    "Received event validation failed for '%s' but skipping in non-strict mode: %s",
                    event_type, errors
                )
                return

            # Call the original callback
            try:
                original_callback(event)
            except Exception as exc:
                logger.error("Error in callback for event type '%s': %s", event_type, exc, exc_info=True)
                raise

        return wrapper

    def connect(self) -> bool:
        """Connect to the message bus.

        Returns:
            bool: True if connection successful, False otherwise
        """
        return self._subscriber.connect()

    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        self._subscriber.disconnect()

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        routing_key: str = None,
        exchange: str = None,
    ) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to (e.g., "ArchiveIngested")
            callback: Function to call when an event is received
            routing_key: Optional routing key pattern for filtering events
                        (e.g., "archive.ingested", "archive.*")
            exchange: Optional exchange name (for compatibility)
        """
        # Store the original callback
        self._callbacks[event_type] = callback

        # Create validating wrapper
        validating_callback = self._validating_callback_wrapper(event_type, callback)

        # Subscribe with the validating wrapper
        # Support both old and new parameter names for flexibility
        kwargs = {"callback": validating_callback}
        if event_type:
            kwargs["event_type"] = event_type
        if routing_key:
            kwargs["routing_key"] = routing_key
        if exchange:
            kwargs["exchange"] = exchange

        self._subscriber.subscribe(**kwargs)

    def start_consuming(self) -> None:
        """Start consuming events.

        This method blocks and processes events as they arrive,
        calling the registered callbacks (with validation).
        """
        self._subscriber.start_consuming()

    def stop_consuming(self) -> None:
        """Stop consuming events gracefully."""
        self._subscriber.stop_consuming()
