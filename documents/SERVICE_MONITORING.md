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
- Qdrant Dashboard: http://localhost:6333/dashboard (vectorstore web UI)
- Service container logs: via `docker compose logs -f <service>`

## 3) Metrics (Prometheus)

### Metrics Collection Strategy
This system uses a **push model** for service metrics:
- Services use `PrometheusPushGatewayMetricsCollector` to push metrics to the Pushgateway at `pushgateway:9091`
- Prometheus scrapes metrics from Pushgateway, NOT from service endpoints
- Services do NOT expose `/metrics` endpoints (only `/health` and `/stats` endpoints)
- Infrastructure exporters (MongoDB, RabbitMQ, Qdrant, cAdvisor) use the traditional pull model with `/metrics` endpoints

### Quick Checks
- Open Prometheus UI → **Status > Targets** to verify all scrape targets are `UP`
- Check Pushgateway UI at http://localhost:9091 to see pushed metrics from services
- Run ad-hoc queries (Examples):
  - `up{job="pushgateway"}` — verify Pushgateway is being scraped
  - `copilot_messages_parsed_total` — service metrics pushed to Pushgateway
  - `up{job="mongodb"}` — infrastructure exporter health
- Container resource queries (via cAdvisor):
  - `sum by (container_label_com_docker_compose_service) (rate(container_cpu_usage_seconds_total{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}[5m])) * 100` — CPU usage percentage
  - `sum by (container_label_com_docker_compose_service) (container_memory_usage_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}) / 1024 / 1024` — Memory usage in MB
  - `(sum by (container_label_com_docker_compose_service) (container_memory_usage_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}) / clamp_min(sum by (container_label_com_docker_compose_service) (container_spec_memory_limit_bytes{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}), 1)) * 100` — Memory usage as % of limit
  - `changes(container_start_time_seconds{container_label_com_docker_compose_project=~"copilot-for-consensus.*"}[1h])` — Container restarts
  - `sum by (container_label_com_docker_compose_service) (rate(container_network_receive_bytes_total{container_label_com_docker_compose_project=~"copilot-for-consensus.*", interface!~"lo"}[5m]))` — Network receive rate (excludes loopback)

### Service Health Endpoints
While services don't expose `/metrics`, they do provide:
- `/health` — Health check with basic statistics
- `/stats` — Detailed service statistics (where applicable)

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
- **Document Processing Status**: Document processing state tracking and anomaly detection (opt-in with `--profile monitoring-extra`)
  - Document counts by status (pending, processing, completed, failed)
  - Status transition trends over time
  - Processing duration metrics
  - Document age tracking to detect stuck flows
  - Embedding completion rates
  - Attempt count distributions
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

**Note**: cAdvisor is enabled by default and starts automatically with the monitoring stack.

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
- **Availability**: Starts automatically with the monitoring stack
- **Query Patterns**: Uses Docker Compose labels (`container_label_com_docker_compose_project` and `container_label_com_docker_compose_service`) for robust filtering across environments

### Troubleshooting
- **No data in dashboard**: 
  1. Verify cAdvisor is running: `docker compose ps cadvisor`
  2. If not running, start it: `docker compose up -d cadvisor`
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
- **Grafana Dashboard**: http://localhost:3000 → **Qdrant Vectorstore Status** (UID: `copilot-vectorstore-status`)
- **Qdrant Web UI**: http://localhost:6333/dashboard (native Qdrant interface)
- **Direct API**: http://localhost:6333 (REST API for collections, points, metrics)

### Qdrant Exporter
The Qdrant exporter starts automatically with the monitoring stack and provides metrics to Prometheus.

**Note**: The exporter requires the vectorstore service to be running and healthy.

### Key Metrics
- **Vector Counts**: Total vectors stored per collection (primarily `embeddings` collection)
- **Growth Rate**: Vectors added per second to track embedding ingestion
- **Storage Size**: Disk space consumed by vector collections
- **Indexed Vectors**: Number of vectors with completed indexing
- **Segments**: Internal storage segments per collection (indicates compaction status)
- **Memory Usage**: Qdrant process memory consumption (thresholds at ~800MB and 1GB are examples; tune to your deployment)
- **Scrape Health**: Exporter connectivity and data freshness

### Monitoring Queries (Prometheus)
- Vector count: `qdrant_collection_vectors_count{collection="embeddings"}`
- Growth rate: `deriv(qdrant_collection_vectors_count{collection="embeddings"}[5m])`
- Storage size: `qdrant_collection_size_bytes{collection="embeddings"}`
- Memory usage: `qdrant_memory_usage_bytes`
- Scrape errors: `rate(qdrant_scrape_errors_total[5m])`

**Dashboard Tip**: Use the `Collection` dropdown to switch between collections (default: `embeddings`).

### Troubleshooting
- **No vectors appearing**: Check embedding service logs; verify Qdrant connectivity
- **High memory usage**: Consider collection optimization or increasing resources (adjust dashboard thresholds to match your limits)
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

## 9.4) Document Processing Status Monitoring

