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

### 3. Permission Validation

Services MUST validate they have required permissions on connected resources:

```python
# Validate document store permissions (read/write access)
logger.info("Validating document store permissions...")
if str(config.doc_store_type).lower() != "inmemory":
    try:
        # Test write permission
        test_doc_id = document_store.insert_document("_startup_validation", {"test": True})
        # Test read permission
        retrieved = document_store.get_document("_startup_validation", test_doc_id)
        if retrieved is None:
            raise PermissionError("Document store read permission validation failed")
        # Clean up test document
        document_store.delete_document("_startup_validation", test_doc_id)
        logger.info("Document store permissions validated successfully")
    except Exception as e:
        logger.error(f"Document store permission validation failed: {e}")
        raise PermissionError(f"Document store does not have required read/write permissions: {e}")
```

### 4. Schema Availability Validation

Services MUST validate that all required event/document schemas can be loaded:

```python
# Validate required event schemas can be loaded
logger.info("Validating event schemas...")
schema_provider = FileSchemaProvider()
required_schemas = ["JSONParsed", "ChunksPrepared", "ChunkingFailed"]
for schema_name in required_schemas:
    schema = schema_provider.get_schema(schema_name)
    if schema is None:
        logger.error(f"Failed to load required schema: {schema_name}")
        raise RuntimeError(f"Required event schema '{schema_name}' could not be loaded")
logger.info(f"Successfully validated {len(required_schemas)} required event schemas")
```

### 5. Exception Handling

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
3. ✅ **Document Store Connection** - `document_store.connect()` must succeed
4. ✅ **Document Store Permissions** - Test read/write access with a test document (unless using inmemory)
5. ✅ **Event Schemas** - Validate all required event schemas can be loaded at startup

### Vector Store Services (embedding, summarization)

In addition to event-driven validations, these services MUST validate:
6. ✅ **Vector Store** - `vector_store.connect()` must succeed (unless using inmemory)

### Batch Services (ingestion)

These services MUST validate:
1. ✅ **Message Bus Publisher** - `publisher.connect()` must succeed (unless using noop)
2. ✅ **Storage Path** - Verify storage path exists and is writable
3. ✅ **Event Schemas** - Validate all required event schemas can be loaded at startup

## Testing

All services MUST have startup validation tests that verify:

1. **Service fails when publisher connection fails** (for non-noop backends)
2. **Service fails when subscriber connection fails**
3. **Service fails when document store connection fails**
4. **Service fails when document store lacks read/write permissions**
5. **Service fails when required event schemas cannot be loaded**
6. **Service fails when vector store connection fails** (for vector store services)
7. **Service allows noop/inmemory backends to gracefully handle connection failures**

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
- [ ] Service validates document store permissions (read/write test)
- [ ] Service validates all required event/document schemas can be loaded
- [ ] Service raises clear `ConnectionError` or `PermissionError` exceptions when validations fail
- [ ] Service exits with code 1 when startup fails
- [ ] Service logs clear error messages indicating which dependency or validation failed
- [ ] Service has tests validating startup failure when each dependency is unavailable
- [ ] Service has tests validating startup failure when permissions are insufficient
- [ ] Service has tests validating startup failure when schemas are missing
- [ ] Service allows noop/test backends to gracefully handle connection failures

## Services Status

| Service | Publisher | Subscriber | Doc Store | Permissions | Schemas | Vector Store | Tests |
|---------|-----------|------------|-----------|-------------|---------|--------------|-------|
| chunking | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ |
| parsing | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | ⚠️ |
| embedding | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ |
| orchestrator | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | ⚠️ |
| summarization | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ |
| reporting | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ |
| ingestion | ✅ | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ |

Legend:
- ✅ = Validated
- ⚠️ = Needs implementation
- N/A = Not applicable

## Best Practices

1. **Always validate connections immediately after creation** - Don't defer validation until first use
2. **Always validate permissions after connecting** - Test read/write access with a test document
3. **Always validate schemas at startup** - Ensure all required event/document schemas can be loaded
4. **Fail fast with clear error messages** - Include the dependency name and reason for failure
5. **Allow test/noop backends to gracefully handle failures** - This enables local development and testing
6. **Exit with code 1 on startup failure** - This signals to orchestrators/init systems that the service failed
7. **Log all validation attempts and results** - Helps with debugging deployment issues
8. **Test all failure scenarios** - Ensure services behave correctly when dependencies are unavailable or misconfigured
