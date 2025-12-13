# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Event handler decorator for safe event processing with error handling."""

import logging
from typing import Callable, Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


def safe_event_handler(
    event_name: str = "event",
    error_reporter: Optional[Any] = None,
    on_error: Optional[Callable] = None,
):
    """Decorator for safe event handling with consistent error logging and reporting.
    
    Args:
        event_name: Name of the event being handled (for logging)
        error_reporter: Optional error reporter instance
        on_error: Optional callback function called when error occurs (receives self, error, event)
        
    Returns:
        Decorated function with error handling
        
    Example:
        @safe_event_handler("JSONParsed", error_reporter=self.error_reporter)
        def _handle_json_parsed(self, event: Dict[str, Any]):
            # Process event
            pass
            
        # With error callback:
        @safe_event_handler("MyEvent", on_error=lambda self, e, evt: self.failures += 1)
        def _handle_my_event(self, event: Dict[str, Any]):
            # Process event
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, event: Dict[str, Any]):
            try:
                return func(self, event)
            except Exception as e:
                logger.error(
                    f"Error handling {event_name} event: {e}",
                    exc_info=True
                )
                # Try to get error reporter from instance or use provided one
                reporter = error_reporter
                if reporter is None and hasattr(self, 'error_reporter'):
                    reporter = self.error_reporter
                
                if reporter:
                    reporter.report(e, context={"event": event, "event_name": event_name})
                
                # Call error callback if provided
                if on_error:
                    on_error(self, e, event)
        
        return wrapper
    return decorator
