<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Adapter

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

# Copilot Events Adapter

A shared Python library for event publishing and subscribing across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Publisher Interface**: Common interface for all event publishers
- **Abstract Subscriber Interface**: Common interface for all event subscribers
- **RabbitMQ Implementation**: Production-ready RabbitMQ publisher and subscriber with persistent messages and guaranteed delivery
- **Azure Service Bus Implementation**: Production-ready Azure Service Bus publisher and subscriber with support for queues, topics, and managed identity
- **No-op Implementation**: Testing publisher and subscriber that work in-memory
- **Event Models**: Common event data structures for system-wide consistency
- **Factory Pattern**: Simple factory functions for creating publishers and subscribers
- **Schema Validation**: ValidatingEventPublisher wrapper for enforcing schema validation on published events
- **Publisher Confirms**: Guaranteed message delivery with broker acknowledgments
- **Queue Pre-declaration**: Ensures queues exist before publishing to avoid message loss

## Persistent Messaging Guarantees

The RabbitMQ implementation provides production-quality message durability:

1. **Durable Queues**: All queues survive broker restarts (`durable=True`, `auto_delete=False`, `exclusive=False`)
2. **Persistent Messages**: All messages written to disk (`delivery_mode=2`)
3. **Publisher Confirms**: Broker acknowledges message persistence before returning success
4. **Pre-declared Queues**: Queues created before messages are published (via `definitions.json` or `declare_queue()`)
5. **Unroutable Detection**: Publisher detects messages sent to non-existent queues (`mandatory=True`)

These features ensure:
- Messages survive RabbitMQ restarts
- No loss when consumer services are offline
- No silent drops when queues are missing
- Full compliance with RabbitMQ persistence best practices

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
pip install -e adapters/copilot_events
pip install -e adapters/copilot_auth
```

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

See [CONTRIBUTING.md](../../CONTRIBUTING.md) in the main repository.

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Installation

### For Development (Editable Mode)

From the copilot_events directory:

```bash
cd adapters/copilot_events
pip install -e .
```

### For Production

```bash
pip install copilot-events
```

## Usage

### Basic Publisher Creation

```python
from copilot_message_bus import create_publisher

# Create RabbitMQ publisher
publisher = create_publisher(
    message_bus_type="rabbitmq",
    host="messagebus",
    port=5672,
    username="guest",
    password="guest"
)

# Create Azure Service Bus publisher (with connection string)
publisher = create_publisher(
    message_bus_type="azureservicebus",
    connection_string="Endpoint=sb://namespace.servicebus.windows.net/;...",
    queue_name="copilot-events"
)

