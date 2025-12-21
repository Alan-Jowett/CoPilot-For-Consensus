<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Metrics Collection Abstraction

The metrics collection abstraction provides a pluggable interface for collecting observability metrics across different backends (Prometheus, OpenTelemetry, StatsD, etc.).

## Features

- **Pluggable backends**: Easily switch between NoOp (for testing), Prometheus, or other metrics backends
- **Consistent API**: Uniform interface for counters, histograms, and gauges
- **Tag support**: Add labels/tags to metrics for better categorization
- **Environment-based configuration**: Configure backend via environment variables
- **Production-ready**: Prometheus integration for production observability

## Quick Start

### Basic Usage

```python
from copilot_metrics import create_metrics_collector

# Create a metrics collector (auto-detects from METRICS_BACKEND env var)
metrics = create_metrics_collector()

# Increment a counter
metrics.increment("requests_total", tags={"method": "GET", "status": "200"})

# Observe a value (histogram)
metrics.observe("request_duration_seconds", 0.123, tags={"endpoint": "/api/v1"})

# Set a gauge
metrics.gauge("active_connections", 42)
```

### Configuration

Configure the metrics backend using the `METRICS_BACKEND` environment variable:

```bash
# For local development and testing (default)
METRICS_BACKEND=noop

# For production with Prometheus
METRICS_BACKEND=prometheus

# For production with Prometheus Pushgateway
METRICS_BACKEND=pushgateway

# For Azure-native deployments
METRICS_BACKEND=azure_monitor
```

Or specify backend explicitly in code:

```python
# NoOp collector (no dependencies)
metrics = create_metrics_collector(backend="noop")

# Prometheus collector (requires prometheus_client)
metrics = create_metrics_collector(backend="prometheus")
```

## Metric Types

### Counter

Counters track cumulative values that only increase (e.g., request count, errors).

```python
# Increment by 1 (default)
metrics.increment("http_requests_total")

# Increment by custom amount
metrics.increment("bytes_processed", value=1024)

# With tags/labels
metrics.increment("api_calls", tags={
    "service": "ingestion",
    "method": "POST",
    "status": "200"
})
```

### Histogram/Summary

Histograms observe values to create distributions (e.g., request duration, file size).

```python
import time

start = time.time()
# ... do some work ...
duration = time.time() - start

metrics.observe("processing_duration_seconds", duration, tags={
    "operation": "parse_archive"
})
```

### Gauge

Gauges represent values that can go up or down (e.g., queue depth, memory usage).

```python
# Set gauge to current value
metrics.gauge("queue_depth", current_queue_size)
metrics.gauge("memory_usage_bytes", get_memory_usage())

# With tags
metrics.gauge("active_threads", thread_count, tags={
    "service": "embedding"
})
```

## Backend Implementations

### NoOpMetricsCollector

The NoOp collector stores metrics in memory without external dependencies. Perfect for:

- Local development
- Testing
- Debugging metrics instrumentation

```python
from copilot_metrics import NoOpMetricsCollector

metrics = NoOpMetricsCollector()

# Collect some metrics
metrics.increment("test_counter", value=5)
metrics.observe("test_histogram", 1.5)

# Access collected metrics (useful for testing)
assert metrics.get_counter_total("test_counter") == 5.0
assert metrics.get_observations("test_histogram") == [1.5]

# Clear metrics between tests
metrics.clear_metrics()
```

### PrometheusMetricsCollector

The Prometheus collector integrates with Prometheus for production observability.

**Installation:**

```bash
pip install prometheus-client
```

**Usage:**

```python
from copilot_metrics import PrometheusMetricsCollector
from prometheus_client import start_http_server

# Create collector with custom namespace
metrics = PrometheusMetricsCollector(namespace="copilot")

# Start Prometheus HTTP server to expose metrics
start_http_server(8000)  # Metrics available at http://localhost:8000/metrics

# Collect metrics
metrics.increment("requests_total", tags={"service": "ingestion"})
metrics.observe("request_duration_seconds", 0.123)
metrics.gauge("queue_depth", 10)
```

**Prometheus Configuration:**

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'copilot-services'
    static_configs:
      - targets: ['ingestion:8000', 'parsing:8000', 'embedding:8000']