The document processing status exporter provides deep visibility into document states across the pipeline. This helps detect stuck flows, supports debugging, and provides visibility into system health and throughput.

### Enabling the Exporter

The document processing status exporter is optional and uses the `monitoring-extra` compose profile:

```bash
# Start document processing monitoring (requires MongoDB to be running)
docker compose --profile monitoring-extra up -d document-processing-exporter

# Or start all monitoring services including document processing
docker compose --profile monitoring-extra up -d
```

**Note**: The exporter is not required for core functionality and won't impact CI builds.

### Key Metrics

The exporter exposes the following metrics for monitoring document processing:

- **`copilot_document_status_count{collection, status}`**: Count of documents by collection and status
  - Collections: `archives`, `messages`, `chunks`, `threads`
  - Status values: `pending`, `processing`, `processed`, `failed`
  
- **`copilot_document_processing_duration_seconds{collection}`**: Average processing duration (time between creation and completion)
  - Useful for identifying performance degradation
  - Default threshold: Warning at 300s (5 min), Critical at 600s (10 min)

- **`copilot_document_age_seconds{collection, status}`**: Average time since last update
  - Critical for detecting stuck documents
  - Default threshold: Warning at 1800s (30 min), Critical at 3600s (1 hour)

- **`copilot_document_attempt_count{collection}`**: Average retry attempt count
  - Indicates transient failures or resource contention
  - Default threshold: Warning at 2.5 average attempts

- **`copilot_chunks_embedding_status_count{embedding_generated}`**: Count of chunks by embedding status
  - Values: `True` (embedded), `False` (not embedded)
  - Target completion rate: >80%

### Dashboard Panels

The **Document Processing Status** dashboard (UID: `copilot-document-processing-status`) provides:

1. **Archive Processing Status**: Bar gauge showing document counts by status
2. **Archive Status Over Time**: Stacked area chart of status transitions
3. **Avg Archive Processing Duration**: Gauge with yellow (>5 min) and red (>10 min) thresholds
4. **Avg Pending Archive Age**: Gauge showing how long documents wait for processing
5. **Avg Archive Attempt Count**: Retry distribution indicator
6. **Chunk Embedding Completion Rate**: Percentage of chunks with embeddings
7. **Chunk Embedding Status Over Time**: Trend of embedding generation progress
8. **Document Age by Status**: Multi-line chart to detect stuck documents
9. **Archive Status Summary**: Table view with status, count, and age
10. **Archive Processing & Failure Rates**: Rate of successful vs. failed processing

### Prometheus Queries

Use these queries for ad-hoc investigation:

```promql
# Current status distribution for archives
copilot_document_status_count{collection="archives"}

# Failure rate (percentage)
(copilot_document_status_count{collection="archives",status="failed"} 
 / (copilot_document_status_count{collection="archives",status="failed"} 
    + copilot_document_status_count{collection="archives",status="processed"})) * 100

# Documents pending longer than 30 minutes
copilot_document_age_seconds{collection="archives",status="pending"} > 1800

# Embedding completion rate
copilot_chunks_embedding_status_count{embedding_generated="True"} 
/ (copilot_chunks_embedding_status_count{embedding_generated="True"} 
   + copilot_chunks_embedding_status_count{embedding_generated="False"})

# Processing rate (documents/second over 5 minutes)
rate(copilot_document_status_count{collection="archives",status="processed"}[5m])

# Failure rate (failures/second over 5 minutes)
rate(copilot_document_status_count{collection="archives",status="failed"}[5m])
```

### Alert Rules

The system includes automated alerts for document processing anomalies (see `infra/prometheus/alerts/document_processing.yml`):

- **HighDocumentFailureRate**: >10% failure rate for 15 minutes
- **DocumentsStuckPending**: Pending documents older than 1 hour
- **LongDocumentProcessingDuration**: Processing takes >10 minutes
- **LowEmbeddingCompletionRate**: <80% of chunks have embeddings
- **HighDocumentAttemptCount**: Average >2.5 retry attempts
- **FailedDocumentsAccumulating**: Rapid increase in failed documents (>0.5/sec)
- **DocumentsStuckProcessing**: Documents in processing state for >2 hours

### Operational Triage Guide

#### Scenario 1: High failure rate alert

**Symptoms**: `HighDocumentFailureRate` alert firing, dashboard shows increasing failed count

**Diagnosis**:
1. Check the **Archive Status Over Time** panel - is the failure rate sudden or gradual?
2. Review failed document count in **Archive Processing Status**
3. Check parsing service logs: `docker compose logs parsing | grep -i error`
4. Verify MongoDB connectivity: `docker compose ps documentdb`

**Actions**:
1. Query failed archives in MongoDB:
   ```javascript
   db.archives.find({status: "failed"}).limit(10)
   ```
2. Check error-reporting service for detailed error messages
3. Review recent deployments or configuration changes
4. If transient (network, resource), consider reprocessing failed archives
5. If systematic, fix root cause before reprocessing

