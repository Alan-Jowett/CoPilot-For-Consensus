# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Schema-Driven Configuration Migration Guide

This guide explains how to migrate microservices from direct environment variable access to the schema-driven configuration system.

## Overview

The schema-driven configuration system provides:

- **Centralized Schema Definition**: All configuration fields defined in JSON schemas
- **Multi-Source Support**: Load configuration from environment variables, YAML files, document stores, or static sources
- **Type Safety**: Automatic type conversion and validation
- **Fast-Fail Validation**: Configuration errors detected at startup
- **Provider Abstraction**: Services are agnostic about configuration source
- **Typed Access**: Attribute-style configuration access

## Migration Steps

### Step 1: Define Configuration Schema

Create a JSON schema file in `schemas/<service>.json`:

```json
{
  "service_name": "my-service",
  "metadata": {
    "description": "My service configuration schema",
    "version": "1.0.0"
  },
  "fields": {
    "message_bus_host": {
      "type": "string",
      "source": "env",
      "env_var": "MESSAGE_BUS_HOST",
      "default": "messagebus",
      "required": true,
      "description": "Message bus hostname"
    },
    "message_bus_port": {
      "type": "int",
      "source": "env",
      "env_var": "MESSAGE_BUS_PORT",
      "default": 5672,
      "description": "Message bus port"
    }
  }
}
```

### Step 2: Update Service Main File

#### Before (Direct Environment Variable Access):

```python
import os

# Load configuration from environment
message_bus_type = os.getenv("MESSAGE_BUS_TYPE", "rabbitmq")
message_bus_host = os.getenv("MESSAGE_BUS_HOST", "messagebus")
message_bus_port = int(os.getenv("MESSAGE_BUS_PORT", "5672"))
message_bus_user = os.getenv("MESSAGE_BUS_USER", "guest")
message_bus_password = os.getenv("MESSAGE_BUS_PASSWORD", "guest")

doc_store_type = os.getenv("DOC_STORE_TYPE", "mongodb")
doc_store_host = os.getenv("DOC_DB_HOST", "documentdb")
doc_store_port = int(os.getenv("DOC_DB_PORT", "27017"))
doc_store_name = os.getenv("DOC_DB_NAME", "copilot")
```

#### After (Schema-Driven Configuration):

```python
from copilot_config import load_typed_config

# Load configuration from schema
config = load_typed_config("my-service")

# Access configuration via attributes
message_bus_type = config.message_bus_type
message_bus_host = config.message_bus_host
message_bus_port = config.message_bus_port
message_bus_user = config.message_bus_user
message_bus_password = config.message_bus_password

doc_store_type = config.doc_store_type
doc_store_host = config.doc_store_host
doc_store_port = config.doc_store_port
doc_store_name = config.doc_store_name
```

### Step 3: Handle Configuration Errors

Add error handling for configuration validation:

```python
from copilot_config import load_typed_config, ConfigValidationError, ConfigSchemaError

try:
    config = load_typed_config("my-service")
except ConfigSchemaError as e:
    logger.error(f"Configuration schema error: {e}")
    sys.exit(1)
except ConfigValidationError as e:
    logger.error(f"Configuration validation error: {e}")
    sys.exit(1)
```

### Step 4: Update Tests

Update tests to use the schema-driven configuration:

#### Before:

```python
def test_service():
    # Set environment variables
    os.environ["MESSAGE_BUS_HOST"] = "test-host"
    os.environ["MESSAGE_BUS_PORT"] = "6000"
    
    # Run test
    # ...
```

#### After:

```python
from copilot_config import StaticConfigProvider, load_typed_config

def test_service():
    # Create static config for testing
    static_provider = StaticConfigProvider({
        "message_bus_host": "test-host",
        "message_bus_port": 6000,
        "doc_store_host": "test-db",
        # ... other config values
    })
    
    config = load_typed_config(
        "my-service",
        static_provider=static_provider
    )
    
    # Run test with config
    # ...
```

## Example: Chunking Service Migration

