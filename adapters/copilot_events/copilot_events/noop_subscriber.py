# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""No-op event subscriber for testing."""

import logging
from typing import Callable, Dict, Any, List

from .subscriber import EventSubscriber


logger = logging.getLogger(__name__)


class NoopSubscriber(EventSubscriber):
    """No-op implementation of EventSubscriber for testing.
    
    Stores subscriptions and allows manual event injection for testing
    event handlers without requiring a real message bus.
    """

    def __init__(self):
        """Initialize noop subscriber."""
        self.connected = False
        self.consuming = False
        self.callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.routing_keys: Dict[str, str] = {}

    def connect(self) -> bool:
        """Simulate connection to message bus.
        
        Returns:
            bool: Always returns True
        """
        self.connected = True
        logger.debug("NoopSubscriber connected")
        return True

    def disconnect(self) -> None:
        """Simulate disconnection from message bus."""
        self.connected = False
        self.consuming = False
        logger.debug("NoopSubscriber disconnected")

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        routing_key: str = None
    ) -> None:
        """Register a callback for an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is received
            routing_key: Optional routing key (stored but not used)
        """
        self.callbacks[event_type] = callback
        self.routing_keys[event_type] = routing_key
        logger.debug(f"NoopSubscriber subscribed to {event_type}")

    def start_consuming(self) -> None:
        """Mark subscriber as consuming.
        
        Note: NoopSubscriber doesn't actually consume. Use inject_event()
        to manually trigger callbacks for testing.
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
        self.consuming = True
        logger.debug("NoopSubscriber started consuming")

    def stop_consuming(self) -> None:
        """Stop consuming events."""
        self.consuming = False
        logger.debug("NoopSubscriber stopped consuming")

    def inject_event(self, event: Dict[str, Any]) -> None:
        """Manually inject an event to trigger callbacks.
        
        This is useful for testing event handlers without a real message bus.
        
        Args:
            event: Event dictionary with at least 'event_type' field
            
        Raises:
            ValueError: If event doesn't have 'event_type' field
        """
        event_type = event.get('event_type')
        
        if not event_type:
            raise ValueError("Event must have 'event_type' field")
        
        callback = self.callbacks.get(event_type)
        
        if callback:
            callback(event)
            logger.debug(f"NoopSubscriber injected {event_type} event")
        else:
            logger.debug(f"No callback for {event_type}")

    def get_subscriptions(self) -> List[str]:
        """Get list of subscribed event types.
        
        Returns:
            List of event types that have registered callbacks
        """
        return list(self.callbacks.keys())

    def clear_subscriptions(self) -> None:
        """Clear all registered callbacks."""
        self.callbacks.clear()
        self.routing_keys.clear()
        logger.debug("NoopSubscriber cleared all subscriptions")