# Create Azure Service Bus publisher (with managed identity)
publisher = create_publisher(
    message_bus_type="azureservicebus",
    fully_qualified_namespace="namespace.servicebus.windows.net",
    topic_name="copilot-events",
    use_managed_identity=True
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
from copilot_message_bus import ArchiveIngestedEvent, create_publisher

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
from copilot_message_bus import create_publisher, NoopPublisher

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
from copilot_message_bus import create_subscriber

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
from copilot_message_bus import create_subscriber

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

### Validating Events with Schema Validation

The `ValidatingEventPublisher` wrapper enforces schema validation before publishing:

```python
from copilot_message_bus import create_publisher, ValidatingEventPublisher
from copilot_schema_validation import FileSchemaProvider

# Create base publisher
base_publisher = create_publisher("rabbitmq", host="messagebus")
base_publisher.connect()

# Create schema provider (loads schemas from filesystem or database)
schema_provider = FileSchemaProvider()

# Wrap publisher with validation
validating_publisher = ValidatingEventPublisher(
    publisher=base_publisher,
    schema_provider=schema_provider,
    strict=True  # Raise error on validation failure
)

# Valid event passes validation
valid_event = {
    "event_type": "ArchiveIngested",
    "event_id": "a1b2c3d4e5f6789",
    "timestamp": "2025-12-11T00:00:00Z",
    "version": "1.0",
    "data": {
        "archive_id": "archive-123",
        "source_name": "ietf-quic",
        "file_path": "/data/archives/quic.mbox"
    }
}
validating_publisher.publish("copilot.events", "archive.ingested", valid_event)

# Invalid event raises ValidationError in strict mode
invalid_event = {
    "event_type": "ArchiveIngested",
    "event_id": "123",
    "timestamp": "2025-12-11T00:00:00Z",
    "version": "1.0",
    "data": {}  # Missing required fields
}

try:
    validating_publisher.publish("copilot.events", "archive.ingested", invalid_event)
except ValidationError as e:
    print(f"Validation failed: {e.errors}")

# Non-strict mode: logs warning but allows publishing
permissive_publisher = ValidatingEventPublisher(
    publisher=base_publisher,
    schema_provider=schema_provider,
    strict=False  # Log warning but continue
)
permissive_publisher.publish("copilot.events", "archive.ingested", invalid_event)
```

See [examples/validating_publisher_example.py](examples/validating_publisher_example.py) for a complete demonstration.

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
- Durable exchanges and queues
- Publisher confirms for guaranteed delivery
- Queue pre-declaration support
- Mandatory flag to detect unroutable messages
- Connection retry logic
- JSON serialization
- Comprehensive logging

**Persistent Messaging Features:**

The RabbitMQPublisher ensures no message loss through:

1. **Publisher Confirms**: Enabled by default, the publisher waits for broker acknowledgment
2. **Queue Pre-declaration**: Declare queues before publishing to avoid dropped messages
3. **Durable Queues**: All queues are durable with `auto_delete=False` and `exclusive=False`
4. **Persistent Messages**: All messages use `delivery_mode=2` for disk persistence
5. **Unroutable Detection**: Messages published to non-existent queues are detected

**Usage with Queue Pre-declaration:**

```python
from copilot_message_bus import RabbitMQPublisher

# Create publisher with confirms enabled (default)
publisher = RabbitMQPublisher(
    host="messagebus",
    enable_publisher_confirms=True  # Default
)
publisher.connect()  # Raises on failure

# Declare queues before publishing (raises on failure)
publisher.declare_queue(
    queue_name="archive.ingested",
    routing_key="archive.ingested",
    exchange="copilot.events"
)

# Now publish - guaranteed delivery (raises on failure)
publisher.publish(
    exchange="copilot.events",
    routing_key="archive.ingested",
    event={"event_type": "ArchiveIngested", "data": {...}}
)

# Or declare multiple queues at once (returns bool aggregate)
queues = [
    {"queue_name": "archive.ingested", "routing_key": "archive.ingested"},
    {"queue_name": "json.parsed", "routing_key": "json.parsed"},
]
ok = publisher.declare_queues(queues)
if not ok:
    # One or more declarations failed; inspect logs or retry as needed
    pass
```

#### RabbitMQSubscriber

Production subscriber implementation with:
- Topic-based routing
- Manual acknowledgment support
- Durable queue declarations with proper persistence flags
- Error handling with requeue
- Automatic routing key generation
- Callback-based event dispatch

**Persistence Settings:**

Named queues are declared with:
- `durable=True`: Queue survives broker restart
- `auto_delete=False`: Queue persists when no consumers
- `exclusive=False`: Queue can be accessed by multiple connections

#### AzureServiceBusPublisher

Azure Service Bus publisher implementation with:
- Support for both queues and topics
- Connection string or managed identity authentication
- Persistent messages by default
- JSON serialization
- Comprehensive logging and error handling

**Authentication Options:**

The AzureServiceBusPublisher supports two authentication methods:

1. **Connection String**: Simple authentication using Azure Service Bus connection string
2. **Managed Identity**: Azure Active Directory authentication using `DefaultAzureCredential`

**Usage with Connection String:**

```python
from copilot_message_bus import AzureServiceBusPublisher

# Create publisher with connection string
publisher = AzureServiceBusPublisher(
    connection_string="Endpoint=sb://namespace.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=...",
    queue_name="copilot-events"
)
publisher.connect()

# Publish event to queue
publisher.publish(
    exchange="copilot.events",
    routing_key="archive.ingested",
    event={"event_type": "ArchiveIngested", "data": {...}}
)

publisher.disconnect()
```

**Usage with Managed Identity:**

```python
from copilot_message_bus import AzureServiceBusPublisher

# Create publisher with managed identity (recommended for production)
publisher = AzureServiceBusPublisher(
    fully_qualified_namespace="namespace.servicebus.windows.net",
    topic_name="copilot-events",
    use_managed_identity=True
)
publisher.connect()

# Publish event to topic
publisher.publish(
    exchange="copilot.events",
    routing_key="archive.ingested",
    event={"event_type": "ArchiveIngested", "data": {...}}
)

publisher.disconnect()
```

**Environment Variables for Configuration:**

```bash
# For connection string authentication
AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://namespace.servicebus.windows.net/;..."
AZURE_SERVICEBUS_QUEUE_NAME="copilot-events"

# For managed identity authentication (in Azure environments)
AZURE_SERVICEBUS_NAMESPACE="namespace.servicebus.windows.net"
AZURE_SERVICEBUS_TOPIC_NAME="copilot-events"
```

#### AzureServiceBusSubscriber

Azure Service Bus subscriber implementation with:
- Support for both queues and topic subscriptions
- Connection string or managed identity authentication
- Manual or automatic message acknowledgment
- Callback-based event dispatch
- Error handling with message abandonment for retry

**Authentication Options:**

Same as the publisher, supporting both connection string and managed identity.

**Usage with Queue:**

```python
from copilot_message_bus import AzureServiceBusSubscriber

# Create subscriber for queue
subscriber = AzureServiceBusSubscriber(
    connection_string="Endpoint=sb://namespace.servicebus.windows.net/;...",
    queue_name="copilot-events",
    auto_complete=False,  # Manual acknowledgment
    max_wait_time=5
)

subscriber.connect()

# Register callback
def handle_event(event):
    print(f"Received: {event['event_type']}")

subscriber.subscribe("ArchiveIngested", handle_event)

# Start consuming (blocks)
try:
    subscriber.start_consuming()
except KeyboardInterrupt:
    subscriber.stop_consuming()
    subscriber.disconnect()
```

**Usage with Topic Subscription:**

```python
from copilot_message_bus import AzureServiceBusSubscriber

# Create subscriber for topic/subscription
subscriber = AzureServiceBusSubscriber(
    fully_qualified_namespace="namespace.servicebus.windows.net",
    topic_name="copilot-events",
    subscription_name="parsing-service",
    use_managed_identity=True,
    auto_complete=False
)

subscriber.connect()
subscriber.subscribe("JSONParsed", handle_json_parsed)
subscriber.start_consuming()
```

**Managed Identity Setup:**

For managed identity to work in Azure:
1. Enable managed identity on your Azure resource (VM, App Service, Container Instance, etc.)
2. Grant the managed identity the appropriate roles:
   - `Azure Service Bus Data Sender` for publishing
   - `Azure Service Bus Data Receiver` for subscribing
3. Use `fully_qualified_namespace` parameter instead of `connection_string`
4. Set `use_managed_identity=True`

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

#### ValidatingEventPublisher

Schema validation wrapper that:
- Validates events against JSON schemas before publishing
- Supports both strict (raise error) and non-strict (log warning) modes
- Works with FileSchemaProvider for event schema validation
- Composes cleanly with any EventPublisher implementation
- Provides structured ValidationError with detailed error messages

### Event Models

Event models provide:
- Auto-generated UUIDs
- ISO 8601 timestamps
- Consistent structure
- Type safety
- Easy serialization

## RabbitMQ Configuration for Production

### Heartbeat Configuration

RabbitMQ uses heartbeat frames to detect broken TCP connections. The default heartbeat interval has been increased from 60s to 300s (5 minutes) to provide better tolerance for CPU-intensive workloads.

#### Configuration Parameters

Both `RabbitMQPublisher` and `RabbitMQSubscriber` support:

- **`heartbeat`** (default: 300 seconds) - Interval between heartbeat frames
  - Higher values reduce network overhead and prevent disconnects during CPU-intensive tasks
  - Set to 0 to disable (not recommended)
  
- **`blocked_connection_timeout`** (default: 600 seconds) - Timeout for connections blocked by TCP backpressure
  - Should be at least 2x the heartbeat interval

#### Environment Variables

Override defaults using:

```bash
export RABBITMQ_HEARTBEAT=450               # 7.5 minutes
export RABBITMQ_BLOCKED_CONNECTION_TIMEOUT=900  # 15 minutes
```

#### Programmatic Configuration

```python
from copilot_message_bus.rabbitmq_publisher import RabbitMQPublisher

publisher = RabbitMQPublisher(
    host="messagebus",
    port=5672,
    username="guest",
    password="guest",
    heartbeat=300,  # 5 minutes
    blocked_connection_timeout=600,  # 10 minutes
)
```

For troubleshooting heartbeat timeouts, see [docs/troubleshooting/rabbitmq-heartbeat-timeouts.md](../../docs/troubleshooting/rabbitmq-heartbeat-timeouts.md).

### Docker Compose Setup

The repository includes a pre-configured `infra/rabbitmq/definitions.json` file that declares all queues, exchanges, and bindings needed for the Copilot-for-Consensus pipeline. This ensures queues exist before any service starts publishing.

**In docker-compose.yml:**

```yaml
messagebus:
  image: rabbitmq:3-management
  ports:
    - "5672:5672"
    - "15672:15672"
  volumes:
    - ./infra/rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
  environment:
    - RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbitmq_management load_definitions "/etc/rabbitmq/definitions.json"
```

### Pre-declared Queues

The following durable queues are pre-created:

- `archive.ingested` - Ingestion success events
- `archive.ingestion.failed` - Ingestion failure events
- `json.parsed` - Parsing success events
- `parsing.failed` - Parsing failure events
- `chunks.prepared` - Chunking success events
- `chunking.failed` - Chunking failure events
- `embeddings.generated` - Embedding success events
- `embedding.generation.failed` - Embedding failure events
- `summarization.requested` - Summarization request events
- `orchestration.failed` - Orchestration failure events
- `summary.complete` - Summarization success events
- `summarization.failed` - Summarization failure events
- `report.published` - Report publishing success events
- `report.delivery.failed` - Report delivery failure events

All queues are bound to the `copilot.events` topic exchange with matching routing keys.

### Adding New Event Types

When adding new event types:

1. Add the queue definition to `infra/rabbitmq/definitions.json`
2. Add the binding to the `copilot.events` exchange
3. Create a new event model class (if needed)
4. Update services to publish/subscribe to the new event

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

- Python 3.10+
- pika (for RabbitMQ)
- azure-servicebus (for Azure Service Bus)
- azure-identity (for Azure managed identity authentication)
- copilot-schema-validation (for ValidatingEventPublisher)

## License

MIT License - see LICENSE file for details.

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) in the main repository for contribution guidelines.
