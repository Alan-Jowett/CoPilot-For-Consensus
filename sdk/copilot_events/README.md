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

### Event System
=======
# Copilot-for-Consensus SDK

This directory contains shared Python libraries for the Copilot-for-Consensus microservices system.

## Modules

=======
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
=======
### copilot_events

Event publishing and subscribing library for inter-service communication.

**Features:**
- Abstract publisher/subscriber interfaces
- RabbitMQ implementation for production
- No-op implementation for testing
- Event models for system-wide consistency

**Documentation:** [copilot_events/README.md](copilot_events/README.md)

<<<<<<< HEAD
### copilot_config

Configuration management library for standardized config access.

**Features:**
- Abstract configuration provider interface
- Environment variable provider for production
- Static provider for testing
- Type-safe configuration access (bool, int, string)
=======
=======
>>>>>>> a1f32d6 (Editing)

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

### ConfigProvider Interface

The `ConfigProvider` abstract base class defines the contract for configuration access:

- `get(key, default=None) -> Any`: Get a configuration value
- `get_bool(key, default=False) -> bool`: Get a boolean configuration value
- `get_int(key, default=0) -> int`: Get an integer configuration value

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

#### EnvConfigProvider

Production configuration provider implementation with:
- Reads from environment variables (os.environ)
- Smart type conversion for bool and int types
- Accepts various boolean formats ("true", "1", "yes", "on" for True)
- Returns defaults for missing or invalid values
- Zero external dependencies

#### StaticConfigProvider

Testing configuration provider implementation with:
- Accepts hardcoded configuration dictionary
- Supports native Python types (bool, int, str)
- Includes `set()` method for dynamic updates
- Perfect for unit testing without environment variable side effects
- Isolated from actual system environment

### Event Models

Event models provide:
- Auto-generated UUIDs
- ISO 8601 timestamps
- Consistent structure
- Type safety
- Easy serialization
<<<<<<< HEAD
========
**Documentation:** [copilot_config/README.md](copilot_config/README.md)
=======
>>>>>>> a1f32d6 (Editing)

## Development

Each module is self-contained with its own:
- Source code in `<module_name>/<module_name>/`
- Tests in `<module_name>/tests/`
- Documentation in `<module_name>/README.md`
- Setup configuration in `<module_name>/setup.py`

### Installing a Module

```bash
cd <module_name>
pip install -e .  # Development mode
# or
pip install -e ".[dev]"  # With development dependencies
```

### Running Tests

```bash
cd <module_name>
pytest tests/ -v
```

## Usage

### In Services

Services can import from these modules directly:

```python
# Import events library
from copilot_events import create_publisher, ArchiveIngestedEvent
```

### In Tests

Both modules provide testing implementations:

```python
# Use no-op publisher for testing
from copilot_events import NoopPublisher
```

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
See [../documents/CONTRIBUTING.md](../documents/CONTRIBUTING.md) for contribution guidelines.

## License

All modules are licensed under the MIT License. See [../LICENSE](../LICENSE) for details.
=======
## Architecture
