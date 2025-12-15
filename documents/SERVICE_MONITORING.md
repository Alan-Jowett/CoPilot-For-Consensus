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
- cAdvisor: http://localhost:8082 (container resource metrics, **opt-in**: `docker compose --profile monitoring-extra up -d cadvisor`)
- Qdrant Dashboard: http://localhost:6333/dashboard (vectorstore web UI)
- Service container logs: via `docker compose logs -f <service>`

## 3) Metrics (Prometheus)
- Scrape targets: services expose metrics endpoints (typically `/metrics`) discovered via the compose network.
- Quick checks:
  - Open Prometheus UI → **Status > Targets** to verify all endpoints are `UP`.
  - Run ad-hoc queries (Examples):
    - `up{job="<service>"}` — liveness of scrape targets
    - `rate(http_requests_total{service="<service>"}[5m])` — request rate
    - `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="<service>"}[5m]))` — P95 latency
- Container resource queries (via cAdvisor, requires `--profile monitoring-extra`):
  - `sum by (container_label_com_docker_compose_service) (rate(container_cpu_usage_seconds_total{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}[5m])) * 100` — CPU usage percentage
  - `sum by (container_label_com_docker_compose_service) (container_memory_usage_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}) / 1024 / 1024` — Memory usage in MB
  - `(sum by (container_label_com_docker_compose_service) (container_memory_usage_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}) / clamp_min(sum by (container_label_com_docker_compose_service) (container_spec_memory_limit_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}), 1)) * 100` — Memory usage as % of limit
  - `changes(container_start_time_seconds{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}[1h])` — Container restarts
  - `sum by (container_label_com_docker_compose_service) (rate(container_network_receive_bytes_total{container_label_com_docker_compose_project=~"copilot-for-consensus.*", interface!~"lo"}[5m]))` — Network receive rate (excludes loopback)

## 4) Dashboards & Logs (Grafana + Loki)
- Access Grafana at http://localhost:3000 (default creds: `admin` / `admin`)
- Available dashboards:
  - **Copilot System Health** - Overall service health and uptime
  - **Service Metrics** - Service-level performance metrics
  - **Queue Status** - RabbitMQ queue depths and throughput
  - **Failed Queues** - Failed message monitoring and alerting
  - **MongoDB Document Store Status** - Document counts, storage, and MongoDB performance
  - **Qdrant Vectorstore Status** - Vector counts, storage, and Qdrant performance
- Pre-configured Dashboards:
  - **System Health**: Service uptime and basic health metrics (Prometheus)
  - **Service Metrics**: Detailed service performance metrics (Prometheus)
  - **Queue Status**: RabbitMQ queue depths and message flow (Prometheus)
  - **Failed Queues**: Failed message queue monitoring (Prometheus)
  - **Logs Overview**: Error and warning tracking across all services (Loki)
    - Error/warning counts per service (last 1h)
    - Live error and warning log streams
    - Error rate trends over time
    - Top services by error count
  - **Container Resource Usage**: CPU, memory, network, and disk I/O per container (see section 4.1)
=======
- Dashboards: use or create service dashboards with Prometheus as the data source.
  - **System Health**: Overview of all services and their health status
  - **Service Metrics**: Processing throughput and latency for core services
  - **Queue Status**: RabbitMQ queue depths and consumer metrics
  - **Failed Queues**: Monitoring for messages in failed queues
  - **Vectorstore Status**: Qdrant vector counts, storage, memory, and query performance
>>>>>>> 2c0afb6 (Add Qdrant vectorstore monitoring with exporter and Grafana dashboard)
- Logs via Grafana Explore (Loki):
  - Data source: Loki
  - Basic query: `{container="<service>"}`
  - Filter by severity (if structured): `{container="<service>", level="error"}`
  - Time-align with metrics by selecting the same time window.
- Dashboards: use or create service dashboards with Prometheus as the data source.

### Available Dashboards
- **Copilot System Health**: Overall service health and uptime
- **Service Metrics**: Service-level performance metrics
- **Queue Status**: RabbitMQ queue depths and message flow
- **Failed Queues Overview**: Failed message monitoring and alerting
- **Logs Overview**: Error and warning tracking across all services (Loki)
  - Error/warning counts per service (last 1h)
  - Live error and warning log streams
  - Error rate trends over time
  - Top services by error count
- **MongoDB Document Store Status**: Document counts, growth rate, totals, storage by collection, connections, op counters, query latency, recent changes
- **Pipeline Flow Visualization**: End-to-end pipeline monitoring showing message flow from ingestion through reporting
  - Identify bottlenecks quickly
  - Monitor message rates per stage using counter-based rates
  - Track success and failure counts by stage
  - View processing latency per stage (P95)
  - Default time range: Last 15 minutes

