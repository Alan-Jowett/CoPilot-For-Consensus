<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Reporting Adapter

A shared Python library for error reporting and diagnostics across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Reporter Interface**: Common interface for all error reporters
- **Console Reporter**: Default implementation that logs to stdout
- **Silent Reporter**: Testing implementation with in-memory storage
- **Sentry Reporter**: Scaffold for cloud-based error tracking (requires `sentry-sdk`)
- **Factory Pattern**: Simple factory function for creating reporters

## Installation

### For Development (Editable Mode)

From the adapters directory:

```bash
cd adapters/copilot_reporting
pip install -e ".[dev]"
```

### For Production

```bash
pip install copilot-reporting
```

### With Sentry Support

```bash
pip install copilot-reporting[sentry]
```

## Usage

### Basic Error Reporting

```python
from copilot_reporting import create_error_reporter

# Create a console error reporter (default)
error_reporter = create_error_reporter(reporter_type="console")

# Report an exception with context
try:
    risky_operation()
except Exception as e:
    error_reporter.report(e, context={
        "user_id": "123",
        "operation": "risky_operation",
        "request_id": "abc-def"
    })

# Capture a message without an exception
error_reporter.capture_message(
    "Configuration validation failed",
    level="warning",
    context={"config_source": "environment"}
)
```

### Error Reporter Interface

The `ErrorReporter` abstract base class defines:

- `report(error: Exception, context: dict = None)`: Report an exception with optional context
- `capture_message(message: str, level: str = "error", context: dict = None)`: Capture a message without an exception

Supported levels: `debug`, `info`, `warning`, `error`, `critical`

### Implementations

#### ConsoleErrorReporter

Default error reporter that logs to stdout using Python's logging system:
- Structured error information
- Stack trace logging (at DEBUG level)
- Context as key-value pairs
- Configurable logger name

```python
from copilot_reporting import ConsoleErrorReporter

reporter = ConsoleErrorReporter(logger_name="my_service")
```

#### SilentErrorReporter

Testing error reporter that stores errors in memory:
- Zero output or side effects
- In-memory storage of errors and messages
- Query and filter capabilities
- Perfect for unit tests

```python
from copilot_reporting import SilentErrorReporter

reporter = SilentErrorReporter()

# Later in tests
assert reporter.has_errors()
errors = reporter.get_errors(error_type="ValueError")
messages = reporter.get_messages(level="error")
reporter.clear()
```

#### SentryErrorReporter

Production error reporter for cloud-based error tracking (scaffold for future use):
- Requires `sentry-sdk` package
- Environment-aware reporting
- Context propagation to Sentry
- Level mapping to Sentry severity

```python
from copilot_reporting import SentryErrorReporter

# Note: Requires pip install copilot-reporting[sentry]
reporter = SentryErrorReporter(
    dsn="https://...@sentry.io/...",
    environment="production"
)
```

### Factory Pattern

Use the factory function to select the reporter based on configuration:

```python
from copilot_reporting import create_error_reporter
import os

# Select reporter from environment variable
reporter_type = os.getenv("ERROR_REPORTER_TYPE", "console")
sentry_dsn = os.getenv("SENTRY_DSN")

reporter = create_error_reporter(
    reporter_type=reporter_type,
    dsn=sentry_dsn,
    environment="production"
)
```

### Service Integration Example

```python
from copilot_reporting import create_error_reporter

class MyService:
    def __init__(self, config):
        self.error_reporter = create_error_reporter(
            reporter_type=config.error_reporter_type,
            dsn=config.sentry_dsn
        )
    
    def process_data(self, data):
        try:
            result = self._do_processing(data)
        except Exception as e:
            # Report error with context
            self.error_reporter.report(e, context={
                "operation": "process_data",
                "data_id": data.get("id")
            })
            raise
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Coverage

```bash
pytest tests/ --cov=copilot_reporting --cov-report=html
```

### Linting

```bash
pylint copilot_reporting/
```

## Requirements

- Python 3.10+
- sentry-sdk (optional, for Sentry integration)

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
