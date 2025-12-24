# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Testing Message Bus and Schema Validation

This document describes the testing patterns for message bus interactions and schema validation added to the Copilot-for-Consensus services.

## Overview

All services now have comprehensive tests for:
1. **Schema Validation** - Events are validated against JSON schemas
2. **Message Consumption** - Services correctly handle incoming events
3. **Error Handling** - Services gracefully handle malformed messages
4. **Integration** - End-to-end message flow patterns

## Test Helper Utilities

Each service has a `tests/test_helpers.py` module with schema validation utilities:

```python
from .test_helpers import assert_valid_event_schema

# In your test
event = {...}  # Your event dictionary
assert_valid_event_schema(event)  # Validates against JSON schema
```

## Pattern 1: Schema Validation Tests

Validate that events published by a service conform to their JSON schemas:

```python
def test_publish_event_with_schema_validation(service, mock_publisher):
    """Test that published events validate against schema."""
    service._publish_my_event(...)

    # Get published event
    call_args = mock_publisher.publish.call_args
    event = call_args[1]["message"]

    # Validate against JSON schema
    assert_valid_event_schema(event)
```

### Examples
- `summarization/tests/test_service.py::test_schema_validation_summary_complete_valid`
- `ingestion/tests/test_service.py::test_archive_ingested_event_schema_validation`
- `chunking/tests/test_service.py::test_schema_validation_chunks_prepared`

## Pattern 2: Message Consumption Tests

Test that services correctly handle incoming events:

```python
def test_consume_event():
    """Test consuming and processing an event."""
    # Create a valid event
    event = {
        "event_type": "MyEvent",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {...}
    }

    # Validate incoming event
    assert_valid_event_schema(event)

    # Process the event
    service._handle_my_event(event)

    # Verify processing succeeded
    assert service.get_stats()["events_processed"] == 1
```

### Examples
- `summarization/tests/test_service.py::test_consume_summarization_requested_event`
- `chunking/tests/test_service.py::test_consume_json_parsed_event`
- `parsing/tests/test_service.py::test_consume_archive_ingested_event`

## Pattern 3: Invalid Message Handling Tests

Test that services handle malformed messages gracefully:

```python
def test_handle_malformed_event():
    """Test handling event with missing required field."""
    # Event missing 'data' field
    event = {
        "event_type": "MyEvent",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        # Missing 'data' field
    }

    # Should handle gracefully without crashing
    try:
        service._handle_my_event(event)
    except KeyError:
        # Expected - service should validate required fields
        pass
```

### Examples
- `summarization/tests/test_service.py::test_handle_malformed_event_missing_data`
- `chunking/tests/test_service.py::test_handle_malformed_event_missing_data`
- `parsing/tests/test_service.py::test_handle_malformed_event_missing_data`

## Pattern 4: Integration Tests

Document and test message flow patterns across services:

```python
def test_message_flow_pattern():
    """Document message flow from service A to service B."""
    # Input event from service A
    input_event = {
        "event_type": "EventA",
        ...
    }
    validate_event(input_event)

    # Output event from service B
    output_event = {
        "event_type": "EventB",
        "data": {
            "preserved_field": input_event["data"]["field"],  # Data flow
            ...
        }
    }
    validate_event(output_event)

    # Verify data preservation
    assert output_event["data"]["preserved_field"] == input_event["data"]["field"]
```

### Examples
- `tests/test_integration_message_flow.py::TestMessageFlowPatterns::test_ingestion_produces_archive_ingested`
- `tests/test_integration_message_flow.py::TestMessageFlowPatterns::test_parsing_consumes_archive_ingested_produces_json_parsed`
- `tests/test_integration_message_flow.py::TestMessageFlowPatterns::test_chunking_consumes_json_parsed_produces_chunks_prepared`

## Running Tests

### Individual Service Tests
```bash
# Run all tests for a service
cd summarization
python -m pytest tests/ -v

# Run specific test category
python -m pytest tests/test_service.py::test_schema_validation_summary_complete_valid -v
```

### Integration Tests
```bash
cd tests
python -m pytest test_integration_message_flow.py -v
```

### All Tests
```bash
# From repository root
python -m pytest summarization/tests/ chunking/tests/ parsing/tests/ ingestion/tests/ tests/ -v
```

## Event Schemas

All event schemas are located in `documents/schemas/events/`:
- `ArchiveIngested.schema.json`
- `JSONParsed.schema.json`
- `ChunksPrepared.schema.json`
- `SummarizationRequested.schema.json`
- `SummaryComplete.schema.json`
- And more...

## Key Benefits

1. **Early Detection** - Schema validation catches mismatches during development
2. **Documentation** - Tests serve as documentation for event structures and flows
3. **Reliability** - Error handling tests ensure services are robust
4. **Maintainability** - Changes to schemas are immediately caught by tests

## Best Practices

1. **Always validate events** - Use `assert_valid_event_schema()` for all published events
2. **Test happy path and errors** - Include both valid and invalid message tests
3. **Document data flow** - Use integration tests to show how data flows between services
4. **Keep tests focused** - One test should verify one aspect (schema, consumption, or error handling)
5. **Use realistic data** - Test events should match production event structures

## Adding Tests to New Services

When adding a new service:

1. Copy `test_helpers.py` to your `tests/` directory
2. Add schema validation to existing event publishing tests
3. Add message consumption tests for events your service subscribes to
4. Add invalid message handling tests
5. Update integration tests if your service adds new event flows

## Example: Adding Tests to a New Service

```python
# tests/test_helpers.py
# (Copy from any existing service)

# tests/test_service.py
from .test_helpers import assert_valid_event_schema

def test_my_event_schema_validation(service, mock_publisher):
    """Test that MyEvent validates against schema."""
    service._publish_my_event(field1="value1", field2="value2")

    call_args = mock_publisher.publish.call_args
    event = call_args[1]["message"]

    # This will fail if event doesn't match schema
    assert_valid_event_schema(event)

def test_consume_incoming_event():
    """Test consuming IncomingEvent."""
    event = {
        "event_type": "IncomingEvent",
        "event_id": "test-123",
        "timestamp": "2023-10-15T12:00:00Z",
        "version": "1.0",
        "data": {...}
    }

    # Validate event structure
    assert_valid_event_schema(event)

    # Process it
    service._handle_incoming_event(event)

    # Verify results
    assert service.get_stats()["events_processed"] == 1

def test_handle_malformed_event():
    """Test handling malformed event."""
    event = {"event_type": "IncomingEvent"}  # Missing required fields

    try:
        service._handle_incoming_event(event)
    except (KeyError, ValueError):
        pass  # Expected
```

## Troubleshooting

### Schema not found
If you get "No schema found for event type X":
- Check that the schema file exists in `documents/schemas/events/X.schema.json`
- Verify the event_type in your event matches the schema filename

### Validation fails
If validation fails unexpectedly:
- Compare your event against the schema in `documents/schemas/events/`
- Check for missing required fields
- Verify field types match schema (string vs integer, array vs string, etc.)
- Look at the validation error messages for specific issues

### Tests can't import modules
- Ensure `pytest.ini` includes `pythonpath = .`
- Check that adapters are installed: `python adapters/scripts/install_adapters.py`
- Run tests from the service directory, not from root