### Logs via Grafana Explore (Loki)
- Data source: Loki
- Basic query: `{container="<service>"}`
- Filter by severity (if structured): `{container="<service>", level="error"}`
- Time-align with metrics by selecting the same time window.

## 4.1) Container Resource Monitoring
The **Container Resource Usage** dashboard provides comprehensive visibility into resource consumption.

**Prerequisites**: cAdvisor must be enabled with the `monitoring-extra` profile:
```bash
docker compose --profile monitoring-extra up -d cadvisor
```

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
- **Opt-in**: Disabled by default; enable with `docker compose --profile monitoring-extra up -d cadvisor`
- **Query Patterns**: Uses Docker Compose labels (`container_label_com_docker_compose_project` and `container_label_com_docker_compose_service`) for robust filtering across environments

### Troubleshooting
- **No data in dashboard**: 
  1. Verify cAdvisor is enabled and running: `docker compose --profile monitoring-extra ps cadvisor`
  2. If not running, start it: `docker compose --profile monitoring-extra up -d cadvisor`
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

## 5.1) Qdrant Vectorstore Monitoring
- **Grafana Dashboard**: http://localhost:3000 → **Qdrant Vectorstore Status**
- **Qdrant Web UI**: http://localhost:6333/dashboard (native Qdrant interface)
- **Direct API**: http://localhost:6333 (REST API for collections, points, metrics)

### Key Metrics
- **Vector Counts**: Total vectors stored per collection (primarily `embeddings` collection)
- **Growth Rate**: Vectors added per second to track embedding ingestion
- **Storage Size**: Disk space consumed by vector collections
- **Indexed Vectors**: Number of vectors with completed indexing
- **Segments**: Internal storage segments per collection (indicates compaction status)
- **Memory Usage**: Qdrant process memory consumption
- **Scrape Health**: Exporter connectivity and data freshness

### Monitoring Queries (Prometheus)
- Vector count: `qdrant_collection_vectors_count{collection="embeddings"}`
- Growth rate: `deriv(qdrant_collection_vectors_count{collection="embeddings"}[5m])`
- Storage size: `qdrant_collection_size_bytes{collection="embeddings"}`
- Memory usage: `qdrant_memory_usage_bytes`
- Scrape errors: `rate(qdrant_scrape_errors_total[5m])`

### Troubleshooting
- **No vectors appearing**: Check embedding service logs; verify Qdrant connectivity
- **High memory usage**: Consider collection optimization or increasing resources
- **Many segments**: May indicate need for manual compaction
- **Scrape failures**: Check qdrant-exporter logs (`docker compose logs qdrant-exporter`)
- **Slow queries**: Review indexed vectors count; indexing may be lagging

### Direct Collection Inspection
```bash
# List all collections
curl http://localhost:6333/collections

# Get embeddings collection info
curl http://localhost:6333/collections/embeddings

# Count points/vectors
curl -X POST http://localhost:6333/collections/embeddings/points/count \
  -H 'Content-Type: application/json' \
  -d '{"exact": true}'
```

## 6) Log Collection (Loki / Promtail)
- Container logs are forwarded by Promtail into Loki.
- If logs are missing in Loki:
  - `docker compose logs -f promtail`
  - Verify promtail config paths match container log locations.

## 8) Health & Readiness
- If services expose `/health` or `/ready`, curl from host or from within the compose network:
  - Host: `curl http://localhost:<mapped-port>/health`
  - In-network: `docker compose exec <service> curl http://<service>:<port>/health`

## 9) Common Diagnostics (Playbook)
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

## 9.1) End-to-End Pipeline Status (Mail Archive)
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
    - **Verify vectors stored**: Check `qdrant_collection_vectors_count{collection="embeddings"}` in Grafana or Prometheus
    - **Growth rate**: Monitor `deriv(qdrant_collection_vectors_count{collection="embeddings"}[5m])` to confirm active ingestion
  - Summarization: logs for summary generation per thread/batch; queue drains accordingly.
  - Reporting: logs for report generation or delivery; reporting queue drains; final outputs written/stored.

- If stuck:
  - Check the stage’s queue depth and consumer count in RabbitMQ UI.
  - Inspect that stage’s container logs for errors (auth, schema, upstream/downstream unavailable).
  - Validate config/credentials for dependent services (doc store, vector store, message bus).
  - **For embedding issues**: Check Qdrant Vectorstore Status dashboard; verify qdrant-exporter is running and healthy.

