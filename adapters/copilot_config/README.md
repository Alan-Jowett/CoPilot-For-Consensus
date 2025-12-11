# Copilot Config Adapter

A shared Python library for configuration management across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract ConfigProvider Interface**: Common interface for all configuration providers
- **EnvConfigProvider**: Production-ready provider that reads from environment variables
- **StaticConfigProvider**: Testing provider with hardcoded configuration values
- **Factory Pattern**: Simple factory function for creating configuration providers
- **Type-Safe Access**: Smart type conversion for bool and int types with proper defaults

## Installation

### For Development (Editable Mode)

From the adapters root directory:

```bash
cd adapters/copilot_config
pip install -e .
```

### For Production

```bash
pip install copilot-config
```

## Usage

### Production Configuration

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

### Testing Configuration

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

### Service Integration Example

```python
from copilot_config import create_config_provider, ConfigProvider
from typing import Optional

class MyServiceConfig:
    def __init__(self, host: str, port: int, enabled: bool):
        self.host = host
        self.port = port
        self.enabled = enabled
    
    @classmethod
    def from_env(cls, config_provider: Optional[ConfigProvider] = None):
        """Load configuration from environment variables."""
        if config_provider is None:
            config_provider = create_config_provider()
        
        return cls(
            host=config_provider.get("SERVICE_HOST", "localhost"),
            port=config_provider.get_int("SERVICE_PORT", 8080),
            enabled=config_provider.get_bool("SERVICE_ENABLED", True),
        )

# Production: uses environment variables
config = MyServiceConfig.from_env()

# Testing: uses static configuration
from copilot_config import StaticConfigProvider
test_config = MyServiceConfig.from_env(
    config_provider=StaticConfigProvider({
        "SERVICE_HOST": "test-host",
        "SERVICE_PORT": "9000",
        "SERVICE_ENABLED": "false"
    })
)
```

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