```

## Service Integration Example

Here's how to integrate metrics into a microservice:

```python
import os
import logging
from copilot_metrics import create_metrics_collector
from copilot_events import EventPublisher

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher
        # Initialize metrics collector from environment
        self.metrics = create_metrics_collector()
        logger.info(f"Metrics collector initialized: {type(self.metrics).__name__}")
    
    def ingest_archive(self, archive_id: str, source: str):
        """Ingest an archive and emit metrics."""
        # Measure processing time - initialize before try block
        import time
        start_time = time.time()
        
        try:
            # Track that we started processing
            self.metrics.increment("archives_started", tags={
                "source": source
            })
            
            # ... actual ingestion logic ...
            
            duration = time.time() - start_time
            
            # Record success metrics
            self.metrics.increment("archives_ingested", tags={
                "source": source,
                "status": "success"
            })
            self.metrics.observe("ingestion_duration_seconds", duration, tags={
                "source": source
            })
            
            logger.info(f"Archive {archive_id} ingested in {duration:.2f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Track failures
            self.metrics.increment("archives_ingested", tags={
                "source": source,
                "status": "error"
            })
            self.metrics.increment("ingestion_errors", tags={
                "source": source,
                "error_type": type(e).__name__
            })
            logger.error(f"Failed to ingest archive {archive_id}: {e}")
            raise
```

## Best Practices

### Naming Conventions

Follow these conventions for metric names:

- Use snake_case: `http_requests_total`, not `httpRequestsTotal`
- Include units: `request_duration_seconds`, `file_size_bytes`
- Use descriptive names: `parsing_errors_total`, not just `errors`
- Suffix counters with `_total`: `requests_total`, `bytes_processed_total`

### Tags/Labels

- Keep tag cardinality low (avoid user IDs, timestamps, etc.)
- Use consistent tag names across services
- Common tags: `service`, `operation`, `status`, `method`, `error_type`

### Metrics to Collect

Recommended metrics for each service:

**Counters:**
- Request/operation counts: `{service}_requests_total`
- Success/error counts: `{service}_errors_total`
- Items processed: `{service}_items_processed_total`

**Histograms:**
- Processing duration: `{service}_duration_seconds`
- Item sizes: `{service}_item_size_bytes`

**Gauges:**
- Queue depth: `{service}_queue_depth`
- Active connections: `{service}_active_connections`
- Resource usage: `{service}_memory_usage_bytes`

## Testing

Use the NoOp collector in tests to verify metrics are emitted correctly:

```python
import pytest
from copilot_metrics import NoOpMetricsCollector
from myapp.service import MyService

def test_service_emits_metrics():
    """Test that service emits expected metrics."""
    metrics = NoOpMetricsCollector()
    service = MyService(metrics=metrics)
    
    # Exercise the service
    service.process_item("test-item")
    
    # Verify metrics were emitted
    assert metrics.get_counter_total("items_processed") == 1.0
    assert len(metrics.get_observations("processing_duration")) == 1
    
    # Verify tags
    assert metrics.get_counter_total(
        "items_processed",
        tags={"status": "success"}
    ) == 1.0
```

## Troubleshooting

### Prometheus metrics not appearing

1. Ensure `prometheus_client` is installed:
   ```bash
   pip install prometheus-client
   ```

2. Verify metrics HTTP endpoint is exposed:
   ```python
   from prometheus_client import start_http_server
   start_http_server(8000)
   ```

3. Check Prometheus configuration points to correct target

### High cardinality warnings

If you see warnings about high cardinality:
- Avoid using IDs, timestamps, or unbounded values as tags
- Use status codes instead of full URLs
- Group similar values into categories

## Azure Monitor Integration

### AzureMonitorMetricsCollector

The Azure Monitor collector integrates with Azure Monitor (Application Insights) using OpenTelemetry for Azure-native observability in production deployments.

**Installation:**

```bash
pip install copilot-metrics[azure]
# Or manually:
pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk
```

**Configuration:**

Azure Monitor requires a connection string or instrumentation key. Configure via environment variables:

```bash
# Recommended: Use connection string (includes endpoint and instrumentation key)
export AZURE_MONITOR_CONNECTION_STRING="InstrumentationKey=<your-key>;IngestionEndpoint=https://..."

# Alternative: Use instrumentation key only (legacy)
export AZURE_MONITOR_INSTRUMENTATION_KEY="<your-instrumentation-key>"

# Optional: Customize metric namespace (default: "copilot")
export AZURE_MONITOR_METRIC_NAMESPACE="myapp"

# Optional: Customize export interval in milliseconds (default: 60000)
export AZURE_MONITOR_EXPORT_INTERVAL_MILLIS="30000"

# Set the metrics backend
export METRICS_BACKEND="azure_monitor"
```

**Getting Connection String:**

1. Create an Application Insights resource in Azure Portal
2. Navigate to your Application Insights resource
3. Copy the "Connection String" from the Overview page

**Usage:**

```python
from copilot_metrics import create_metrics_collector

# Auto-detect from environment
metrics = create_metrics_collector()  # Uses METRICS_BACKEND env var

# Or explicitly create Azure Monitor collector
metrics = create_metrics_collector(backend="azure_monitor")

# Or create directly with parameters
from copilot_metrics import AzureMonitorMetricsCollector

metrics = AzureMonitorMetricsCollector(
    connection_string="InstrumentationKey=...",
    namespace="copilot",
    export_interval_millis=60000
)

# Collect metrics (same API as other collectors)
metrics.increment("requests_total", tags={"service": "ingestion", "status": "success"})
metrics.observe("request_duration_seconds", 0.123, tags={"endpoint": "/api"})
metrics.gauge("active_connections", 42)

# Gracefully shutdown on application exit
metrics.shutdown()
```

**Azure Monitor Features:**

- **Asynchronous Export**: Metrics are batched and exported periodically (default: every 60 seconds)
- **Dimensions**: Tags/labels are mapped to Azure Monitor custom dimensions
- **OpenTelemetry Standard**: Uses OpenTelemetry SDK for portability
- **Resource Attributes**: Service name and namespace are included as resource attributes

**Local Development:**

For local development without Azure credentials, use the NoOp collector:

```bash
export METRICS_BACKEND="noop"
```

**Viewing Metrics in Azure:**

1. Navigate to your Application Insights resource in Azure Portal
2. Go to "Metrics" section
3. Select "Custom" metric namespace
4. Choose your metric (e.g., `copilot.requests_total`)
5. Add filters using dimensions (tags)

**Example Queries in Application Insights:**

```kusto
// View all custom metrics
customMetrics
| where name startswith "copilot."
| summarize sum(value) by name, bin(timestamp, 5m)

// Filter by dimensions
customMetrics
| where name == "copilot.requests_total"
| where customDimensions.service == "ingestion"
| summarize requests = sum(value) by status=tostring(customDimensions.status)
```

**Best Practices for Azure Monitor:**

- Use consistent tag names across services for better correlation
- Keep dimension cardinality reasonable (avoid high-cardinality values like user IDs)
- Use meaningful metric names with units (e.g., `request_duration_seconds`)
- Monitor your Application Insights quota and pricing
- Call `shutdown()` on application termination to flush remaining metrics

**Docker/Kubernetes Deployment:**

```yaml
# docker-compose.yml
services:
  myservice:
    environment:
      - METRICS_BACKEND=azure_monitor
      - AZURE_MONITOR_CONNECTION_STRING=${AZURE_MONITOR_CONNECTION_STRING}
      - AZURE_MONITOR_METRIC_NAMESPACE=copilot
```

```yaml
# Kubernetes ConfigMap/Secret
apiVersion: v1
kind: Secret
metadata:
  name: azure-monitor-config
type: Opaque
stringData:
  connection-string: "InstrumentationKey=..."
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: metrics-config
data:
  METRICS_BACKEND: "azure_monitor"
  AZURE_MONITOR_METRIC_NAMESPACE: "copilot"
```

**Identity and Permissions:**

Azure Monitor uses the connection string for authentication. No additional Azure RBAC permissions are required. The connection string includes the instrumentation key which grants write access to the Application Insights resource.

For enhanced security in production:
- Store connection strings in Azure Key Vault
- Use managed identities where possible
- Rotate instrumentation keys periodically
- Restrict network access to Application Insights endpoints

**Troubleshooting:**

1. **Metrics not appearing in Azure Portal:**
   - Check connection string is correct
   - Verify export interval has elapsed (default: 60 seconds)
   - Check Application Insights quota and throttling limits
   - Look for errors in application logs

2. **High latency or performance impact:**
   - Increase export interval: `AZURE_MONITOR_EXPORT_INTERVAL_MILLIS=120000`
   - Ensure async export is working (should not block application)

3. **Missing dimensions:**
   - Verify tags are provided as dictionaries
   - Check dimension names are valid (alphanumeric, underscore)
   - Note: Observable gauges have limited dimension support

## Future Extensions

Potential future backends:

- **StatsD**: For DataDog, Graphite integration  
- **CloudWatch**: AWS native metrics
- **Custom backends**: Implement `MetricsCollector` interface

To add a new backend:

```python
from copilot_metrics.metrics import MetricsCollector

class MyCustomCollector(MetricsCollector):
    def increment(self, name, value=1.0, tags=None):
        # Custom implementation
        pass
    
    def observe(self, name, value, tags=None):
        # Custom implementation
        pass
    
    def gauge(self, name, value, tags=None):
        # Custom implementation
        pass
```
