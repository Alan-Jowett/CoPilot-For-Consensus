<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot SDK

Shared Python libraries for Copilot-for-Consensus microservices.

## Modules

Each module is self-contained with its own code, tests, documentation, and setup.py.

### [copilot_events](copilot_events/)

Event-driven communication infrastructure for microservices.

- **Purpose**: Event publishing and subscribing across services
- **Features**: RabbitMQ and in-memory implementations, event models
- **Installation**: `cd copilot_events && pip install -e .`
- **Documentation**: [copilot_events/README.md](copilot_events/README.md)

### [copilot_auth](copilot_auth/)

# Copilot Events SDK

A shared Python library for event publishing and subscribing across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Publisher Interface**: Common interface for all event publishers
- **Abstract Subscriber Interface**: Common interface for all event subscribers
- **RabbitMQ Implementation**: Production-ready RabbitMQ publisher and subscriber with persistent messages
- **No-op Implementation**: Testing publisher and subscriber that work in-memory
- **Event Models**: Common event data structures for system-wide consistency
- **Factory Pattern**: Simple factory functions for creating publishers and subscribers
- **Pluggable Schema Provider**: Load schemas via filesystem or any `DocumentStore` (Mongo via `copilot-storage`)

## Development

Each module can be developed and tested independently:

```bash
# Install and test copilot_events
cd copilot_events
pip install -e .[dev]
pytest tests/ -v

# Install and test copilot_auth
cd copilot_auth
pip install -e .[dev]
pytest tests/ -v
```

## Usage in Services

Services can depend on individual modules as needed:

**requirements.txt:**
```
copilot-events>=0.1.0
copilot-auth>=0.1.0
```

Or install from local development:
```bash
pip install -e sdk/copilot_events
pip install -e sdk/copilot_auth
```

### Using the Document-Store Schema Provider

Schemas can be loaded via the document store abstraction (Mongo implementation lives in `copilot-storage`):

```python
from copilot_events import DocumentStoreSchemaProvider

# Prefer context manager usage for automatic cleanup
with DocumentStoreSchemaProvider(
     mongo_uri="mongodb://admin:password@documentdb:27017/admin?authSource=admin",
     collection_name="event_schemas",
     database_name="copilot",  # optional; defaults to "copilot"
 ) as provider:
     schema = provider.get_schema("ArchiveIngested")
     event_types = provider.list_event_types()
```For tests, inject `InMemoryDocumentStore` from `copilot-storage` to avoid external services.

## Architecture

Each module follows a consistent structure:

```
module_name/
├── module_name/       # Package code
│   ├── __init__.py
│   └── ...
├── tests/            # Module-specific tests
│   └── test_*.py
├── examples/         # Example applications (optional)
│   └── *.py
├── README.md         # Module documentation
└── setup.py          # Module setup configuration
```

## Contributing

See [CONTRIBUTING.md](../documents/CONTRIBUTING.md) in the main repository.

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Installation

### For Development (Editable Mode)

From the copilot_events directory:

```bash
cd sdk/copilot_events
pip install -e .
```

### For Production

```bash
pip install copilot-events
```

## Usage

### Basic Publisher Creation

```python
from copilot_events import create_publisher

# Create RabbitMQ publisher
publisher = create_publisher(
    message_bus_type="rabbitmq",
    host="messagebus",
    port=5672,
    username="guest",
    password="guest"
)

# Connect and publish
publisher.connect()
publisher.publish(
    exchange="copilot.events",
    routing_key="archive.ingested",
    event={
        "event_type": "ArchiveIngested",
        "data": {"archive_id": "123", "status": "success"}
    }
)
publisher.disconnect()
```

### Using Event Models

```python
from copilot_events import ArchiveIngestedEvent, create_publisher

# Create event with auto-generated ID and timestamp
event = ArchiveIngestedEvent(
    data={
        "archive_id": "abc-123",
        "source_name": "ietf-quic",
        "file_path": "/data/archives/file.mbox",
        "file_hash_sha256": "abc123...",
    }
)

# Publish event
publisher = create_publisher(message_bus_type="rabbitmq")
publisher.connect()
publisher.publish(
    exchange="copilot.events",
    routing_key="archive.ingested",
    event=event.to_dict()
)
publisher.disconnect()
```

### Testing with NoopPublisher

```python
from copilot_events import create_publisher, NoopPublisher

# Create no-op publisher for testing
publisher = create_publisher(message_bus_type="noop")
publisher.connect()

# Publish events (stored in memory, not sent anywhere)
publisher.publish("copilot.events", "test.event", {"foo": "bar"})

# Access published events for assertions
assert len(publisher.published_events) == 1
assert publisher.published_events[0]["routing_key"] == "test.event"
```

### Subscribing to Events

```python
from copilot_events import create_subscriber

# Create RabbitMQ subscriber
subscriber = create_subscriber(
    message_bus_type="rabbitmq",
    host="messagebus",
    port=5672,
    username="guest",
    password="guest"
)

# Connect to message bus
subscriber.connect()

# Define callback for handling events
def handle_archive_ingested(event):
    print(f"Received event: {event['event_id']}")
    archive_id = event['data']['archive_id']
    print(f"Processing archive: {archive_id}")

# Subscribe to event type
subscriber.subscribe(
    event_type="ArchiveIngested",
    callback=handle_archive_ingested,
    routing_key="archive.ingested"  # Optional, auto-generated if not provided
)

# Start consuming (blocks)
try:
    subscriber.start_consuming()
except KeyboardInterrupt:
    subscriber.stop_consuming()
    subscriber.disconnect()
```

