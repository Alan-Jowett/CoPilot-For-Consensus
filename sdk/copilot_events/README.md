# Copilot Events SDK

A shared Python library for event publishing and subscribing across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Publisher Interface**: Common interface for all event publishers
- **Abstract Subscriber Interface**: Common interface for all event subscribers
- **Abstract Document Store Interface**: Common interface for NoSQL document storage backends
- **RabbitMQ Implementation**: Production-ready RabbitMQ publisher and subscriber with persistent messages
- **MongoDB Implementation**: Production-ready MongoDB document store
- **No-op Implementation**: Testing publisher and subscriber that work in-memory
- **In-Memory Document Store**: Testing document store that works in-memory
- **Event Models**: Common event data structures for system-wide consistency
- **Factory Pattern**: Simple factory functions for creating publishers, subscribers, and document stores

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

### Event Models

Event models provide:
- Auto-generated UUIDs
- ISO 8601 timestamps
- Consistent structure
- Type safety
- Easy serialization

## Document Storage

### Using Document Stores

```python
from copilot_events import create_document_store

# Create in-memory store for testing/local dev
store = create_document_store(store_type="inmemory")
store.connect()

# Insert document
doc_id = store.insert_document("users", {
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})

# Get document by ID
user = store.get_document("users", doc_id)
print(user["name"])  # Alice

# Query documents
results = store.query_documents("users", {"age": 30})

# Update document
store.update_document("users", doc_id, {"age": 31})

# Delete document
store.delete_document("users", doc_id)

store.disconnect()
```

### Using MongoDB Store

```python
from copilot_events import create_document_store

# Create MongoDB store
store = create_document_store(
    store_type="mongodb",
    host="mongodb",
    port=27017,
    username="user",
    password="pass",
    database="copilot_db"
)

# Connect and use
if store.connect():
    doc_id = store.insert_document("archives", {
        "archive_id": "abc-123",
        "status": "processed",
        "timestamp": "2025-01-01T00:00:00Z"
    })
    store.disconnect()
```

### Document Store Interface

The `DocumentStore` abstract base class defines the contract:

- `connect() -> bool`: Establish connection to the store
- `disconnect() -> None`: Close connection
- `insert_document(collection, doc) -> str`: Insert a document and return its ID
- `get_document(collection, doc_id) -> Optional[Dict]`: Retrieve a document by ID
- `query_documents(collection, filter_dict, limit) -> List[Dict]`: Query documents matching filter
- `update_document(collection, doc_id, patch) -> bool`: Update a document
- `delete_document(collection, doc_id) -> bool`: Delete a document

### Implementations

#### MongoDocumentStore

Production MongoDB implementation with:
- Connection pooling via pymongo
- Automatic ObjectId handling
- Error handling and logging
- Support for authentication
- Standard MongoDB query syntax

#### InMemoryDocumentStore

Testing implementation with:
- In-memory dict-based storage
- Simple equality-based filtering
- Fast execution for unit tests
- Utility methods for clearing data
- Zero external dependencies

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
- pymongo (for MongoDB)

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
