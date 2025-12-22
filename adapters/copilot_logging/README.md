<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Logging Adapter

A pluggable logging abstraction layer for Copilot-for-Consensus microservices.

## Features

- **Abstract Logger Interface**: Common interface for all logger implementations
- **Structured JSON Output**: StdoutLogger provides structured JSON logs for observability
- **Silent Testing**: SilentLogger stores logs in memory for testing without output
- **Environment Configuration**: Easy configuration via environment variables
- **Factory Pattern**: Simple factory function for creating loggers
- **Uvicorn Integration**: Built-in configuration for FastAPI/Uvicorn HTTP access logs with DEBUG-level health checks

## Installation

The `copilot_logging` module is a standalone package with its own setup.py. Install it in editable mode for development:

```bash
cd adapters/copilot_logging
pip install -e .
```

## Usage

### Basic Usage

```python
from copilot_logging import create_logger

# Create a logger (defaults: LOG_TYPE/LOG_LEVEL/LOG_NAME env or stdout/INFO/copilot)
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

# Create logger from environment (falls back to stdout/INFO/copilot)
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

### AzureMonitorLogger

Sends structured logs to Azure Monitor / Application Insights for cloud-native observability. Ideal for production Azure deployments with full distributed tracing support.

```python
import os
from copilot_logging import create_logger

# Configure Azure Monitor connection
os.environ['AZURE_MONITOR_CONNECTION_STRING'] = 'InstrumentationKey=xxx;IngestionEndpoint=https://...'

# Create Azure Monitor logger
logger = create_logger(logger_type="azuremonitor", level="INFO", name="prod-service")

# Log with correlation IDs for distributed tracing
logger.info(
    "Request processed",
    correlation_id="corr-123",
    trace_id="trace-456",
    user_id=789,
    duration_ms=123.45
)
```

**Features:**
- Automatic export to Azure Monitor / Application Insights
- Support for correlation IDs and distributed tracing
- Custom dimensions for structured data
- Graceful fallback to console logging if Azure Monitor is unavailable
- Compatible with Azure Monitor dashboards, alerts, and queries

**Environment Variables:**
- `AZURE_MONITOR_CONNECTION_STRING`: Connection string for Azure Monitor (required to enable Azure Monitor logging; if unset, logs are written to console only)
- `AZURE_MONITOR_INSTRUMENTATION_KEY`: Legacy instrumentation key (deprecated, use connection string)
- `AZURE_MONITOR_CONSOLE_LOG`: Set to "true" to also log to console for local debugging (optional)

**Installation:**

The Azure Monitor logger requires additional dependencies. Install them with:

```bash
pip install copilot-logging[azuremonitor]
```

Or manually:

```bash
pip install azure-monitor-opentelemetry-exporter opentelemetry-api opentelemetry-sdk
```

**Fallback Behavior:**

If the Azure Monitor SDK is not installed or the connection string is not configured, the logger automatically falls back to console logging with a warning message. This ensures your application continues to run even without Azure Monitor configured.

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

### Uvicorn Integration (FastAPI/HTTP Services)

For FastAPI services using Uvicorn, use the `create_uvicorn_log_config` function to configure structured JSON logging for HTTP access logs:

```python
# main.py
from fastapi import FastAPI
import uvicorn
from copilot_logging import create_logger, create_uvicorn_log_config

# Create structured logger for application logs
logger = create_logger(logger_type="stdout", level="INFO", name="parsing")

# Create FastAPI app
app = FastAPI(title="Parsing Service")

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

def main():
    logger.info("Starting FastAPI server on port 8000")
    
    # Configure Uvicorn with structured JSON logging
    # Health check logs will be at DEBUG level
    log_config = create_uvicorn_log_config(service_name="parsing", log_level="INFO")
    
    # Start server with custom log configuration
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=log_config)

if __name__ == "__main__":
    main()
