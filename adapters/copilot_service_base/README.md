# Copilot Service Base

Shared utilities and base classes for Copilot microservices.

## Overview

This package provides common patterns and utilities extracted from repetitive code across microservices:

- **BaseService**: Abstract base class with common functionality (stats tracking, metrics, error reporting)
- **retry_with_backoff**: Utility function for retry logic with exponential backoff
- **safe_event_handler**: Decorator for safe event handling with error reporting

## Features

### Retry Logic with Exponential Backoff

The `retry_with_backoff` function provides a reusable retry mechanism:

```python
from copilot_service_base import retry_with_backoff

def process_data():
    # Your processing logic
    pass

result = retry_with_backoff(
    process_data,
    max_attempts=3,
    backoff_seconds=5,
    max_backoff_seconds=60,
    on_retry=lambda e, attempt: logger.info(f"Retry {attempt}: {e}"),
    on_failure=lambda e, attempt: logger.error(f"Failed after {attempt} attempts"),
)
```

Features:
- Exponential backoff with configurable base and maximum
- Callbacks for retry and failure events
- Type-safe return values

### Safe Event Handler Decorator

The `safe_event_handler` decorator wraps event handlers with error handling:

```python
from copilot_service_base import safe_event_handler

class MyService:
    def __init__(self, error_reporter):
        self.error_reporter = error_reporter
    
    @safe_event_handler("JSONParsed")
    def _handle_json_parsed(self, event):
        # Process event
        # Errors are automatically logged, reported, and re-raised (for message requeue)
        pass
    
    # To swallow errors instead of re-raising:
    @safe_event_handler("MyEvent", reraise=False)
    def _handle_my_event(self, event):
        # Errors logged but not re-raised
        pass
```

Features:
- Automatic error logging with event name
- Error reporter integration
- Event context in error reports
- Re-raises exceptions by default (for message requeue in event-driven systems)
- Optional `reraise=False` to swallow exceptions
- Error reporter integration
- Event context in error reports

### Base Service Class

The `BaseService` class provides common functionality for all services:

```python
from copilot_service_base import BaseService

class MyService(BaseService):
    def start(self):
        self.subscriber.subscribe(
            event_type="MyEvent",
            callback=self._handle_event,
        )
    
    def process(self):
        self.increment_processed()
        self.record_metric("my_metric", value=1.0, tags={"status": "success"})
```

Features:
- Built-in stats tracking (processed count, failures, processing time)
- Metrics collection helpers
- Error reporting helpers
- Standard get_stats() implementation

## Usage

Install as a dependency in your service:

```bash
pip install -e /path/to/adapters/copilot_service_base
```

## Testing

Run tests:

```bash
pytest
```

## Benefits

- **Reduced Code Duplication**: Common patterns extracted into reusable utilities
- **Consistent Error Handling**: Standardized error handling across all services
- **Easier Maintenance**: Bug fixes and improvements apply to all services
- **Better Testability**: Utilities are independently tested