### Using the Pipeline Flow Dashboard

The **Pipeline Flow Visualization** dashboard provides a unified view for troubleshooting pipeline issues. Here are common scenarios:

**Scenario 1: Chunking queue is growing (bottleneck detected)**
1. Open the Pipeline Flow dashboard at http://localhost:3000
2. Look at the visual flow diagram (top row) - the "Chunking" box will be yellow (50-200 messages) or red (>200 messages)
3. Check the "Message Rate by Stage" panel - if the "Chunking → Embedding" line is flat or declining while "Parsing → Chunking" is increasing, chunking is the bottleneck
4. In the "Pipeline Bottleneck Alert" table, chunking will appear at the top with the highest queue depth
5. **Action**: Check chunking service logs: `docker compose logs -f chunking` or use Grafana Loki: `{container="chunking", level="error"}`
6. Common causes: service crashes, resource exhaustion, downstream dependency (doc store) unavailable

**Scenario 2: High failure rate in embedding stage**
1. Open the Pipeline Flow dashboard
2. Check the "Success/Failure Counts by Stage" table at the bottom
3. If `embedding.generation.failed` queue has a high message count, this indicates systematic failures
4. Look at the "Queue Depth by Stage" stacked area chart - you may see embedding queue draining but failed queue growing
5. **Action**: Inspect embedding service logs for errors, check vector store (Qdrant) connectivity and health
6. Switch to the "Failed Queues Overview" dashboard for detailed failure analysis

**Scenario 3: End-to-end throughput is low but no obvious bottleneck**
1. Check the "End-to-End Throughput" stat panel - if it's near zero or very low, the pipeline is stalled
2. Look at the "Stage Processing Latency (P95)" panel - if any stage shows abnormally high latency (>10s), that's the culprit
3. Even if queues are empty, high latency indicates slow processing
4. **Action**: 
   - For high parsing latency: check if documents are unusually large or complex
   - For high embedding latency: check Ollama service health and model loading times
   - For high summarization latency: check LLM service availability and response times

**Scenario 4: Pipeline is processing but reports aren't being generated**
1. Visual flow shows messages flowing through all stages but "Reporting" box stays red
2. Check "Message Rate by Stage" - if "Reporting Output" line is flat at zero, reports aren't completing
3. **Action**: Check reporting service logs and verify report delivery configuration (S3, filesystem, etc.)

**Scenario 5: Sudden spike in all queues (upstream overload)**
1. All boxes in visual flow turn yellow/red simultaneously
2. "Queue Depth by Stage" stacked chart shows all layers growing together
3. "Message Rate by Stage" shows all rates increasing
4. **Action**: This indicates ingestion is overwhelming the pipeline. Either:
   - Rate-limit ingestion at the source
   - Scale up consumer services: `docker compose up -d --scale parsing=2 --scale chunking=2`
   - Check if this is expected (e.g., large batch import) or anomalous

## 8.2) Using the Orchestrator
- Purpose: coordinates cross-service workflows and may dispatch work to the pipeline.
- Observability:
  - Metrics: `up{job="orchestrator"}` plus any orchestrator-specific counters (dispatch counts, failures).
  - Logs: `{container="orchestrator"}` in Loki for task submissions and error handling.
  - Queues: if orchestrator publishes jobs, watch the relevant RabbitMQ queues for growth/drain.
- Operations:
  - Trigger or requeue work via orchestrator endpoints/CLI (if exposed); confirm acceptance in logs.
  - If orchestration fails, check credentials and downstream availability (RabbitMQ, doc store, vector store).

## 9.3) Managing Failed Queues
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

## 10) Scaling & Load Debugging
- Horizontal scale in compose: `docker compose up -d --scale <service>=N` (if the service is stateless and supports scaling).
- Watch effects:
  - Prometheus: `rate(http_requests_total...)` per instance.
  - RabbitMQ: queue depth and consumer count.
  - Grafana/Loki: error rates per instance.

## 11) Cleanup & Reset
- Stop stack: `docker compose down`
- Remove volumes (destructive): `docker compose down -v`
- Clear Loki data (if stored in a volume) before re-running tests to start fresh.

## 12) Tips for Faster Troubleshooting
- Always correlate metrics (Prometheus) with logs (Loki) and queue state (RabbitMQ) on the same time window.
- Keep one Grafana tab on dashboards and one on Explore for logs.
- When adding new services, ensure they expose `/metrics` and log to stdout for Promtail to ingest.
- For persistent issues, capture: timestamps, Grafana screenshots, exact PromQL/Loki queries, and RabbitMQ queue stats.