#### Scenario 2: Documents stuck in pending

**Symptoms**: `DocumentsStuckPending` alert, **Avg Pending Archive Age** gauge is red

**Diagnosis**:
1. Check RabbitMQ ingestion queue depth: http://localhost:15672
2. Verify parsing service is running: `docker compose ps parsing`
3. Check for consumer connection issues in RabbitMQ UI
4. Review parsing service logs for exceptions

**Actions**:
1. Restart parsing service if not consuming: `docker compose restart parsing`
2. Check for message backlog in RabbitMQ and scale consumers if needed
3. Verify MongoDB is accepting writes
4. Monitor **Archive Status Over Time** to confirm pending count decreases

#### Scenario 3: Low embedding completion rate

**Symptoms**: `LowEmbeddingCompletionRate` alert, **Chunk Embedding Completion Rate** gauge is yellow/red

**Diagnosis**:
1. Check **Chunk Embedding Status Over Time** - is the gap widening?
2. Verify embedding service health: `docker compose ps embedding`
3. Check Qdrant vectorstore: `curl http://localhost:6333/collections`
4. Review Ollama service status: `docker compose ps ollama`

**Actions**:
1. Check embedding service logs: `docker compose logs embedding`
2. Verify Qdrant is accepting writes: Grafana > Qdrant Vectorstore Status
3. Check Ollama model availability: `docker compose logs ollama | grep -i model`
4. Monitor embedding queue in RabbitMQ for backlog
5. Consider scaling embedding service if sustained high load

#### Scenario 4: Long processing duration

**Symptoms**: `LongDocumentProcessingDuration` alert, **Avg Archive Processing Duration** gauge is red

**Diagnosis**:
1. Check if all archives are slow or just a subset
2. Query MongoDB for largest archives:
   ```javascript
   db.archives.find().sort({file_size_bytes: -1}).limit(10)
   ```
3. Review **Container Resource Usage** dashboard for bottlenecks
4. Check MongoDB performance: **MongoDB Document Store Status** dashboard

**Actions**:
1. If specific archives are large/complex, this may be expected
2. If all processing is slow, check resource constraints (CPU, memory, disk I/O)
3. Review MongoDB query performance and indexes
4. Consider optimizing parsing logic for complex documents
5. Scale parsing service if CPU-bound: `docker compose up -d --scale parsing=2`

#### Scenario 5: High attempt count

**Symptoms**: `HighDocumentAttemptCount` alert, **Avg Archive Attempt Count** gauge is yellow/red

**Diagnosis**:
1. Check for patterns in retry errors (transient vs. persistent)
2. Review error-reporting service for retry context
3. Monitor RabbitMQ for message redelivery patterns
4. Check service restart frequency in **Container Resource Usage**

**Actions**:
1. If transient (network timeouts), monitor for resolution
2. If persistent errors, investigate root cause before further retries
3. Check dependency health (MongoDB, RabbitMQ connectivity)
4. Review service resource limits and adjust if OOM kills are occurring
5. Consider exponential backoff or circuit breaker patterns if not implemented

### MongoDB Direct Inspection

For detailed document investigation, connect to MongoDB and query directly:

```bash
# Connect to MongoDB
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin

# Switch to copilot database
use copilot

# Count documents by status
db.archives.aggregate([
  {$group: {_id: "$status", count: {$sum: 1}}}
])

# Find oldest pending archives
db.archives.find({status: "pending"})
  .sort({created_at: 1})
  .limit(10)

# Find failed archives with errors
db.archives.find({status: "failed"})
  .sort({updated_at: -1})
  .limit(10)

# Find documents with high attempt counts (if field exists)
db.archives.find({attemptCount: {$gt: 2}})
  .sort({attemptCount: -1})

# Find chunks without embeddings
db.chunks.find({embedding_generated: false})
  .limit(10)

# Count chunks by embedding status
db.chunks.aggregate([
  {$group: {_id: "$embedding_generated", count: {$sum: 1}}}
])
```

### Troubleshooting

- **No data in dashboard**:
  1. Verify exporter is enabled and running: `docker compose --profile monitoring-extra ps document-processing-exporter`
  2. If not running, start it: `docker compose --profile monitoring-extra up -d document-processing-exporter`
  3. Check exporter logs: `docker compose --profile monitoring-extra logs document-processing-exporter`

- **Missing metrics**: 
  1. Check Prometheus targets (http://localhost:9090/targets) - `document-processing` should be UP
  2. Verify MongoDB connectivity from exporter
  3. Ensure collections have documents with expected fields

- **Incorrect age calculations**:
  1. Verify documents have `created_at` and `updated_at` timestamps
  2. Check for timezone issues (all timestamps should be UTC)
  3. Review exporter logs for aggregation errors

- **Alert not firing**:
  1. Verify alert rules loaded: http://localhost:9090/alerts
  2. Check Prometheus rule evaluation: http://localhost:9090/rules
  3. Review alert conditions match actual metric values
  4. Ensure alert manager is configured if using external alerting



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
