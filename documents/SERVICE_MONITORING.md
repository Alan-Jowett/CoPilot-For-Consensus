# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Service Monitoring & Troubleshooting Guide

This guide explains how to monitor and troubleshoot the services in this repository. It covers metrics, logs, message bus visibility, and common diagnostics, including a section specific to the Docker Compose setup shipped with the repo.

## 1) Quick Start (Docker Compose)
- Build & start: `docker compose up -d`
- Status: `docker compose ps`
- Logs (all): `docker compose logs -f`
- Logs (one service): `docker compose logs -f <service>`
- Stop: `docker compose down`

## 2) Observability Endpoints & Ports (default compose values)
- Grafana: http://localhost:3000 (dashboards + Loki Explore; default creds: `admin` / `admin`)
- Prometheus: http://localhost:9090 (raw metrics, ad-hoc queries)
- Loki HTTP API: http://localhost:3100 (log store)
- Promtail (shipper): publishes container logs into Loki
- RabbitMQ Management UI: http://localhost:15672 (default creds: `guest` / `guest` unless overridden)
- cAdvisor: http://localhost:8082 (container resource metrics)
- Service container logs: via `docker compose logs -f <service>`

## 3) Metrics (Prometheus)
- Scrape targets: services expose metrics endpoints (typically `/metrics`) discovered via the compose network.
- Quick checks:
  - Open Prometheus UI → **Status > Targets** to verify all endpoints are `UP`.
  - Run ad-hoc queries (Examples):
    - `up{job="<service>"}` — liveness of scrape targets
    - `rate(http_requests_total{service="<service>"}[5m])` — request rate
    - `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="<service>"}[5m]))` — P95 latency
- Container resource queries (via cAdvisor):
  - `rate(container_cpu_usage_seconds_total{name=~"copilot-.*"}[5m]) * 100` — CPU usage percentage
  - `container_memory_usage_bytes{name=~"copilot-.*"} / 1024 / 1024` — Memory usage in MB
  - `(container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100` — Memory usage as % of limit
  - `changes(container_start_time_seconds{name=~"copilot-.*"}[1h])` — Container restarts
  - `rate(container_network_receive_bytes_total{name=~"copilot-.*"}[5m])` — Network receive rate

## 4) Dashboards & Logs (Grafana + Loki)
- Access Grafana at http://localhost:3000 (default creds: `admin` / `admin`)
- **Available Dashboards:**
  - **System Health**: Overall service health and uptime
  - **Service Metrics**: Application-level metrics (throughput, latency)
  - **Queue Status**: RabbitMQ queue depths and message flow
  - **Failed Queues**: Dead letter queue monitoring and alerts
  - **Container Resource Usage**: CPU, memory, network, and disk I/O per container (see section 4.1)
- Logs via Grafana Explore (Loki):
  - Data source: Loki
  - Basic query: `{container="<service>"}`
  - Filter by severity (if structured): `{container="<service>", level="error"}`
  - Time-align with metrics by selecting the same time window.

## 4.1) Container Resource Monitoring
The **Container Resource Usage** dashboard provides comprehensive visibility into resource consumption:

### Panels and Purpose
1. **CPU Usage by Service**: Time series showing CPU percentage per container
   - Threshold alerts: Yellow at 50%, Red at 80%
   - Use to identify CPU-intensive services or bottlenecks

2. **Memory Usage by Service**: Time series showing memory consumption in MB
   - Track memory growth patterns over time
   - Correlate with application performance issues

3. **Memory Usage (% of Limit)**: Gauge showing memory as percentage of container limits
   - **Warning at 80%**, **Critical at 90%**
   - Proactive monitoring to prevent OOM kills

4. **Container Restart Count**: Table showing restarts in the last hour
   - Color-coded: Green (0), Yellow (1+), Red (3+)
   - Indicates service instability or crash loops

5. **Network I/O by Service**: Time series of receive/transmit rates
   - Identify network-intensive services
   - Detect unusual traffic patterns

6. **Top Resource Consumers**: Sortable table with all metrics
   - Quick identification of resource hogs
   - Columns: Service, CPU %, Memory MB, Network RX/TX, Restarts

7. **Memory Growth Rate**: Derivative of memory usage to detect leaks
   - Steadily increasing values indicate potential memory leaks
   - Negative values indicate memory being freed properly