### Original Code (chunking/main.py):

```python
# Load configuration from environment
message_bus_type = os.getenv("MESSAGE_BUS_TYPE", "rabbitmq")
message_bus_host = os.getenv("MESSAGE_BUS_HOST", "messagebus")
message_bus_port = int(os.getenv("MESSAGE_BUS_PORT", "5672"))
message_bus_user = os.getenv("MESSAGE_BUS_USER", "guest")
message_bus_password = os.getenv("MESSAGE_BUS_PASSWORD", "guest")

doc_store_type = os.getenv("DOC_STORE_TYPE", "mongodb")
doc_store_host = os.getenv("DOC_DB_HOST", "documentdb")
doc_store_port = int(os.getenv("DOC_DB_PORT", "27017"))
doc_store_name = os.getenv("DOC_DB_NAME", "copilot")
doc_store_user = os.getenv("DOC_DB_USER", "")
doc_store_password = os.getenv("DOC_DB_PASSWORD", "")

chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
chunking_strategy = os.getenv("CHUNKING_STRATEGY", "recursive")
```

### Migrated Code:

```python
from copilot_config import load_typed_config, ConfigValidationError

try:
    config = load_typed_config("chunking")
except ConfigValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)

# Access configuration
message_bus_type = config.message_bus_type
message_bus_host = config.message_bus_host
message_bus_port = config.message_bus_port
message_bus_user = config.message_bus_user
message_bus_password = config.message_bus_password

doc_store_type = config.doc_store_type
doc_store_host = config.doc_store_host
doc_store_port = config.doc_store_port
doc_store_name = config.doc_store_name
doc_store_user = config.doc_store_user
doc_store_password = config.doc_store_password

chunk_size = config.chunk_size
chunk_overlap = config.chunk_overlap
chunking_strategy = config.chunking_strategy
```

## Benefits

1. **Single Source of Truth**: All configuration fields defined in one place
2. **Type Safety**: Automatic type conversion and validation
3. **Fast-Fail**: Configuration errors detected at startup
4. **Testability**: Easy to mock configuration for testing
5. **Documentation**: Schema serves as documentation
6. **Flexibility**: Easy to add new sources (YAML, document store, etc.)
7. **Consistency**: All services use the same configuration pattern

## Schema Field Types

- `string`: String values
- `int`: Integer values  
- `bool`: Boolean values (accepts "true", "1", "yes", "on" as True)
- `float`: Floating-point values
- `object`: Nested objects
- `array`: Arrays/lists

## Configuration Sources

- `env`: Environment variables (default)
- `yaml`: YAML files
- `document_store`: Document store (MongoDB, etc.)
- `static`: Static/hardcoded values

## Best Practices

1. **Mark critical fields as required**: Use `"required": true` for essential configuration
2. **Provide sensible defaults**: Most fields should have defaults for easier deployment
3. **Use descriptive names**: Follow existing naming conventions (e.g., `message_bus_host`)
4. **Document fields**: Add descriptions to all fields
5. **Group related fields**: Consider using nested objects for related configuration
6. **Test with minimal config**: Ensure defaults work in development
7. **Validate early**: Load and validate configuration at service startup

## Troubleshooting

### Schema not found error

```
ConfigSchemaError: Schema file not found: /path/to/schemas/my-service.json
```

**Solution**: Ensure the schema file exists in the `schemas/` directory at the repository root.

### Validation error for required field

```
ConfigValidationError: Configuration validation failed for my-service:
  - database_host: Required field 'database_host' is missing
```

**Solution**: Either:
1. Set the environment variable
2. Add a default value to the schema
3. Make the field optional (`"required": false`)

### Type conversion error

```
ConfigValidationError: Invalid value for field 'port': expected int, got 'invalid'
```

**Solution**: Ensure environment variables contain valid values for the expected type.

## Next Steps

1. Migrate one service at a time
2. Test thoroughly after each migration
3. Update documentation as needed
4. Consider adding YAML file support for local development
5. Consider adding document store support for centralized configuration
