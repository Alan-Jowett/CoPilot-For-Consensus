# Copilot Events SDK

A shared Python library for event publishing across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Publisher Interface**: Common interface for all event publishers
- **RabbitMQ Implementation**: Production-ready RabbitMQ publisher with persistent messages
- **No-op Implementation**: Testing publisher that stores events in memory
- **Event Models**: Common event data structures for system-wide consistency
- **Factory Pattern**: Simple factory function for creating publishers

## Installation

### For Development (Editable Mode)

From the root of the repository:

```bash
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

## Architecture

### Publisher Interface

The `EventPublisher` abstract base class defines the contract:

- `connect() -> bool`: Establish connection to message bus
- `disconnect() -> None`: Close connection
- `publish(exchange, routing_key, event) -> bool`: Publish an event

### Implementations

#### RabbitMQPublisher

Production implementation with:
- Persistent messages (delivery_mode=2)
- Durable exchanges
- Connection retry logic
- JSON serialization
- Comprehensive logging

#### NoopPublisher

Testing implementation with:
- In-memory event storage
- Query and filter capabilities
- Zero external dependencies
- Fast execution for unit tests

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