8. **Disk I/O by Service**: Read/write rates per container
   - Identify services with heavy disk usage
   - Correlate with storage performance issues

9. **Service Health Status**: Color-coded stat panels showing service uptime
   - Correlate resource pressure with service outages
   - Green = UP, Red = DOWN

### Using the Dashboard
- **Memory Leak Detection**: Watch the "Memory Growth Rate" panel for services with consistently positive derivatives
- **Capacity Planning**: Use historical data to identify trends and plan resource allocation
- **Incident Response**: Correlate resource spikes with errors in logs (Loki) and failed queues
- **Performance Optimization**: Identify services consuming disproportionate resources

### Metrics Source
- **Data Source**: cAdvisor (Container Advisor)
- **Endpoint**: http://localhost:8082 (mapped from container port 8080)
- **Prometheus Job**: `cadvisor`
- **Query Patterns**: Filters containers with `name=~"copilot-.*"` to show only application services

### Troubleshooting
- **No data in dashboard**: Verify cAdvisor is running (`docker compose ps cadvisor`)
- **Missing metrics**: Check Prometheus targets (http://localhost:9090/targets) - cadvisor should be UP
- **High memory %**: Investigate service logs, check for memory leaks, consider increasing container limits
- **Frequent restarts**: Check container logs (`docker compose logs <service>`) for crash reasons

## 5) RabbitMQ Management UI
- URL: http://localhost:15672
- Check queues, consumers, message rates, and dead-letter queues.
- Useful views:
  - **Queues** → select queue → **Get messages** to peek payloads.
  - **Connections/Channels** to ensure consumers are live.
  - **Overview** to watch publish/ack rates.

## 6) Log Collection (Loki / Promtail)
- Container logs are forwarded by Promtail into Loki.
- If logs are missing in Loki:
  - `docker compose logs -f promtail`
  - Verify promtail config paths match container log locations.

## 7) Health & Readiness
- If services expose `/health` or `/ready`, curl from host or from within the compose network:
  - Host: `curl http://localhost:<mapped-port>/health`
  - In-network: `docker compose exec <service> curl http://<service>:<port>/health`

## 8) Common Diagnostics (Playbook)
- Service looks down in Prometheus `up`:
  - Check container: `docker compose ps` and `docker compose logs <service>`
  - Confirm port mapping and metrics endpoint availability (`curl http://<service>:<port>/metrics` inside network).
- Spikes in errors/latency:
  - Grafana: inspect P95/P99 latency panels; correlate with logs in Loki for same time window.
  - RabbitMQ: check queue backlogs and consumer acks.
- No logs in Loki for a service:
  - Confirm container is emitting logs to stdout/stderr.
  - Check promtail config and container labels; inspect promtail logs.
- Message processing stalls:
  - RabbitMQ UI: queue depth rising, consumers low/none.
  - Service logs: look for connection/auth errors to RabbitMQ or doc store.
- Unexpected restarts:
  - `docker compose ps` for restart count; `docker compose logs <service>` for crash reason.

## 8.1) End-to-End Pipeline Status (Mail Archive)
Use these signals to see whether a mail archive was ingested and where it is in the pipeline.

- Ingestion → Parsing → Chunking → Embedding → Summarization → Reporting
  - **RabbitMQ queues** (primary signal):
    - Open RabbitMQ UI → Queues; watch queue depth and unacked counts for each stage (ingestion, parsing, chunking, embedding, summarization, reporting).
    - If a queue grows and consumers stay low/idle, the pipeline is stuck at that stage.
  - **Logs per service** (Loki/Grafana Explore):
    - Query by container: `{container="ingestion"}` then `{container="parsing"}` etc.
    - Look for per-message IDs flowing across services (ingestion log ID should appear in downstream logs).
  - **Metrics (Prometheus/Grafana):**
    - Throughput: `rate(messages_processed_total{stage="ingestion"}[5m])` and similar for other stages if emitted.
    - Errors: `rate(stage_errors_total{stage="parsing"}[5m])` for spikes.
    - Queue depth via RabbitMQ exporter if enabled (e.g., `rabbitmq_queue_messages_ready{queue="ingestion"}`).

- How to tell if an archive is ingested:
  - Ingestion logs show download and publish events for the archive key or filename.
  - RabbitMQ ingestion queue decreases after publish, and parsing queue shows corresponding enqueued messages.
  - Downstream services emit logs referencing the same message ID as it progresses.

- How to tell downstream status:
  - Parsing: look for successful parse logs and messages moving from parsing queue to chunking queue.
  - Chunking: logs indicating chunks emitted; chunking queue drains while embedding queue fills.
  - Embedding: logs for vector creation; embedding queue drains; vector store writes succeed (check logs/metrics if emitted).
  - Summarization: logs for summary generation per thread/batch; queue drains accordingly.
  - Reporting: logs for report generation or delivery; reporting queue drains; final outputs written/stored.

- If stuck:
  - Check the stage’s queue depth and consumer count in RabbitMQ UI.
  - Inspect that stage’s container logs for errors (auth, schema, upstream/downstream unavailable).
  - Validate config/credentials for dependent services (doc store, vector store, message bus).

## 8.2) Using the Orchestrator
- Purpose: coordinates cross-service workflows and may dispatch work to the pipeline.
- Observability:
  - Metrics: `up{job="orchestrator"}` plus any orchestrator-specific counters (dispatch counts, failures).
  - Logs: `{container="orchestrator"}` in Loki for task submissions and error handling.
  - Queues: if orchestrator publishes jobs, watch the relevant RabbitMQ queues for growth/drain.
- Operations:
  - Trigger or requeue work via orchestrator endpoints/CLI (if exposed); confirm acceptance in logs.
  - If orchestration fails, check credentials and downstream availability (RabbitMQ, doc store, vector store).

## 8.3) Managing Failed Queues
Failed message queues (`*.failed`) accumulate messages when services encounter unrecoverable errors after exhausting retries. Proper handling is critical to prevent data loss and pipeline degradation.

### Quick Checks
- **RabbitMQ UI**: http://localhost:15672 → **Queues** → filter by `.failed`
- **Grafana Dashboard**: http://localhost:3000 → **Failed Queues Overview**
- **CLI Tool**: `python scripts/manage_failed_queues.py list`

### Common Operations
```bash
# List all failed queues and message counts
python scripts/manage_failed_queues.py list

# Inspect failed messages
python scripts/manage_failed_queues.py inspect parsing.failed --limit 10

# Export for backup/analysis
python scripts/manage_failed_queues.py export parsing.failed --output backup.json

# Requeue after fixing root cause (test with --dry-run first)
python scripts/manage_failed_queues.py requeue parsing.failed --dry-run
python scripts/manage_failed_queues.py requeue parsing.failed

# Purge old/obsolete messages (always export first!)
python scripts/manage_failed_queues.py export parsing.failed --output archive.json
python scripts/manage_failed_queues.py purge parsing.failed --limit 100 --confirm
```

### Alerting Thresholds
- **Warning**: >50 messages for 15 minutes → Investigate root cause
- **Critical**: >200 messages for 5 minutes → Escalate to on-call
- **Emergency**: >1000 messages → Declare incident, all-hands

### When to Requeue vs. Purge
**Requeue** when:
- Transient errors resolved (network, resource constraints)
- Service bug fixed and deployed
- Configuration corrected

**Purge** when:
- Messages beyond retention policy (>30 days)
- Source data corrupted/obsolete
- Permanent errors unfixable

**⚠️ Always export messages before purging!**

For complete operational runbook, see **[FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md)**

## 9) Scaling & Load Debugging
- Horizontal scale in compose: `docker compose up -d --scale <service>=N` (if the service is stateless and supports scaling).
- Watch effects:
  - Prometheus: `rate(http_requests_total...)` per instance.
  - RabbitMQ: queue depth and consumer count.
  - Grafana/Loki: error rates per instance.

## 10) Cleanup & Reset
- Stop stack: `docker compose down`
- Remove volumes (destructive): `docker compose down -v`
- Clear Loki data (if stored in a volume) before re-running tests to start fresh.

## 11) Tips for Faster Troubleshooting
- Always correlate metrics (Prometheus) with logs (Loki) and queue state (RabbitMQ) on the same time window.
- Keep one Grafana tab on dashboards and one on Explore for logs.
- When adding new services, ensure they expose `/metrics` and log to stdout for Promtail to ingest.
- For persistent issues, capture: timestamps, Grafana screenshots, exact PromQL/Loki queries, and RabbitMQ queue stats.
