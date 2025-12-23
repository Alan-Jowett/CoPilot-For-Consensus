# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""No-op event publisher for testing."""

import logging
from typing import Dict, Any, List

from .publisher import EventPublisher

logger = logging.getLogger(__name__)


class NoopPublisher(EventPublisher):
    """No-op publisher for testing that stores events in memory."""

    def __init__(self):
        """Initialize no-op publisher."""
        self.published_events: List[Dict[str, Any]] = []
        self.connected = False

    def connect(self) -> None:
        """Pretend to connect (always succeeds)."""
        self.connected = True
        logger.debug("NoopPublisher: connected")

    def disconnect(self) -> None:
        """Pretend to disconnect."""
        self.connected = False
        logger.debug("NoopPublisher: disconnected")

    def publish(self, exchange: str, routing_key: str, event: Dict[str, Any]) -> None:
        """Store event without publishing to a real message bus.

        Args:
            exchange: Exchange name
            routing_key: Routing key
            event: Event data as dictionary
        """
        self.published_events.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "event": event,
            }
        )
        logger.debug(
            f"NoopPublisher: published {event.get('event_type')} to {exchange}/{routing_key}"
        )

    def clear_events(self) -> None:
        """Clear all stored events (useful for testing)."""
        self.published_events.clear()

    def get_events(self, event_type: str = None) -> List[Dict[str, Any]]:
        """Get stored events, optionally filtered by event type.

        Args:
            event_type: Optional event type to filter by

        Returns:
            List of published events
        """
        if event_type is None:
            return self.published_events
        return [
            e for e in self.published_events
            if e["event"].get("event_type") == event_type
        ]