```

**Key features:**
- **Structured JSON output**: All Uvicorn logs use the same JSON format as application logs
- **DEBUG-level access logs**: Health check and other access logs are at DEBUG level to reduce noise
- **Consistent format**: Access logs match the format of application logs

**Sample output:**
```json
{"timestamp": "2025-12-18T18:30:00.000000Z", "level": "INFO", "logger": "parsing", "message": "Starting FastAPI server on port 8000"}
{"timestamp": "2025-12-18T18:30:01.123456Z", "level": "INFO", "logger": "parsing", "message": "Started server process"}
{"timestamp": "2025-12-18T18:30:05.234567Z", "level": "DEBUG", "logger": "parsing", "message": "127.0.0.1:36210 - \"GET /health HTTP/1.1\" 200 OK"}
```

**Note:** Health check logs at DEBUG level are hidden by default when running at INFO level. To see them, set the log level to DEBUG:

```python
log_config = create_uvicorn_log_config("parsing", "DEBUG")
```

## Benefits

1. **Consistent Logging**: All services use the same logging interface
2. **Structured Data**: JSON output enables easy parsing and analysis
3. **Testability**: Silent logger makes testing logging behavior easy
4. **Observability**: Structured logs integrate well with monitoring tools
5. **Flexibility**: Easy to add new logger backends (e.g., cloud logging)
6. **Cloud-Native**: Azure Monitor logger provides enterprise observability with distributed tracing

## Azure Monitor Deployment Guide

### Prerequisites

1. **Azure Monitor Workspace**: Create an Application Insights resource in Azure Portal
2. **Connection String**: Obtain the connection string from your Application Insights resource
3. **SDK Installation**: Install the Azure Monitor dependencies

### Setup Steps

#### 1. Create Azure Application Insights Resource

Using Azure CLI:

```bash
# Create resource group (if needed)
az group create --name myResourceGroup --location eastus

# Create Application Insights
az monitor app-insights component create \
  --app myapp-insights \
  --location eastus \
  --resource-group myResourceGroup \
  --application-type web

# Get connection string
az monitor app-insights component show \
  --app myapp-insights \
  --resource-group myResourceGroup \
  --query connectionString -o tsv
```

Or use the Azure Portal:
1. Navigate to Azure Portal → Create a resource → Application Insights
2. Fill in the required fields and create the resource
3. Copy the Connection String from the Overview page

#### 2. Install Dependencies

```bash
pip install copilot-logging[azuremonitor]
```

#### 3. Configure Environment Variables

For local development (`.env` file):

```bash
AZURE_MONITOR_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=https://...
LOG_TYPE=azuremonitor
LOG_LEVEL=INFO
LOG_NAME=my-service
```

For Docker (docker-compose.yml):

```yaml
services:
  my-service:
    environment:
      - AZURE_MONITOR_CONNECTION_STRING=${AZURE_MONITOR_CONNECTION_STRING}
      - LOG_TYPE=azuremonitor
      - LOG_LEVEL=INFO
      - LOG_NAME=my-service
```

For Kubernetes (deployment.yaml):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: azure-monitor-secret
type: Opaque
stringData:
  connection-string: InstrumentationKey=xxx;IngestionEndpoint=https://...
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  template:
    spec:
      containers:
      - name: my-service
        env:
        - name: AZURE_MONITOR_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: azure-monitor-secret
              key: connection-string
        - name: LOG_TYPE
          value: "azuremonitor"
        - name: LOG_LEVEL
          value: "INFO"
```

#### 4. Update Application Code

```python
from copilot_logging import create_logger

# Logger will automatically use Azure Monitor if configured
logger = create_logger()

# Start logging
logger.info("Service started", version="1.0.0", environment="production")
```

### Querying Logs in Azure Monitor

Once your logs are flowing to Azure Monitor, you can query them using Kusto Query Language (KQL):

#### View Recent Logs

```kusto
traces
| where timestamp > ago(1h)
| where customDimensions.logger == "my-service"
| project timestamp, message, severityLevel, customDimensions
| order by timestamp desc
```

#### Filter by Log Level

```kusto
traces
| where severityLevel >= 3  // WARNING and ERROR only
| where customDimensions.logger == "my-service"
| project timestamp, message, severityLevel
```

#### Track Request Performance

```kusto
traces
| where message has "Request processed"
| extend duration_ms = toreal(customDimensions.duration_ms)
| summarize avg(duration_ms), percentile(duration_ms, 95) by bin(timestamp, 5m)
```

#### Distributed Tracing with Correlation IDs

