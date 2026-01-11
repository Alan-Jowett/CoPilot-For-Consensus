# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract base classes for message bus publishers and subscribers."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class EventPublisher(ABC):
    """Abstract base class for event publishers."""

    @abstractmethod
    def publish(self, exchange: str, routing_key: str, event: dict[str, Any]) -> None:
        """Publish an event to the message bus.

        Args:
            exchange: Exchange name (e.g., "copilot.events")
            routing_key: Routing key (e.g., "archive.ingested")
            event: Event data as dictionary

        Raises:
            Exception: If publishing fails for any reason
        """
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the message bus.

        Raises:
            Exception: If connection fails for any reason
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass


class EventSubscriber(ABC):
    """Abstract base class for event subscribers.

    Provides a common interface for subscribing to and consuming events
    from the message bus. Implementations should handle the specifics
    of connecting to and consuming from the message bus.
    """

    @abstractmethod
    def connect(self) -> None:
        """Connect to the message bus.

        Raises:
            Exception: If connection fails for any reason
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass

    @abstractmethod
    def subscribe(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], None],
        routing_key: str | None = None,
        exchange: str | None = None,
    ) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to (e.g., "ArchiveIngested")
            callback: Function to call when an event is received
            routing_key: Optional routing key pattern for filtering events
                        (e.g., "archive.ingested", "archive.*")
            exchange: Optional exchange name (for subscribers that support it)
        """
        pass

    @abstractmethod
    def start_consuming(self) -> None:
        """Start consuming events.

        This method should block and process events as they arrive,
        calling the registered callbacks.
        """
        pass

    @abstractmethod
    def stop_consuming(self) -> None:
        """Stop consuming events gracefully."""
        pass
