<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Error Reporting Service

A lightweight error aggregation service for Copilot-for-Consensus microservices.

## Overview

The Error Reporting Service provides centralized error tracking and visualization for all microservices in the Copilot-for-Consensus system. It receives structured error events, stores them in memory, and provides both a web UI and REST API for viewing and filtering errors.

## Features

- **REST API** for error submission and retrieval
- **Web UI** for browsing and filtering errors
- **In-memory storage** with configurable limits (10,000 errors by default)
- **Statistics dashboard** showing error counts by service, level, and type
- **Filtering** by service, error level, and error type
- **Structured error events** with context, stack traces, and metadata

## API Endpoints

### POST /api/errors
Submit a new error event.

**Request Body:**
```json
{
  "service": "ingestion",
  "level": "error",
  "message": "Failed to connect to message bus",
  "error_type": "ConnectionError",
  "stack_trace": "Traceback...",
  "context": {
    "host": "messagebus",
    "port": 5672
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "error_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### GET /api/errors
Retrieve errors with optional filtering.

**Query Parameters:**
- `service` - Filter by service name
- `level` - Filter by error level (error, warning, critical, info)
- `error_type` - Filter by error type
- `limit` - Maximum number of errors to return (default: 100, max: 1000)
- `offset` - Number of errors to skip (default: 0)

**Example:**
```
GET /api/errors?service=ingestion&level=error&limit=50
```

### GET /api/errors/{error_id}
Get a specific error by ID.

### GET /api/stats
Get error statistics.

**Response:**
```json
{
  "total_errors": 42,
  "by_service": {
    "ingestion": 15,
    "parsing": 10,
    "embedding": 17
  },
  "by_level": {
    "error": 30,
    "warning": 10,
    "critical": 2
  },
  "by_type": {
    "ConnectionError": 5,
    "ValueError": 3
  }
}
```

### GET /ui
Web interface for viewing errors (browser-friendly).

## Web UI

Access the web UI at `http://localhost:8081/ui` to:
- View recent errors in a table
- Filter by service and error level
- See statistics for total errors, errors by service, and errors by level

## Integration with Services

Services can report errors by sending POST requests to the `/api/errors` endpoint. For Python services using the `copilot_reporting` adapter, you can extend the `ConsoleErrorReporter` to also send errors to this service.

**Example:**
```python
import requests

def report_error_to_service(service_name, level, message, error_type=None, stack_trace=None, context=None):
    """Report an error to the error reporting service."""
    try:
        response = requests.post(
            "http://error-reporting:8081/api/errors",
            json={
                "service": service_name,
                "level": level,
                "message": message,
                "error_type": error_type,
                "stack_trace": stack_trace,
                "context": context
            },
            timeout=5
        )
        return response.status_code == 201
    except Exception as e:
        # Don't fail the main application if error reporting fails
        print(f"Failed to report error: {e}")
        return False
```

## Configuration

The service has minimal configuration:
- **Port**: 8081 (configurable via environment or code)
- **Max Errors**: 10,000 errors in memory (configurable in code)

## Development

### Running Locally
```bash
cd error-reporting
pip install -r requirements.txt
python main.py
```

### Running with Docker
```bash
docker compose up error-reporting
```

## Future Enhancements

Potential improvements for production use:
- Persistent storage (MongoDB, PostgreSQL)
- Authentication and authorization
- Email/Slack notifications for critical errors
- Error grouping and deduplication
- Rate limiting
- Data retention policies
- Integration with Sentry SDK for more features

## License

MIT License - see LICENSE file for details.
