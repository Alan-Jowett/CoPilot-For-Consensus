<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Config Adapter

A shared Python library for configuration management across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract ConfigProvider Interface**: Common interface for all configuration providers
- **EnvConfigProvider**: Production-ready provider that reads from environment variables
- **StaticConfigProvider**: Testing provider with hardcoded configuration values
- **DocStoreConfigProvider**: Provider that reads configuration from document stores
- **StorageConfigProvider**: Dynamic configuration backed by copilot_storage document stores with TTL-based refresh
- **Schema-Driven Configuration**: JSON schema-based configuration with validation
- **Typed Configuration**: Type-safe configuration access with attribute-style syntax
- **Multi-Source Support**: Load configuration from environment, document stores, or static sources
- **Fast-Fail Validation**: Validate configuration at startup and fail fast on errors
- **Factory Pattern**: Simple factory function for creating configuration providers
- **Type-Safe Access**: Smart type conversion for bool, int, float, and string types with proper defaults

## Installation

### For Development (Editable Mode)

From the adapters root directory:

```bash
cd adapters/copilot_config
pip install -e ".[dev]"
```

### For Production

```bash
pip install copilot-config
```

## Usage

### Schema-Driven Configuration (Recommended)

The recommended approach is to use schema-driven configuration with the `load_config()` function.

#### 1. Define a Schema

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
    },
    "debug": {
      "type": "bool",
      "source": "env",
      "env_var": "DEBUG",
      "default": false,
      "description": "Enable debug mode"
    }
  }
}
```

#### 2. Load Configuration

```python
from copilot_config import load_typed_config

# Load configuration with schema validation
# Returns TypedConfig with attribute-ONLY access (enables static verification)
config = load_typed_config("my-service")

# Access via attributes (verifiable by static analysis tools)
print(config.message_bus_host)  # "messagebus"
print(config.message_bus_port)  # 5672
print(config.debug)             # False

# Dictionary-style access intentionally NOT supported
# config["message_bus_host"]  # ✗ Raises AttributeError
# This ensures all accessed keys can be verified against the schema
```

#### 3. Error Handling

For compile-time safety, all services must use `load_typed_config()`.
Trying to import `load_config()` directly will fail:

```python
from copilot_config import load_typed_config, ConfigValidationError, ConfigSchemaError

try:
    config = load_typed_config("my-service")
except ConfigSchemaError as e:
    print(f"Schema error: {e}")
except ConfigValidationError as e:
    print(f"Validation error: {e}")
```

### Schema Field Types

Supported field types:
- `string`: String values
- `int`: Integer values
- `bool`: Boolean values (accepts "true", "1", "yes", "on" as True)
- `float`: Floating-point values
- `object`: Nested objects (dictionaries)
- `array`: Array/list values

### Configuration Sources

Each field can specify where its value comes from:

- `env`: Environment variables (via `env_var` parameter)
- `document_store`: Document store (via `doc_store_path` parameter)
- `static`: Static/hardcoded values

### Validation

The schema loader validates:
- **Required fields**: Fields marked as `required: true` must have values
- **Type validation**: Values are converted to the correct type
- **Fast-fail**: Configuration errors are detected at startup
- **Compile-time safety**: Only `load_typed_config()` is exported; unvalidated config loading is impossible

Example error:

```python
from copilot_config import load_typed_config, ConfigValidationError

try:
    config = load_typed_config("my-service")
except ConfigValidationError as e:
    print(f"Configuration error: {e}")
    # Configuration validation failed for my-service:
    #   - message_bus_host: Required field 'message_bus_host' is missing
```

### Traditional Configuration Providers

You can also use the low-level configuration providers directly:

#### Production Configuration

```python
from copilot_config import create_config_provider

# Create provider (defaults to environment variables)
config = create_config_provider()

# Get string values
host = config.get("MESSAGE_BUS_HOST", "localhost")

# Get boolean values (accepts "true", "1", "yes", "on" as True)
enabled = config.get_bool("FEATURE_ENABLED", False)

# Get integer values
port = config.get_int("MESSAGE_BUS_PORT", 5672)
```

#### Testing Configuration

```python
from copilot_config import StaticConfigProvider

# Create provider with test configuration
config = StaticConfigProvider({
    "MESSAGE_BUS_HOST": "test-host",
    "MESSAGE_BUS_PORT": 6000,
    "FEATURE_ENABLED": True,
})

# Use same interface
host = config.get("MESSAGE_BUS_HOST")  # "test-host"
port = config.get_int("MESSAGE_BUS_PORT")  # 6000
enabled = config.get_bool("FEATURE_ENABLED")  # True

# Dynamically update config in tests
config.set("NEW_KEY", "new_value")
```

#### Dynamic Configuration via copilot_storage

```python
from copilot_config import StorageConfigProvider
from copilot_storage import create_document_store

# Backed by any copilot_storage DocumentStore implementation
store = create_document_store(store_type="inmemory")
store.connect()
store.insert_document("config", {"key": "PROMPT", "value": "Use the newest prompt."})

# Cached reads with a small TTL for dynamic values
config = StorageConfigProvider(doc_store=store, cache_ttl_seconds=10)

prompt = config.get("PROMPT")
```

If you do not pass a `doc_store`, `StorageConfigProvider` will create one using
environment variables (defaults to `mongodb`):

- `CONFIG_STORE_TYPE` (e.g., `mongodb`, `inmemory`)
- `CONFIG_STORE_HOST` / `CONFIG_STORE_PORT`
- `CONFIG_STORE_USERNAME` / `CONFIG_STORE_PASSWORD`
- `CONFIG_STORE_DATABASE` (default: `copilot_config`)

Install copilot_storage support with `pip install copilot-config[storage]`.

## Architecture

### ConfigProvider Interface

The `ConfigProvider` abstract base class defines the contract for configuration access:

- `get(key, default=None) -> Any`: Get a configuration value
- `get_bool(key, default=False) -> bool`: Get a boolean configuration value
- `get_int(key, default=0) -> int`: Get an integer configuration value

### Implementations

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

#### DocStoreConfigProvider

Document store configuration provider with:
- Loads configuration from document stores (MongoDB, etc.)
- Caches configuration for performance
- Supports nested keys and objects
- Useful for centralized configuration management

### Schema-Driven Configuration

The schema-driven system provides:
- **ConfigSchema**: Represents a service's configuration schema
- **FieldSpec**: Defines individual configuration fields
- **SchemaConfigLoader**: Loads and validates configuration based on schema
- **load_config()**: Main entry point for schema-driven configuration
- **TypedConfig**: Typed wrapper for attribute-style configuration access

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Running Tests with Coverage

```bash
pytest tests/ --cov=copilot_config --cov-report=html
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

See [CONTRIBUTING.md](../../documents/CONTRIBUTING.md) for contribution guidelines.