```kusto
traces
| where customDimensions.correlation_id == "corr-123"
| order by timestamp asc
| project timestamp, message, customDimensions
```

### Best Practices

1. **Use Correlation IDs**: Always pass correlation_id for distributed tracing across services
2. **Structured Data**: Use custom dimensions for queryable fields
3. **Log Levels**: Use appropriate log levels (INFO for normal flow, WARNING for issues, ERROR for failures)
4. **Sensitive Data**: Never log passwords, tokens, or PII in logs
5. **Cost Management**: Monitor your Application Insights data ingestion to control costs
6. **Sampling**: For high-volume applications, consider configuring sampling in Application Insights

### Monitoring and Alerts

Set up alerts in Azure Monitor based on log patterns:

1. Navigate to your Application Insights resource → Alerts → New alert rule
2. Create conditions based on log queries (e.g., error rate > threshold)
3. Configure action groups for notifications (email, SMS, webhook)

### Troubleshooting

**Logs not appearing in Azure Monitor:**
- Verify connection string is correct
- Check network connectivity to Azure endpoints
- Review application logs for Azure Monitor SDK errors
- Ensure firewall allows outbound HTTPS to Azure endpoints

**High latency:**
- Azure Monitor uses batch export by default (may take 1-2 minutes)
- For real-time debugging, enable console logging with `AZURE_MONITOR_CONSOLE_LOG=true`

**Fallback mode activated:**
- Check if Azure Monitor SDK is installed: `pip list | grep azure-monitor`
- Verify AZURE_MONITOR_CONNECTION_STRING environment variable is set
- Review application startup logs for configuration errors

## Future Enhancements

Potential future logger implementations:

- **FileLogger**: Log rotation and file-based logging
- **SyslogLogger**: Integration with syslog
- **MultiLogger**: Fan-out to multiple backends simultaneously
- **AWS CloudWatch Logger**: Integration with AWS CloudWatch Logs
- **GCP Cloud Logging Logger**: Integration with Google Cloud Logging

## API Reference

### `create_logger(logger_type, level, name)`

Factory function to create logger instances.

**Parameters:**
- `logger_type` (str, optional): Type of logger ("stdout", "silent", "azuremonitor"). Defaults to "stdout".
- `level` (str, optional): Log level ("DEBUG", "INFO", "WARNING", "ERROR"). Defaults to "INFO".
- `name` (str, optional): Logger name for identification. Defaults to "copilot".

**Returns:**
- `Logger`: Logger instance

### `create_uvicorn_log_config(service_name, log_level)`

Create Uvicorn logging configuration with structured JSON output.

**Parameters:**
- `service_name` (str): Name of the service for log identification
- `log_level` (str, optional): Default log level ("DEBUG", "INFO", "WARNING", "ERROR"). Defaults to "INFO".

**Returns:**
- `dict`: Dictionary compatible with Uvicorn's `log_config` parameter

**Features:**
- Configures structured JSON logging for all Uvicorn logs
- Sets access logs (including health checks) to DEBUG level
- Uses INFO level for error logs
- Integrates seamlessly with copilot_logging format

**Example:**
```python
from copilot_logging import create_uvicorn_log_config
import uvicorn

log_config = create_uvicorn_log_config("parsing", "INFO")
uvicorn.run(app, host="0.0.0.0", port=8000, log_config=log_config)
```

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

### `AzureMonitorLogger` (Additional Methods)

**Methods:**
- `is_fallback_mode()`: Returns True if using fallback console logging, False if using Azure Monitor

**Configuration:**
- Requires `AZURE_MONITOR_CONNECTION_STRING` or `AZURE_MONITOR_INSTRUMENTATION_KEY` environment variable
- Optional: `AZURE_MONITOR_CONSOLE_LOG=true` to enable console logging alongside Azure Monitor
- Automatically falls back to console logging if Azure Monitor is not configured or SDK is not installed

**Special Parameters:**
All logging methods support these optional keyword arguments:
- `correlation_id`: Correlation ID for distributed tracing
- `trace_id`: Trace ID for distributed tracing
- `exc_info`: Exception information (bool or tuple) for exception logging
- Any other keyword arguments become custom dimensions in Azure Monitor

## License

MIT License - See LICENSE file for details.
