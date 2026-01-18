# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validating event publisher that enforces schema validation."""

import logging
from typing import Any

from .publisher import EventPublisher

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when event validation fails.

    Attributes:
        event_type: The event type that failed validation
        errors: List of validation error messages
    """

    def __init__(self, event_type: str, errors: list[str]):
        self.event_type = event_type
        self.errors = errors
        error_msg = f"Validation failed for event type '{event_type}': {'; '.join(errors)}"
        super().__init__(error_msg)


class ValidatingEventPublisher(EventPublisher):
    """Event publisher that validates events against schemas before publishing.

    This is a decorator/wrapper around any EventPublisher implementation that
    adds schema validation. It uses a SchemaProvider to retrieve schemas and
    validates events before delegating to the underlying publisher.

    Example:
        >>> from copilot_message_bus import create_publisher
        >>> from copilot_schema_validation import FileSchemaProvider
        >>>
        >>> base_publisher = create_publisher("noop")
        >>> schema_provider = FileSchemaProvider()
        >>> validating_publisher = ValidatingEventPublisher(
        ...     publisher=base_publisher,
        ...     schema_provider=schema_provider
        ... )
        >>>
        >>> event = {
        ...     "event_type": "ArchiveIngested",
        ...     "event_id": "123",
        ...     "timestamp": "2025-01-01T00:00:00Z",
        ...     "version": "1.0",
        ...     "data": {"archive_id": "abc"}
        ... }
        >>> validating_publisher.publish("copilot.events", "archive.ingested", event)
    """

    def __init__(
        self,
        publisher: EventPublisher,
        schema_provider: Any | None = None,
        strict: bool = True,
    ):
        """Initialize the validating publisher.

        Args:
            publisher: Underlying EventPublisher to delegate to
            schema_provider: SchemaProvider for retrieving schemas (optional)
            strict: If True, raise ValidationError on validation failure.
                   If False, log error and allow publish to proceed.
        """
        self._publisher = publisher
        self._schema_provider = schema_provider
        self._strict = strict

    def _validate_event(self, event: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate an event against its schema.

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
            logger.error("Failed to retrieve schema for event type '%s': %s", event_type, exc)
            return False, [f"Schema retrieval failed: {exc}"]

        # Validate event against schema
        try:
            from copilot_schema_validation import (
                validate_json,  # type: ignore[import-not-found] # pylint: disable=import-outside-toplevel
            )

            is_valid, errors = validate_json(event, schema, schema_provider=self._schema_provider)
            return is_valid, errors
        except Exception as exc:
            logger.error("Validation failed with exception: %s", exc)
            return False, [f"Validation exception: {exc}"]

    def publish(self, exchange: str, routing_key: str, event: dict[str, Any]) -> None:
        """Publish an event after validating it against its schema.

        Args:
            exchange: Exchange name (e.g., "copilot.events")
            routing_key: Routing key (e.g., "archive.ingested")
            event: Event data as dictionary

        Raises:
            ValidationError: If strict=True and validation fails
            Exception: If publishing fails (propagated from underlying publisher)
        """
        # Validate event
        is_valid, errors = self._validate_event(event)

        if not is_valid:
            event_type = event.get("event_type", "unknown")

            if self._strict:
                # In strict mode, raise exception
                raise ValidationError(event_type, errors)

            # In non-strict mode, log warning and continue
            logger.warning("Event validation failed for '%s' but continuing in non-strict mode: %s", event_type, errors)

        # Delegate to underlying publisher
        self._publisher.publish(exchange, routing_key, event)

    def connect(self) -> None:
        """Connect to the message bus.

        Raises:
            Exception: If connection fails for any reason
        """
        self._publisher.connect()

    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        self._publisher.disconnect()

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to underlying publisher for test utilities.

        This allows tests to access attributes like 'published_events' on
        the wrapped NoopPublisher while using the validating wrapper.
        """
        return getattr(self._publisher, name)
