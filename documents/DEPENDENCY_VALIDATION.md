# Dependency Validation Pattern

## Overview

All services in the Copilot-for-Consensus system validate their runtime dependencies during startup to fail fast when required services are unavailable. This prevents services from starting in a partially functional state and makes debugging easier.

## Validation Pattern

### 1. Configuration Loading

All services use `load_typed_config()` to load and validate configuration:

```python
from copilot_config import load_typed_config

config = load_typed_config("service-name")
```

Configuration schemas define required fields, types, and defaults. The loader validates configuration against the schema and raises `ConfigValidationError` if validation fails.

### 2. Dependency Connection Validation

After creating adapters, services MUST validate that connections succeed:

```python
# Create and connect publisher
publisher = create_publisher(
    message_bus_type=config.message_bus_type,
    host=config.message_bus_host,
    port=config.message_bus_port,
    username=config.message_bus_user,
    password=config.message_bus_password,
)

# Validate connection (fail fast for production backends)
if not publisher.connect():
    if str(config.message_bus_type).lower() != "noop":
        logger.error("Failed to connect publisher to message bus. Failing fast.")
        raise ConnectionError("Publisher failed to connect to message bus")
    else:
        logger.warning("Failed to connect publisher to message bus. Continuing with noop publisher.")
```

### 3. Exception Handling

Services use a top-level exception handler to catch and log all startup failures:

```python
def main():
    try:
        # ... service initialization ...
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        sys.exit(1)
```

## Required Validations by Service Type

### Event-Driven Services (chunking, parsing, embedding, etc.)

These services MUST validate:
1. ✅ **Message Bus Publisher** - `publisher.connect()` must succeed (unless using noop)
2. ✅ **Message Bus Subscriber** - `subscriber.connect()` must succeed
3. ✅ **Document Store** - `document_store.connect()` must succeed

### Vector Store Services (embedding, summarization)

In addition to event-driven validations, these services MUST validate:
4. ✅ **Vector Store** - `vector_store.connect()` must succeed (unless using inmemory)

### Batch Services (ingestion)

These services MUST validate:
1. ✅ **Message Bus Publisher** - `publisher.connect()` must succeed (unless using noop)
2. ✅ **Storage Path** - Verify storage path exists and is writable

## Testing

All services MUST have startup validation tests that verify:

1. **Service fails when publisher connection fails** (for non-noop backends)
2. **Service fails when subscriber connection fails**
3. **Service fails when document store connection fails**
4. **Service fails when vector store connection fails** (for vector store services)
5. **Service allows noop backends to fail gracefully**

Example test structure:

```python
def test_service_fails_when_publisher_connection_fails():
    """Test that service fails fast when publisher cannot connect."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            # Setup mock config
            config = Mock()
            config.message_bus_type = "rabbitmq"
            # ... configure all required fields ...
            mock_config.return_value = config
            
            # Setup mock publisher that fails to connect
            mock_publisher = Mock()
            mock_publisher.connect = Mock(return_value=False)
            mock_create_publisher.return_value = mock_publisher
            
            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                service_main.main()
            
            # Should exit with code 1 (error)
            assert exc_info.value.code == 1
```

## Checklist for Adding New Services

When adding a new service, ensure:

- [ ] Service loads configuration using `load_typed_config()`
- [ ] Service validates all adapter connections (publisher, subscriber, document store, etc.)
- [ ] Service raises clear `ConnectionError` exceptions when connections fail
- [ ] Service exits with code 1 when startup fails
- [ ] Service logs clear error messages indicating which dependency failed
- [ ] Service has tests validating startup failure when each dependency is unavailable
- [ ] Service allows noop/test backends to gracefully handle connection failures

## Services Status

| Service | Publisher | Subscriber | Document Store | Vector Store | Tests |
|---------|-----------|------------|----------------|--------------|-------|
| chunking | ✅ | ✅ | ✅ | N/A | ✅ |
| parsing | ✅ | ✅ | ✅ | N/A | ⚠️ |
| embedding | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| orchestrator | ✅ | ✅ | ✅ | N/A | ⚠️ |
| summarization | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| reporting | ✅ | ✅ | ✅ | N/A | ✅ |
| ingestion | ✅ | N/A | N/A | N/A | ⚠️ |

Legend:
- ✅ = Validated
- ⚠️ = Needs startup validation tests
- N/A = Not applicable

## Best Practices

1. **Always validate connections immediately after creation** - Don't defer validation until first use
2. **Fail fast with clear error messages** - Include the dependency name and reason for failure
3. **Allow test/noop backends to gracefully handle failures** - This enables local development and testing
4. **Exit with code 1 on startup failure** - This signals to orchestrators/init systems that the service failed
5. **Log connection attempts and results** - Helps with debugging deployment issues
6. **Test all failure scenarios** - Ensure services behave correctly when dependencies are unavailable
