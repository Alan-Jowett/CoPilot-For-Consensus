<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Service Metrics Integration Guide

How to integrate metrics collection into services using `copilot_metrics`, Pushgateway, Prometheus, and Grafana.

## Overview
Pipeline: Service → MetricsCollector → Pushgateway → Prometheus → Grafana. Dependencies: `prometheus-client>=0.20.0` and `copilot_metrics` adapter.

## Metrics Checklist (baseline)
- `copilot_<service>_messages_processed_total` (Counter, labels: status)
- `copilot_<service>_processing_duration_seconds` (Histogram, buckets: `[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5, 10, 30, 60]`)
- `copilot_<service>_failures_total` (Counter, labels: error_type)
- `copilot_<service>_active_workers_current` (Gauge)
Optional: queue depth (Gauge), retry attempts (Counter), batch sizes (Histogram).

## Integration Steps
1) Initialize collector:
```python
from copilot_metrics import get_metrics_collector
import os

metrics = get_metrics_collector(
    backend=os.environ.get("METRICS_BACKEND", "pushgateway"),
    pushgateway_url=os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091"),
    job_name=f"copilot-{SERVICE_NAME}",
)
```
2) Define metric names:
```python
SERVICE_NAME = "parsing"
METRIC_MESSAGES_PROCESSED = f"copilot_{SERVICE_NAME}_messages_processed_total"
METRIC_PROCESSING_DURATION = f"copilot_{SERVICE_NAME}_processing_duration_seconds"
METRIC_FAILURES = f"copilot_{SERVICE_NAME}_failures_total"
METRIC_ACTIVE_WORKERS = f"copilot_{SERVICE_NAME}_active_workers_current"
```
3) Instrument code (counters/histograms/gauges). Example:
```python
def process_message(msg):
    start = time.time()
    try:
        ...
        metrics.increment(METRIC_MESSAGES_PROCESSED, 1.0, tags={"status": "success", "service": SERVICE_NAME})
    except Exception as e:
        metrics.increment(METRIC_FAILURES, 1.0, tags={"error_type": type(e).__name__, "service": SERVICE_NAME})
        metrics.increment(METRIC_MESSAGES_PROCESSED, 1.0, tags={"status": "failure", "service": SERVICE_NAME})
        raise
    finally:
        metrics.observe(METRIC_PROCESSING_DURATION, value=time.time() - start, tags={"service": SERVICE_NAME})
        metrics.safe_push()
```
4) Push metrics with `safe_push()` (non-throwing).

## Naming Standards
Format: `copilot_<service>_<metric>_<unit|type>`. Use `_seconds`, `_bytes`, `_tokens`, `_messages`, `_total` suffixes appropriately. Keep labels low-cardinality.

## Labels
- Required: `service`, `environment` (e.g., ENV env var)
- Status/outcome labels for counters; `error_type` for failures
- Domain labels: `queue`, `collection`, `database` (bounded values)
- Avoid high-cardinality fields (user_id, message_id, timestamps)

## Common Pitfalls
- Forgetting `safe_push()`
- High-cardinality labels
- Inconsistent naming (missing `copilot_` prefix or unit suffix)
- Not recording durations in `finally`

## Testing
- Unit: inject mocked `MetricsCollector` and assert increment/observe/safe_push called.
- Integration: `docker compose up -d parsing pushgateway monitoring`; query Pushgateway/Prometheus; verify in Grafana.

## PromQL Examples
- Throughput: `rate(copilot_parsing_messages_processed_total[5m])`
- P95 latency: `histogram_quantile(0.95, rate(copilot_parsing_processing_duration_seconds_bucket[5m]))`
- Error rate: `(rate(copilot_parsing_failures_total[5m]) / rate(copilot_parsing_messages_processed_total[5m])) * 100`

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_BACKEND` | `pushgateway` | Backend (pushgateway, prometheus, noop) |
| `PUSHGATEWAY_URL` | `http://pushgateway:9091` | Pushgateway URL |
| `ENV` | `dev` | Environment label |

## Reference & Links
- Observability RFC: [docs/OBSERVABILITY_RFC.md](../OBSERVABILITY_RFC.md)
- Monitoring guide: [docs/observability/service-monitoring.md](service-monitoring.md)
- copilot_metrics adapter: [adapters/copilot_metrics/README.md](../../adapters/copilot_metrics/README.md)
- Prometheus best practices: https://prometheus.io/docs/practices/
