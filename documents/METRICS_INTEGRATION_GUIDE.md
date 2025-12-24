<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Service Metrics Integration Guide

This guide explains how to integrate metrics collection into new or existing services in the Copilot-for-Consensus project.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Metrics Checklist](#metrics-checklist)
4. [Integration Steps](#integration-steps)
5. [Metrics Naming Standards](#metrics-naming-standards)
6. [Label Schema](#label-schema)
7. [Example Implementation](#example-implementation)
8. [Testing](#testing)
9. [Common Pitfalls](#common-pitfalls)
10. [Reference](#reference)

---

## Overview

All services in Copilot-for-Consensus use the `copilot_metrics` adapter for metrics collection. Services push metrics to Pushgateway, which Prometheus then scrapes.

**Architecture:**
```
Service → MetricsCollector → Pushgateway → Prometheus → Grafana
```

---

## Prerequisites

### Required Dependencies

Add to your service's `requirements.txt` or `pyproject.toml`:

```txt
prometheus-client>=0.20.0
```

### Import Metrics Adapter

```python
from copilot_metrics import get_metrics_collector, MetricsCollector
```

---

## Metrics Checklist

Every service MUST implement these baseline metrics:

### Required Metrics

- [ ] **`<service>_messages_processed_total`** (Counter)
  - Total messages processed
  - Labels: `status` (success/failure)
  
- [ ] **`<service>_processing_duration_seconds`** (Histogram)
  - Time taken to process each message
  - Buckets: `[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5, 10, 30, 60]`
  
- [ ] **`<service>_failures_total`** (Counter)
  - Total failures by error type
  - Labels: `error_type` (e.g., `ConnectionError`, `TimeoutError`)
  
- [ ] **`<service>_active_workers_current`** (Gauge)
  - Number of active workers/threads

### Optional Metrics (Recommended)

- [ ] **`<service>_queue_depth_messages`** (Gauge)
  - Current queue depth (if service manages a queue)
  - Labels: `queue`
  
- [ ] **`<service>_retry_attempts_total`** (Counter)
  - Total retry attempts
  
- [ ] **`<service>_batch_size_messages`** (Histogram)
  - Distribution of batch sizes processed

---

## Integration Steps

### Step 1: Initialize Metrics Collector

In your service's main file or `service.py`:

```python
from copilot_metrics import get_metrics_collector
import os

# Initialize metrics collector
metrics = get_metrics_collector(
    backend=os.environ.get("METRICS_BACKEND", "pushgateway"),
    pushgateway_url=os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091"),
    job_name=f"copilot-{SERVICE_NAME}",  # e.g., "copilot-parsing"
)
```

### Step 2: Define Metric Names

Follow the naming convention:

```python
SERVICE_NAME = "parsing"  # Replace with your service name

# Metric names
METRIC_MESSAGES_PROCESSED = f"copilot_{SERVICE_NAME}_messages_processed_total"
METRIC_PROCESSING_DURATION = f"copilot_{SERVICE_NAME}_processing_duration_seconds"
METRIC_FAILURES = f"copilot_{SERVICE_NAME}_failures_total"
METRIC_ACTIVE_WORKERS = f"copilot_{SERVICE_NAME}_active_workers_current"
```

### Step 3: Instrument Your Code

#### Counter Example (messages processed)

```python
def process_message(message):
    try:
        # Your processing logic here
        result = do_processing(message)
        
        # Increment success counter
        metrics.increment(
            METRIC_MESSAGES_PROCESSED,
            value=1.0,
            tags={"status": "success", "service": SERVICE_NAME}
        )
        
        return result
    except Exception as e:
        # Increment failure counter
        metrics.increment(
            METRIC_FAILURES,
            value=1.0,
            tags={
                "error_type": type(e).__name__,
                "service": SERVICE_NAME
            }
        )
        
        # Also increment total processed (with failure status)
        metrics.increment(
            METRIC_MESSAGES_PROCESSED,
            value=1.0,
            tags={"status": "failure", "service": SERVICE_NAME}
        )
        
        raise
```

#### Histogram Example (duration)

```python
import time

def process_message_with_timing(message):
    start_time = time.time()
    try:
        result = do_processing(message)
        return result
    finally:
        # Record processing duration
        duration = time.time() - start_time
        metrics.observe(
            METRIC_PROCESSING_DURATION,
            value=duration,
            tags={"service": SERVICE_NAME}
        )
```

#### Gauge Example (active workers)

```python
class WorkerPool:
    def __init__(self):
        self.active_count = 0
    
    def start_worker(self):
        self.active_count += 1
        metrics.gauge(
            METRIC_ACTIVE_WORKERS,
            value=self.active_count,
            tags={"service": SERVICE_NAME}
        )
    
    def stop_worker(self):
        self.active_count -= 1
        metrics.gauge(
            METRIC_ACTIVE_WORKERS,
            value=self.active_count,
            tags={"service": SERVICE_NAME}
        )
```

### Step 4: Push Metrics

After collecting metrics, push them to Pushgateway:

```python
def process_batch(messages):
    for message in messages:
        process_message(message)
    
    # Push metrics after processing batch
    metrics.safe_push()
```

**Note**: `safe_push()` will not raise exceptions on push failures (logs warning instead).

---

## Metrics Naming Standards

### Format

```
copilot_<subsystem>_<metric>_<unit>_<type>
```

### Examples

| Metric Name | Type | Description |
|-------------|------|-------------|
| `copilot_parsing_messages_parsed_total` | Counter | Total messages parsed |
| `copilot_parsing_duration_seconds` | Histogram | Parsing duration |
| `copilot_chunking_chunks_created_total` | Counter | Total chunks created |
| `copilot_chunking_chunk_size_tokens` | Histogram | Chunk size distribution |
| `copilot_embedding_failures_total` | Counter | Embedding failures |
| `copilot_embedding_generation_duration_seconds` | Histogram | Embedding generation time |
| `copilot_summarization_tokens_total` | Counter | LLM tokens used |
| `copilot_queue_depth_messages` | Gauge | Queue depth |

### Unit Suffixes

| Unit | Suffix | Example |
|------|--------|---------|
| Seconds | `_seconds` | `processing_duration_seconds` |
| Bytes | `_bytes` | `message_size_bytes` |
| Tokens | `_tokens` | `chunk_size_tokens` |
| Messages | `_messages` | `queue_depth_messages` |
| Count | `_total` (counter) or none (gauge) | `failures_total`, `active_workers` |

---

## Label Schema

### Required Labels (All Metrics)

```python
tags = {
    "service": "<service_name>",       # e.g., "parsing", "embedding"
    "environment": os.getenv("ENV", "dev")  # e.g., "dev", "staging", "prod"
}
```

### Status Labels

For metrics tracking outcomes:

```python
tags = {
    "status": "success",  # or "failure", "pending", "retrying"
    "outcome": "success", # or "timeout", "error"
}
```

### Error Labels

For failure metrics:

```python
tags = {
    "error_type": "ConnectionError",  # Exception class name
    "error_code": "500",              # HTTP status or error code (optional)
}
```

### Domain-Specific Labels

#### Queue Metrics
```python
tags = {
    "queue": "parsing",     # Queue name
    "vhost": "/",           # RabbitMQ virtual host
}
```

#### Database Metrics
```python
tags = {
    "collection": "archives",  # MongoDB collection or Qdrant collection
    "database": "copilot",     # Database name
}
```

### Cardinality Guidelines

**DO:**
- Use low-cardinality labels (< 100 unique values)
- Use bounded enums for status/type labels
- Group similar values into broader categories

**DON'T:**
- ❌ Use `user_id`, `email`, `ip_address`
- ❌ Use `message_id`, `document_id`, `thread_id`
- ❌ Use `timestamp`, `request_id`, `trace_id`

For high-cardinality data, use structured logs instead.

---

## Example Implementation

### Complete Service Example

```python
# parsing/app/service.py

import os
import time
import logging
from typing import Any, Dict
from copilot_metrics import get_metrics_collector

logger = logging.getLogger(__name__)

# Service configuration
SERVICE_NAME = "parsing"
ENVIRONMENT = os.getenv("ENV", "dev")

# Initialize metrics
metrics = get_metrics_collector(
    backend="pushgateway",
    pushgateway_url=os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091"),
    job_name=f"copilot-{SERVICE_NAME}",
)

# Metric names
METRIC_MESSAGES_PROCESSED = f"copilot_{SERVICE_NAME}_messages_processed_total"
METRIC_PROCESSING_DURATION = f"copilot_{SERVICE_NAME}_processing_duration_seconds"
METRIC_FAILURES = f"copilot_{SERVICE_NAME}_failures_total"
METRIC_ARCHIVES_PROCESSED = f"copilot_{SERVICE_NAME}_archives_processed_total"
METRIC_THREADS_CREATED = f"copilot_{SERVICE_NAME}_threads_created_total"

class ParsingService:
    def process_message(self, message: Dict[str, Any]) -> None:
        """Process a single message from the queue."""
        start_time = time.time()
        
        try:
            # Extract archive from message
            archive_id = message["archive_id"]
            logger.info(f"Processing archive: {archive_id}")
            
            # Parse archive (your logic here)
            result = self._parse_archive(archive_id)
            
            # Record success metrics
            metrics.increment(
                METRIC_MESSAGES_PROCESSED,
                value=1.0,
                tags={"status": "success", "service": SERVICE_NAME, "environment": ENVIRONMENT}
            )
            
            metrics.increment(
                METRIC_ARCHIVES_PROCESSED,
                value=1.0,
                tags={"status": "success", "service": SERVICE_NAME}
            )
            
            if "threads_created" in result:
                metrics.increment(
                    METRIC_THREADS_CREATED,
                    value=result["threads_created"],
                    tags={"service": SERVICE_NAME}
                )
            
            logger.info(f"Successfully processed archive: {archive_id}")
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)
            
            # Record failure metrics
            metrics.increment(
                METRIC_FAILURES,
                value=1.0,
                tags={
                    "error_type": type(e).__name__,
                    "service": SERVICE_NAME,
                    "environment": ENVIRONMENT
                }
            )
            
            metrics.increment(
                METRIC_MESSAGES_PROCESSED,
                value=1.0,
                tags={"status": "failure", "service": SERVICE_NAME, "environment": ENVIRONMENT}
            )
            
            raise
        
        finally:
            # Always record duration
            duration = time.time() - start_time
            metrics.observe(
                METRIC_PROCESSING_DURATION,
                value=duration,
                tags={"service": SERVICE_NAME, "environment": ENVIRONMENT}
            )
            
            # Push metrics to Pushgateway
            metrics.safe_push()
    
    def _parse_archive(self, archive_id: str) -> Dict[str, Any]:
        """Parse an archive (placeholder for actual logic)."""
        # Your parsing logic here
        return {"threads_created": 5}
```

---

## Testing

### Unit Tests

Test metrics collection without actual Pushgateway:

```python
# tests/test_parsing_metrics.py

from unittest.mock import MagicMock
from copilot_metrics import MetricsCollector

def test_metrics_collected():
    # Mock metrics collector
    metrics = MagicMock(spec=MetricsCollector)
    
    # Process message
    service = ParsingService()
    service.metrics = metrics  # Inject mock
    service.process_message({"archive_id": "test-123"})
    
    # Verify metrics were called
    assert metrics.increment.called
    assert metrics.observe.called
    assert metrics.safe_push.called
```

### Integration Tests

Test metrics in running system:

```bash
# Start services
docker compose up -d parsing pushgateway monitoring

# Process a message
# (trigger your service to process something)

# Check metrics in Pushgateway
curl http://localhost:9091/metrics | grep copilot_parsing

# Check metrics in Prometheus
curl 'http://localhost:9090/api/v1/query?query=copilot_parsing_messages_processed_total'
```

### Verify in Grafana

1. Open Grafana: http://localhost:8080/grafana/
2. Go to Explore
3. Run PromQL query:
   ```promql
   rate(copilot_parsing_messages_processed_total[5m])
   ```
4. Verify data appears

---

## Common Pitfalls

### ❌ Forgetting to Push Metrics

```python
# BAD: Metrics collected but never pushed
metrics.increment("my_metric", 1.0)
# Missing: metrics.safe_push()
```

**Solution**: Always call `metrics.safe_push()` after collecting metrics.

### ❌ High-Cardinality Labels

```python
# BAD: Using message_id as label
metrics.increment("messages_processed", 1.0, tags={"message_id": msg_id})
```

**Solution**: Use logs for high-cardinality data, not metrics labels.

### ❌ Inconsistent Naming

```python
# BAD: Inconsistent naming
metrics.increment("parsing_total", 1.0)           # Missing namespace
metrics.increment("copilot_parsing_count", 1.0)   # Wrong suffix
```

**Solution**: Follow naming convention: `copilot_<service>_<metric>_<type>`

### ❌ Missing Error Handling

```python
# BAD: Metrics push failure crashes service
metrics.push()  # Can raise exceptions
```

**Solution**: Use `safe_push()` which logs errors but doesn't raise.

### ❌ Not Recording Duration in Finally Block

```python
# BAD: Duration not recorded on exception
start = time.time()
do_work()
metrics.observe("duration_seconds", time.time() - start)
```

**Solution**: Use try/finally:
```python
start = time.time()
try:
    do_work()
finally:
    metrics.observe("duration_seconds", time.time() - start)
```

---

## Reference

### Metric Types

| Type | Usage | Aggregation |
|------|-------|-------------|
| **Counter** | Monotonically increasing (resets on restart) | `rate()`, `increase()` |
| **Gauge** | Point-in-time value (can go up/down) | `avg()`, `min()`, `max()` |
| **Histogram** | Distribution of values | `histogram_quantile()` |
| **Summary** | Similar to histogram (not recommended) | N/A |

### PromQL Queries

```promql
# Throughput (requests/sec)
rate(copilot_parsing_messages_processed_total[5m])

# P95 latency
histogram_quantile(0.95, rate(copilot_parsing_duration_seconds_bucket[5m]))

# Error rate (%)
(rate(copilot_parsing_failures_total[5m]) / rate(copilot_parsing_messages_processed_total[5m])) * 100

# Total errors by type
sum by (error_type) (copilot_parsing_failures_total)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_BACKEND` | `pushgateway` | Metrics backend (pushgateway, prometheus, noop) |
| `PUSHGATEWAY_URL` | `http://pushgateway:9091` | Pushgateway URL |
| `ENV` | `dev` | Environment label (dev/staging/prod) |

---

## Documentation Links

- [Observability RFC](../docs/OBSERVABILITY_RFC.md) - Full observability strategy
- [Service Monitoring Guide](./SERVICE_MONITORING.md) - Monitoring overview
- [Prometheus Best Practices](https://prometheus.io/docs/practices/) - Official Prometheus docs
- [copilot_metrics Adapter](../adapters/copilot_metrics/README.md) - Metrics adapter docs

---

## Getting Help

- **Slack**: #observability channel
- **Issues**: GitHub Issues with `observability` label
- **Docs**: See `documents/SERVICE_MONITORING.md` for troubleshooting