### Testing with NoopSubscriber

```python
from copilot_events import create_subscriber

# Create no-op subscriber for testing
subscriber = create_subscriber(message_bus_type="noop")
subscriber.connect()

# Register callback
received_events = []
subscriber.subscribe(
    event_type="TestEvent",
    callback=lambda e: received_events.append(e)
)

# Manually inject event for testing
subscriber.inject_event({
    "event_type": "TestEvent",
    "event_id": "123",
    "data": {"test": "value"}
})

# Verify callback was called
assert len(received_events) == 1
assert received_events[0]["event_id"] == "123"
```

## Architecture

### Publisher Interface

The `EventPublisher` abstract base class defines the contract:

- `connect() -> bool`: Establish connection to message bus
- `disconnect() -> None`: Close connection
- `publish(exchange, routing_key, event) -> bool`: Publish an event

### Subscriber Interface

The `EventSubscriber` abstract base class defines the contract:

- `connect() -> None`: Establish connection to message bus
- `disconnect() -> None`: Close connection
- `subscribe(event_type, callback, routing_key) -> None`: Register event handler
- `start_consuming() -> None`: Start processing events (blocking)
- `stop_consuming() -> None`: Stop processing events

### Implementations

#### RabbitMQPublisher

Production publisher implementation with:
- Persistent messages (delivery_mode=2)
- Durable exchanges
- Connection retry logic
- JSON serialization
- Comprehensive logging

#### RabbitMQSubscriber

Production subscriber implementation with:
- Topic-based routing
- Manual acknowledgment support
- Error handling with requeue
- Automatic routing key generation
- Callback-based event dispatch

#### NoopPublisher

Testing publisher implementation with:
- In-memory event storage
- Query and filter capabilities
- Zero external dependencies
- Fast execution for unit tests

#### NoopSubscriber

Testing subscriber implementation with:
- Manual event injection
- In-memory callback registry
- Subscription introspection
- Zero external dependencies

## Error Reporting

The SDK provides an abstraction layer for error reporting that enables services to emit structured error events to different backends (e.g., Sentry, console, file logs) and support consistent error tracking across environments.

### Basic Usage

```python
from copilot_events import create_error_reporter

# Create a console error reporter (default)
error_reporter = create_error_reporter(reporter_type="console")

# Report an exception with context
try:
    # Some operation
    risky_operation()
except Exception as e:
    error_reporter.report(e, context={
        "user_id": "123",
        "operation": "risky_operation",
        "request_id": "abc-def"
    })

# Capture a message without an exception
error_reporter.capture_message(
    "Configuration validation failed",
    level="warning",
    context={"config_file": "app.yaml"}
)
```

### Error Reporter Interface

The `ErrorReporter` abstract base class defines:

- `report(error: Exception, context: dict = None)`: Report an exception with optional context
- `capture_message(message: str, level: str = "error", context: dict = None)`: Capture a message without an exception

Supported levels: `debug`, `info`, `warning`, `error`, `critical`

### Implementations

#### ConsoleErrorReporter

Default error reporter that logs to stdout using Python's logging system:
- Structured error information
- Stack trace logging (at DEBUG level)
- Context as key-value pairs
- Configurable logger name

```python
from copilot_events import ConsoleErrorReporter

reporter = ConsoleErrorReporter(logger_name="my_service")
```

#### SilentErrorReporter

Testing error reporter that stores errors in memory:
- Zero output or side effects
- In-memory storage of errors and messages
- Query and filter capabilities
- Perfect for unit tests

```python
from copilot_events import SilentErrorReporter

reporter = SilentErrorReporter()

# Later in tests
assert reporter.has_errors()
errors = reporter.get_errors(error_type="ValueError")
messages = reporter.get_messages(level="error")
reporter.clear()
```

#### SentryErrorReporter

Production error reporter for cloud-based error tracking (scaffold for future use):
- Requires `sentry-sdk` package
- Environment-aware reporting
- Context propagation to Sentry
- Level mapping to Sentry severity

```python
from copilot_events import SentryErrorReporter

# Note: Requires pip install sentry-sdk
reporter = SentryErrorReporter(
    dsn="https://...@sentry.io/...",
    environment="production"
)
```

### Factory Pattern

Use the factory function to select the reporter based on configuration:

```python
from copilot_events import create_error_reporter
import os

# Select reporter from environment variable
reporter_type = os.getenv("ERROR_REPORTER_TYPE", "console")
sentry_dsn = os.getenv("SENTRY_DSN")

reporter = create_error_reporter(
    reporter_type=reporter_type,
    dsn=sentry_dsn,
    environment="production"
)
```

### Service Integration Example

```python
from copilot_events import create_error_reporter, create_publisher

class MyService:
    def __init__(self, config):
        self.publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host
        )
        
        self.error_reporter = create_error_reporter(
            reporter_type=config.error_reporter_type,
            dsn=config.sentry_dsn
        )
    
    def process_data(self, data):
        try:
            # Process data
            result = self._do_processing(data)
            self.publisher.publish("exchange", "key", result)
        except Exception as e:
            # Report error with context
            self.error_reporter.report(e, context={
                "operation": "process_data",
                "data_id": data.get("id")
            })
            raise
```

### Event Models

Event models provide:
- Auto-generated UUIDs
- ISO 8601 timestamps
- Consistent structure
- Type safety
- Easy serialization

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Coverage

```bash
pytest tests/ --cov=copilot_events --cov-report=html
```

### Linting

```bash
pylint copilot_events/
```

## Requirements

- Python 3.11+
- pika (for RabbitMQ)

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
