# Copilot Logging SDK

A pluggable logging abstraction layer for Copilot-for-Consensus microservices.

## Features

- **Abstract Logger Interface**: Common interface for all logger implementations
- **Structured JSON Output**: StdoutLogger provides structured JSON logs for observability
- **Silent Testing**: SilentLogger stores logs in memory for testing without output
- **Environment Configuration**: Easy configuration via environment variables
- **Factory Pattern**: Simple factory function for creating loggers

## Installation

The `copilot_logging` module is a standalone package with its own setup.py. Install it in editable mode for development:

```bash
cd sdk/copilot_logging
pip install -e .
```

## Usage

### Basic Usage

```python
from copilot_logging import create_logger

# Create a logger (defaults to stdout with INFO level)
logger = create_logger()

# Log messages at different levels
logger.info("Service started")
logger.warning("Connection retry attempt", attempt=3)
logger.error("Failed to process request", error="timeout", request_id="123")
logger.debug("Processing item", item_id=456, details="some details")
```

### Structured Logging

All loggers support structured logging by passing keyword arguments:

```python
logger.info(
    "User authentication successful",
    user_id=123,
    username="alice",
    ip_address="192.168.1.1",
    timestamp="2025-12-10T15:00:00Z"
)
```

This produces JSON output:

```json
{
  "timestamp": "2025-12-10T15:00:00.123456Z",
  "level": "INFO",
  "logger": "copilot",
  "message": "User authentication successful",
  "extra": {
    "user_id": 123,
    "username": "alice",
    "ip_address": "192.168.1.1",
    "timestamp": "2025-12-10T15:00:00Z"
  }
}
```

### Configuration

#### Using Environment Variables

```bash
# Set logger type (stdout, silent)
export LOG_TYPE=stdout

# Set log level (DEBUG, INFO, WARNING, ERROR)
export LOG_LEVEL=INFO

# Set logger name
export LOG_NAME=ingestion-service

# Create logger from environment
python -c "from copilot_logging import create_logger; logger = create_logger()"
```

#### Direct Configuration

```python
from copilot_logging import create_logger

# Create with specific configuration
logger = create_logger(
    logger_type="stdout",
    level="DEBUG",
    name="my-service"
)
```

## Logger Types

### StdoutLogger

Outputs structured JSON logs to stdout. Ideal for production use with log aggregation systems.

```python
from copilot_logging import create_logger

logger = create_logger(logger_type="stdout", level="INFO", name="api-service")
logger.info("Request received", method="GET", path="/api/status")
```

**Output:**
```json
{"timestamp": "2025-12-10T15:30:00.123456Z", "level": "INFO", "logger": "api-service", "message": "Request received", "extra": {"method": "GET", "path": "/api/status"}}
```

### SilentLogger

Stores logs in memory without output. Perfect for testing.

```python
from copilot_logging import create_logger

logger = create_logger(logger_type="silent")
logger.info("Test message", test_id=1)

# Verify logs in tests
assert logger.has_log("Test message")
assert len(logger.get_logs(level="INFO")) == 1
```

## Testing with SilentLogger

The SilentLogger provides methods specifically for testing:

```python
import pytest
from copilot_logging import create_logger

def test_my_function():
    logger = create_logger(logger_type="silent")
    
    # Your code that logs
    my_function(logger)
    
    # Verify logging behavior
    assert logger.has_log("Expected message")
    assert len(logger.get_logs(level="ERROR")) == 0
    
    # Get specific logs
    info_logs = logger.get_logs(level="INFO")
    assert len(info_logs) == 2
    
    # Check for specific log with extra data
    logs = logger.get_logs()
    assert any(
        log["message"] == "User login" and 
        log["extra"]["user_id"] == 123 
        for log in logs
    )
```

## Log Levels

The logger supports four standard log levels:

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for serious problems

Log level filtering is supported - logs below the configured level are not output:

```python
# Only WARNING and ERROR will be output
logger = create_logger(logger_type="stdout", level="WARNING")

logger.debug("This is hidden")      # Not output
logger.info("This is also hidden")  # Not output
logger.warning("This is shown")     # Output
logger.error("This is also shown")  # Output
```

## Integration with Services

### Example Service Integration

```python
# main.py
import os
from copilot_logging import create_logger

def main():
    # Create logger from environment or use defaults
    logger = create_logger(
        logger_type=os.getenv("LOG_TYPE", "stdout"),
        level=os.getenv("LOG_LEVEL", "INFO"),
        name="ingestion-service"
    )
    
    logger.info("Starting service", version="1.0.0")
    
    try:
        # Your service logic
        process_data(logger)
        logger.info("Service completed successfully")
    except Exception as e:
        logger.error("Service failed", error=str(e))
        raise

def process_data(logger):
    logger.debug("Processing started")
    # Processing logic
    logger.info("Processed 100 items", count=100)

if __name__ == "__main__":
    main()
```

## Benefits

1. **Consistent Logging**: All services use the same logging interface
2. **Structured Data**: JSON output enables easy parsing and analysis
3. **Testability**: Silent logger makes testing logging behavior easy
4. **Observability**: Structured logs integrate well with monitoring tools
5. **Flexibility**: Easy to add new logger backends (e.g., cloud logging)

## Future Enhancements

Potential future logger implementations:

- **CloudLogger**: Integration with Azure Monitor, AWS CloudWatch, GCP Logging
- **FileLogger**: Log rotation and file-based logging
- **SyslogLogger**: Integration with syslog
- **MultiLogger**: Fan-out to multiple backends simultaneously

## API Reference

### `create_logger(logger_type, level, name)`

Factory function to create logger instances.

**Parameters:**
- `logger_type` (str, optional): Type of logger ("stdout", "silent"). Defaults to "stdout".
- `level` (str, optional): Log level ("DEBUG", "INFO", "WARNING", "ERROR"). Defaults to "INFO".
- `name` (str, optional): Logger name for identification. Defaults to "copilot".

**Returns:**
- `Logger`: Logger instance

### `Logger` (Abstract Interface)

Base interface for all loggers.

**Methods:**
- `info(message, **kwargs)`: Log info-level message
- `warning(message, **kwargs)`: Log warning-level message
- `error(message, **kwargs)`: Log error-level message
- `debug(message, **kwargs)`: Log debug-level message

### `SilentLogger` (Additional Methods)

**Methods:**
- `clear_logs()`: Clear all stored logs
- `get_logs(level=None)`: Get stored logs, optionally filtered by level
- `has_log(message, level=None)`: Check if a log message exists

## License

MIT License - See LICENSE file for details.
