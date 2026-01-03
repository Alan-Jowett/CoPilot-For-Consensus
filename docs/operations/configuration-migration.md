<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schema-Driven Configuration Migration

This guide shows how to move services from direct environment variable access to the schema-driven configuration system provided by `copilot_config`.

## Why migrate
- Centralize configuration in JSON schemas stored under [docs/schemas](../../docs/schemas)
- Strong typing with automatic conversion and validation
- Multi-source support (env, document store, static) with provider abstraction
- Fast-fail startup validation and attribute-style access in code

## Step 1: Define the schema
Create `../../docs/schemas/configs/<service>.json`:

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

## Step 2: Load typed config in the service

**Before (environment variables):**

```python
import os

message_bus_type = os.getenv("MESSAGE_BUS_TYPE", "rabbitmq")
message_bus_host = os.getenv("MESSAGE_BUS_HOST", "messagebus")
message_bus_port = int(os.getenv("MESSAGE_BUS_PORT", "5672"))
message_bus_user = os.getenv("MESSAGE_BUS_USER", "guest")
message_bus_password = os.getenv("MESSAGE_BUS_PASSWORD", "guest")

doc_store_type = os.getenv("DOCUMENT_STORE_TYPE", "mongodb")
doc_store_host = os.getenv("DOCUMENT_DATABASE_HOST", "documentdb")
doc_store_port = int(os.getenv("DOCUMENT_DATABASE_PORT", "27017"))
doc_store_name = os.getenv("DOCUMENT_DATABASE_NAME", "copilot")
```

**After (schema-driven config):**

```python
from copilot_config import load_typed_config

config = load_typed_config("my-service")

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

## Step 3: Handle validation errors

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

## Step 4: Update tests

```python
from copilot_config import StaticConfigProvider, load_typed_config

def test_service():
    static_provider = StaticConfigProvider({
        "message_bus_host": "test-host",
        "message_bus_port": 6000,
        "doc_store_host": "test-db"
    })

    config = load_typed_config("my-service", static_provider=static_provider)
    # Run test logic using config
```

## Example: Chunking service

```python
from copilot_config import load_typed_config, ConfigValidationError

try:
    config = load_typed_config("chunking")
except ConfigValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)

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

## Field types
- `string`, `int`, `bool`, `float`, `object`, `array`
- Sources: `env` (default), `document_store`, `static`

## Best practices
1. Mark critical fields as `required` and provide defaults where sensible.
2. Use descriptive names following existing patterns (`message_bus_host`, `doc_store_host`).
3. Validate on startup and fail fast on errors.
4. Keep schemas documented—see [docs/schemas/README.md](../schemas/README.md) for layout and pointers.

## Troubleshooting

**Schema not found**: `ConfigSchemaError: Schema file not found` → verify the JSON path under `docs/schemas/configs/`.

**Missing required field**: `ConfigValidationError` reports missing keys → set env vars, add defaults, or mark optional.

**Type conversion error**: ensure env vars contain the expected type (e.g., numeric port values).

## Next steps
1. Migrate one service at a time using static providers in tests.
2. Add document store-backed providers when centralizing configuration.
3. Keep schemas in sync with code changes and update changelog comments in the JSON metadata.
