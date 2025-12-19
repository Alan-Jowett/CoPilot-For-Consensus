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

### Service Metrics Reference

All service metrics use the `copilot_` namespace prefix. Services push metrics to Pushgateway after processing each batch/message.

#### Parsing Service Metrics
- `copilot_parsing_messages_parsed_total` (Counter) - Total messages successfully parsed
  - Used by dashboard query: `rate(copilot_parsing_messages_parsed_total[5m])` for throughput
- `copilot_parsing_archives_processed_total` (Counter) - Total archives processed
  - Labels: `status` (`success` or `failed`)
- `copilot_parsing_threads_created_total` (Counter) - Total email threads created
- `copilot_parsing_duration_seconds` (Histogram) - Time taken to parse archives
  - Used by dashboard query: `histogram_quantile(0.95, rate(copilot_parsing_duration_seconds_bucket[5m]))` for p95 latency
- `copilot_parsing_failures_total` (Counter) - Total parsing failures
  - Labels: `error_type` (e.g., `IOError`, `ParseError`)
  - Used by dashboard query: `rate(copilot_parsing_failures_total[5m])` for error rate

#### Chunking Service Metrics
- `copilot_chunking_chunks_created_total` (Counter) - Total chunks created
  - Used by dashboard query: `rate(copilot_chunking_chunks_created_total[5m])` for throughput
- `copilot_chunking_messages_processed_total` (Counter) - Total messages chunked
  - Labels: `status` (`success`)
- `copilot_chunking_duration_seconds` (Histogram) - Time taken to chunk messages
  - Used by dashboard query: `histogram_quantile(0.95, rate(copilot_chunking_duration_seconds_bucket[5m]))` for p95 latency
- `copilot_chunking_chunk_size_tokens` (Histogram) - Distribution of chunk sizes in tokens
- `copilot_chunking_failures_total` (Counter) - Total chunking failures
  - Labels: `error_type` (e.g., `TokenizationError`)
  - Used by dashboard query: `rate(copilot_chunking_failures_total[5m])` for error rate

#### Embedding Service Metrics
- `copilot_embedding_chunks_processed_total` (Counter) - Total chunks processed for embeddings
- `copilot_embedding_generation_duration_seconds` (Histogram) - Time taken to generate embeddings
  - Used by dashboard query: `histogram_quantile(0.95, rate(copilot_embedding_generation_duration_seconds_bucket[5m]))` for p95 latency
- `copilot_embedding_failures_total` (Counter) - Total embedding generation failures
  - Labels: `error_type` (e.g., `ModelError`, `ConnectionError`)
  - Used by dashboard query: `rate(copilot_embedding_failures_total[5m])` for error rate

#### Summarization Service Metrics
- `copilot_summarization_latency_seconds` (Histogram) - Time taken to generate summaries
  - Used by dashboard query: `histogram_quantile(0.95, rate(copilot_summarization_latency_seconds_bucket[5m]))` for p95 latency
- `copilot_summarization_events_total` (Counter) - Total summarization events
  - Labels: `event_type` (`requested`), `outcome` (`success`)
- `copilot_summarization_llm_calls_total` (Counter) - Total LLM API calls
  - Labels: `backend` (e.g., `openai`, `azure`), `model` (e.g., `gpt-4`)
- `copilot_summarization_tokens_total` (Counter) - Total tokens processed
  - Labels: `type` (`prompt` or `completion`)
- `copilot_summarization_failures_total` (Counter) - Total summarization failures
  - Labels: `error_type` (e.g., `LLMTimeout`, `APIError`)
  - Used by dashboard query: `rate(copilot_summarization_failures_total[5m])` for error rate

#### Orchestrator Service Metrics
- `copilot_orchestrator_summary_triggered_total` (Counter) - Total summaries triggered
  - Labels: `reason` (`chunks_changed`)
- `copilot_orchestrator_summary_skipped_total` (Counter) - Total summaries skipped
  - Labels: `reason` (`summary_already_exists`)
- `copilot_orchestration_events_total` (Counter) - Total orchestration events
  - Labels: `event_type` (`summarization_requested`, `orchestration_failed`), `outcome` (`success`, `failure`)
- `copilot_orchestration_failures_total` (Counter) - Total orchestration failures
  - Labels: `error_type` (e.g., `DocumentStoreError`)

#### Infrastructure Metrics (from Exporters)
- `qdrant_collection_vectors_count` (Gauge) - Number of vectors in Qdrant collection
  - Labels: `collection` (e.g., `embeddings`)
  - Used by dashboard for Vector Store Size panel
- `rabbitmq_queue_messages_ready` (Gauge) - Messages waiting in RabbitMQ queue
  - Labels: `queue` (e.g., `parsing`, `chunking`, `embedding`, `summarization`)
  - Used by dashboard for Queue Depths panel
- `mongodb_collstats_count`, `mongodb_collstats_storageSize` - MongoDB collection stats
- `container_*` - cAdvisor container resource metrics

### Troubleshooting Service Metrics Dashboard

**Problem: "No data" in Service Metrics Dashboard panels**

1. **Verify Pushgateway is running and being scraped**:
   - Check Prometheus targets: http://localhost:9090/targets
   - The `pushgateway` job should show as `UP`
   - If down, start it: `docker compose up -d pushgateway`

2. **Check if services are pushing metrics**:
   - Open Pushgateway UI: http://localhost:9091
   - Look for metrics with `copilot_` prefix
   - If no metrics visible, services may not be pushing

3. **Verify services are processing data**:
   - Services only push metrics after processing messages/batches
   - Check service logs: `docker compose logs -f parsing` (or chunking, embedding, etc.)
   - Look for log entries like "Successfully parsed archive..." or "Chunking completed..."
   - If services aren't processing, they won't push metrics

4. **Test metric push manually**:
   - Run ad-hoc query in Prometheus: http://localhost:9090
   - Try: `copilot_parsing_messages_parsed_total`
   - If this returns data, dashboard queries may need adjustment
   - If this returns no data, services aren't pushing

5. **Check for metric push errors in service logs**:
   - Search logs for "Failed to push metrics"
   - Linux/macOS: `docker compose logs parsing | grep "push metrics"`
   - Windows PowerShell: `docker compose logs parsing | Select-String "push metrics"`
   - Fix any connection errors to Pushgateway

6. **Verify correct metric names**:
   - Dashboard queries must match actual metric names
   - Check the "Service Metrics Reference" section above for correct names
   - Use Prometheus UI to explore available metrics: http://localhost:9090/graph

**Problem: Specific panels show "No data"**

- **Parsing Throughput**: Ensure parsing service has processed at least one archive
- **Chunking Throughput**: Ensure chunking service has processed messages
- **Embedding Latency**: Embedding service needs to generate at least one embedding batch
- **Summarization Latency**: Summarization service needs to complete at least one summary
- **Vector Store Size**: Requires Qdrant exporter to be running (`docker compose ps qdrant-exporter`)
- **Queue Depths**: RabbitMQ metrics are collected via the built-in Prometheus plugin (enabled by default)

**Quick Fix Checklist**:

Linux/macOS (bash):
```bash
# 1. Restart all monitoring services
docker compose restart pushgateway monitoring grafana

# 2. Restart service that's missing metrics
docker compose restart parsing  # or chunking, embedding, summarization

# 3. Trigger some processing to generate metrics
# (Ingest test data - see "ingest test data" intent in .github/copilot-instructions.md)

# 4. Wait 15-30 seconds for metrics to propagate

# 5. Refresh Grafana dashboard
```

Windows (PowerShell):
```powershell
# 1. Restart all monitoring services
docker compose restart pushgateway monitoring grafana

# 2. Restart service that's missing metrics
docker compose restart parsing  # or chunking, embedding, summarization

# 3. Trigger some processing to generate metrics
# (Ingest test data - see "ingest test data" intent in .github/copilot-instructions.md)

# 4. Wait 15-30 seconds for metrics to propagate

# 5. Refresh Grafana dashboard
```


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
- **Service Metrics**: Service-level performance metrics (see section 3.1)
  - Parsing Throughput: Messages parsed per second
  - Chunking Throughput: Chunks created per second
  - Embedding Latency: P50/P95 latency for embedding generation
  - Summarization Latency: P50/P95 latency for summary generation
  - Vector Store Size: Total vectors in Qdrant embeddings collection
  - Queue Depths: Message counts in RabbitMQ queues per service
  - Error Rates: Failed operations per service per second
  - Processing Latency: P95 latency for parsing and chunking
- **Queue Status**: RabbitMQ queue depths and message flow
- **Failed Queues Overview**: Failed message monitoring and alerting
- **Retry Policy Monitoring**: Document retry metrics and stuck document tracking (see section 4.2)
- **Logs Overview**: Error and warning tracking across all services (Loki)
  - Error/warning counts per service (last 1h)
  - Live error and warning log streams
  - Error rate trends over time
  - Top services by error count
- **MongoDB Document Store Status**: Document counts, growth rate, totals, storage by collection, connections, op counters, query latency, recent changes
- **Document Processing Status**: Document processing state tracking and anomaly detection
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
- **Container Resource Usage**: CPU, memory, network, and disk I/O per container (see section 4.1)
- **Qdrant Vectorstore Status**: Vector counts, storage, memory, and query performance (see section 5.1)

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

## 4.2) Retry Policy Monitoring

The **Retry Policy Monitoring** dashboard (UID: `retry-policy`) tracks the automated retry job that handles stuck and failed documents across the pipeline.

### Understanding the Dashboard

**Important**: This dashboard shows metrics from the `retry-job` service, which runs every 15 minutes by default.

**Expected Behavior**:
- **"No Data" state**: Normal if the retry-job hasn't run yet or there are genuinely no stuck/failed documents
- **Zero values**: Healthy state indicating the pipeline is processing without issues
- **Metrics appear**: After the first successful retry-job execution (within 15 minutes of system startup)

### Key Panels

1. **Dashboard Information** (top panel):
   - Explains expected behavior and provides quick troubleshooting commands
   - Always visible to help users understand the "no data" state

2. **Stuck Documents (Current)**: 
   - Gauge showing documents with `status=pending/processing` and `lastAttemptTime > 24 hours`
   - Zero is healthy; values >50 trigger warnings
   - Breakdown by collection (archives, messages, chunks, threads)

3. **Failed Documents (Max Retries)**:
   - Documents that exceeded max retry attempts (3 for archives/messages, 5 for chunks/threads)
   - Require manual investigation and intervention

4. **Retry Rate (docs/sec)**:
   - Rate of documents being automatically requeued
   - Indicates retry job activity

5. **Stuck Documents (Timeseries)**:
   - Historical trend of stuck documents
   - Helps identify patterns (time of day, after deployments, etc.)

6. **Total Documents Requeued**:
   - Cumulative counter of retry attempts
   - Should increase gradually if retries are occurring

7. **Documents Skipped (Backoff)**:
   - Documents skipped due to exponential backoff delay
   - High values indicate backoff is working as intended

8. **Documents Exceeding Max Retries**:
   - Cumulative count of permanent failures
   - Requires service team investigation

9. **Retry Job Duration**:
   - Time taken to complete each retry job execution
   - Helps identify performance degradation

10. **Retry Job Executions**:
    - Success/failure count of retry job runs
    - Should show steady success count

11. **Retry Job Errors**:
    - Errors encountered during retry job execution
    - By error type (connection, publish, etc.)

### Metrics Reference

All metrics are pushed to Prometheus Pushgateway by the retry-job service:

| Metric | Type | Description |
|--------|------|-------------|
| `retry_job_stuck_documents` | Gauge | Current count of stuck documents per collection |
| `retry_job_failed_documents` | Gauge | Current count of failed documents (max retries) per collection |
| `retry_job_documents_requeued_total` | Counter | Total documents requeued for retry |
| `retry_job_documents_skipped_backoff_total` | Counter | Documents skipped due to backoff delay |
| `retry_job_documents_max_retries_exceeded_total` | Counter | Documents exceeding max retry attempts |
| `retry_job_runs_total` | Counter | Retry job executions (success/failure) |
| `retry_job_errors_total` | Counter | Errors during retry job execution |
| `retry_job_duration_seconds` | Histogram | Time to complete retry job |

### Prometheus Queries

Use these queries for ad-hoc investigation:

```promql
# Current stuck documents by collection
retry_job_stuck_documents

# Retry rate over last 5 minutes
rate(retry_job_documents_requeued_total[5m])

# Failed documents requiring intervention
retry_job_failed_documents

# Retry job success rate
rate(retry_job_runs_total{status="success"}[1h])

# Job execution errors
retry_job_errors_total
```

### Troubleshooting

#### Dashboard shows "No Data"

**Diagnosis**:
1. Check if retry-job is running:
   
   Linux/macOS (bash):
   ```bash
   docker compose ps retry-job
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose ps retry-job
   ```

2. View retry-job logs:
   
   Linux/macOS (bash):
   ```bash
   docker compose logs retry-job
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose logs retry-job
   ```

3. Check Prometheus Pushgateway for metrics:
   - Open http://localhost:9091
   - Look for job `retry-job`

**Solutions**:
- If retry-job isn't running:
  
  Linux/macOS (bash):
  ```bash
  docker compose up -d retry-job
  ```
  
  Windows (PowerShell):
  ```powershell
  docker compose up -d retry-job
  ```

- If retry-job is failing: Check logs for connection errors to MongoDB or RabbitMQ

- If you need metrics immediately: Manually trigger the job:
  
  Linux/macOS (bash):
  ```bash
  docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
  ```
  
  Windows (PowerShell):
  ```powershell
  docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
  ```

#### High Stuck Document Count

**Symptoms**: `retry_job_stuck_documents` > 50 for extended period

**Diagnosis**:
1. Check which collection has stuck documents (dashboard shows breakdown)
2. Review service health for that stage:
   
   Linux/macOS (bash):
   ```bash
   docker compose logs <service> | grep ERROR
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose logs <service> | Select-String -Pattern "ERROR"
   ```

3. Check RabbitMQ queue depth: http://localhost:15672
4. Verify MongoDB connectivity:
   
   Linux/macOS (bash):
   ```bash
   docker compose ps documentdb
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose ps documentdb
   ```

**Actions**:
1. If service is down: Restart it:
   
   Linux/macOS (bash):
   ```bash
   docker compose restart <service>
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose restart <service>
   ```

2. If queue is backed up: Check consumer count in RabbitMQ UI
3. If dependency issue: Fix dependency (MongoDB, RabbitMQ, Qdrant, Ollama)
4. Monitor dashboard to confirm stuck count decreases

#### Documents Exceeding Max Retries

**Symptoms**: `retry_job_failed_documents` > 0 and increasing

**Diagnosis**:
1. Check which collection has failures (dashboard shows breakdown)
2. Investigate error patterns:
   
   Linux/macOS (bash):
   ```bash
   docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin
   use copilot
   db.archives.find({status: "failed_max_retries"}).limit(10)
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin
   # Then in mongosh:
   # use copilot
   # db.archives.find({status: "failed_max_retries"}).limit(10)
   ```

3. Review failed queue messages:
   
   Linux/macOS (bash):
   ```bash
   python scripts/manage_failed_queues.py inspect parsing.failed --limit 10
   ```
   
   Windows (PowerShell):
   ```powershell
   python scripts/manage_failed_queues.py inspect parsing.failed --limit 10
   ```

**Actions**:
1. If bug is fixed: Reset attempt count and requeue (see [RETRY_POLICY.md](./RETRY_POLICY.md#purging-permanently-failed-documents))
2. If data is corrupt: Export for analysis then purge
3. If still investigating: Leave in failed state and escalate

#### Retry Job Failing

**Symptoms**: `retry_job_runs_total{status="failure"}` increasing

**Diagnosis**:
1. Check retry-job logs for errors:
   
   Linux/macOS (bash):
   ```bash
   docker compose logs retry-job | tail -100
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose logs retry-job | Select-Object -Last 100
   ```

2. Common issues:
   - MongoDB connection timeout
   - RabbitMQ connection refused
   - Pushgateway unreachable

**Actions**:
1. Verify all dependencies are healthy:
   
   Linux/macOS (bash):
   ```bash
   docker compose ps
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose ps
   ```

2. Check network connectivity between services
3. Restart retry-job:
   
   Linux/macOS (bash):
   ```bash
   docker compose restart retry-job
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose restart retry-job
   ```

4. Run manually with verbose logging:
   
   Linux/macOS (bash):
   ```bash
   docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once --verbose
   ```
   
   Windows (PowerShell):
   ```powershell
   docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once --verbose
   ```

### Alert Integration

The dashboard is integrated with Prometheus alerts defined in `infra/prometheus/alerts/retry_policy.yml`:

- **StuckDocumentsWarning**: Triggers when >50 stuck documents for 1 hour
- **MaxRetriesExceededCritical**: Triggers when documents permanently fail at >10/hour
- **RetryJobFailed**: Triggers when retry job execution fails
- **StuckDocumentsEmergency**: Triggers when >1000 stuck documents (critical)
- **FailedDocumentsAccumulating**: Triggers when >100 failed documents accumulate

See [RETRY_POLICY.md](./RETRY_POLICY.md) for complete alert response procedures.

### Configuration

The retry-job behavior can be tuned via environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRY_JOB_INTERVAL_SECONDS` | 900 (15 min) | How often retry job runs |
| `RETRY_JOB_BASE_DELAY_SECONDS` | 300 (5 min) | Base delay for exponential backoff |
| `RETRY_JOB_MAX_DELAY_SECONDS` | 3600 (60 min) | Maximum backoff delay |
| `RETRY_JOB_STUCK_THRESHOLD_HOURS` | 24 | Hours before document is "stuck" |

To change the retry job interval (e.g., run every 5 minutes):
```bash
# In .env file or docker-compose.yml
RETRY_JOB_INTERVAL_SECONDS=300
```

Then restart: `docker compose restart retry-job`

### Related Documentation

- **[RETRY_POLICY.md](./RETRY_POLICY.md)**: Complete retry policy specification and operational procedures
- **[FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md)**: Failed queue management
- **[DOCUMENT_PROCESSING_OBSERVABILITY.md](./DOCUMENT_PROCESSING_OBSERVABILITY.md)**: Document processing status monitoring

## 5) RabbitMQ Management UI
- URL: http://localhost:15672
- Check queues, consumers, message rates, and dead-letter queues.
- Useful views:
  - **Queues** → select queue → **Get messages** to peek payloads.
  - **Connections/Channels** to ensure consumers are live.
  - **Overview** to watch publish/ack rates.

### RabbitMQ Metrics Collection

RabbitMQ metrics are automatically collected via the **built-in Prometheus plugin** (`rabbitmq_prometheus`), which is enabled by default in `infra/rabbitmq/enabled_plugins`.

**Metrics Endpoint**: The plugin exposes metrics at `http://messagebus:15692/metrics` (internal Docker network). Prometheus scrapes this endpoint every 15 seconds.

**Per-Queue Metrics Configuration**: The messagebus service is configured with `PROMETHEUS_RETURN_PER_OBJECT_METRICS=true` to expose per-queue metrics with labels (e.g., `queue`, `vhost`). This allows Grafana dashboards to display individual queue depths and message rates.

**Key RabbitMQ Metrics**:
- `rabbitmq_queue_messages_ready{queue="<queue_name>",vhost="/"}` - Messages waiting in queue (ready to be consumed) per queue
- `rabbitmq_queue_messages_unacked{queue="<queue_name>",vhost="/"}` - Messages delivered but not yet acknowledged per queue
- `rabbitmq_queue_messages{queue="<queue_name>",vhost="/"}` - Total messages in queue (ready + unacked) per queue
- `rabbitmq_channel_messages_published_total` - Total messages published to channels
- `rabbitmq_channel_messages_delivered_total` - Total messages delivered to consumers
- `rabbitmq_connections` - Number of active connections
- `rabbitmq_consumers` - Number of active consumers
- `rabbitmq_alarms_*` - Resource alarms (memory, disk space, file descriptors)

**Prometheus Queries**:
```promql
# Queue depth (ready messages) by specific queue
rabbitmq_queue_messages_ready{queue="json.parsed"}

# Queue depth for all queues
rabbitmq_queue_messages_ready

# Total messages across all queues
sum(rabbitmq_queue_messages)

# Message publish rate
rate(rabbitmq_channel_messages_published_total[5m])

# Message consumption rate
rate(rabbitmq_channel_messages_delivered_total[5m])

# Active consumers
sum(rabbitmq_consumers)
```

**Troubleshooting**:
- **No RabbitMQ metrics in Prometheus**:
  1. Verify RabbitMQ is healthy: `docker compose ps messagebus`
  2. Check Prometheus targets: http://localhost:9090/targets (look for `rabbitmq` job)
  3. The target should show as `UP` with URL `messagebus:15692`
  4. Check RabbitMQ logs: `docker compose logs messagebus | grep prometheus`

- **Metrics endpoint not accessible**:
  1. Verify plugin is enabled: `docker compose exec messagebus rabbitmq-plugins list | grep prometheus`
  2. Should show `[E*] rabbitmq_prometheus` (E=enabled, *=running)
  3. If disabled, check `infra/rabbitmq/enabled_plugins` file

- **Per-queue metrics missing (no `queue` label)**:
  1. Verify `PROMETHEUS_RETURN_PER_OBJECT_METRICS=true` is set in docker-compose.infra.yml messagebus service
  2. Restart messagebus if the variable was just added: `docker compose restart messagebus`
  3. Wait 15-30 seconds for metrics to populate
  4. Check metrics endpoint directly: `curl http://localhost:15692/metrics | grep 'rabbitmq_queue_messages_ready{queue='`
  5. Should see metrics with labels like: `rabbitmq_queue_messages_ready{queue="json.parsed",vhost="/"}`

**Dashboard Integration**: RabbitMQ metrics are used in:
- **Queue Status** dashboard - Queue depths, message rates, consumer counts
- **Service Metrics** dashboard - Queue Depths panel
- **Pipeline Flow Visualization** dashboard - Message flow and bottleneck detection

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

## 5.2) MongoDB Document Store Monitoring
- **Grafana Dashboard**: http://localhost:3000 → **MongoDB Document Store Status**
- **MongoDB Direct Access**: http://localhost:27017 (connection string: `mongodb://root:example@localhost:27017/admin`)
- **Prometheus Metrics**: Multiple exporters provide comprehensive MongoDB monitoring

### MongoDB Exporters
The system uses three complementary exporters for complete MongoDB observability:

1. **mongodb-exporter** (Port 9216): Generic MongoDB metrics
   - Server status, operation counters, connection stats
   - Query execution metrics and latency
   - Replication and cluster health
   - Provided by: Percona MongoDB Exporter

2. **mongo-doc-count-exporter** (Port 9500): Document counts per collection
   - Real-time document counts for all system collections
   - Collections monitored: archives, messages, chunks, threads, summaries, reports, sources
   - Metric: `copilot_collection_document_count{database, collection}`

3. **mongo-collstats-exporter** (Port 9503): Collection-level storage statistics
   - Storage size per collection (`mongodb_collstats_storageSize`)
   - Document counts (`mongodb_collstats_count`)
   - Average object size (`mongodb_collstats_avgObjSize`)
   - Index sizes (`mongodb_collstats_totalIndexSize`, `mongodb_collstats_indexSize`)
   - Powers the "Storage Size by Collection" dashboard panel

**Note**: All exporters start automatically with the monitoring stack and require documentdb to be healthy.

### Key Metrics
- **Document Counts**: `copilot_collection_document_count{database="copilot",collection="archives"}`
- **Storage Size**: `mongodb_collstats_storageSize{db="copilot",collection="archives"}`
- **Average Object Size**: `mongodb_collstats_avgObjSize{db="copilot"}`
- **Index Sizes**: `mongodb_collstats_totalIndexSize{db="copilot"}`
- **Operations**: `mongodb_op_counters_total` (insert, query, update, delete, command)
- **Connections**: `mongodb_connections{state="current"}`
- **Query Performance**: `mongodb_op_latencies_latency` (read, write, command latency)

### Monitoring Queries (Prometheus)
```promql
# Total documents across all collections
sum(copilot_collection_document_count{database="copilot"})

# Storage growth rate
deriv(mongodb_collstats_storageSize{db="copilot"}[5m])

# Collection size by collection (for dashboard)
mongodb_collstats_storageSize{db="copilot"}

# Operations per second
rate(mongodb_op_counters_total[5m])

# Current connections
mongodb_connections{state="current"}

# Query latency (microseconds)
mongodb_op_latencies_latency
```

**Dashboard Tips**: 
- Use the **MongoDB Document Store Status** dashboard for comprehensive monitoring
- The "Storage Size by Collection" panel shows disk space usage per collection
- Check operation counters to identify high-traffic collections

### Troubleshooting
- **No storage size data**: 
  1. Verify mongo-collstats-exporter is running: `docker compose ps mongo-collstats-exporter`
  2. If not running, start it: `docker compose up -d mongo-collstats-exporter`
  3. Check exporter logs: `docker compose logs mongo-collstats-exporter`

- **Missing document counts**:
  1. Check Prometheus targets (http://localhost:9090/targets)
  2. Verify `mongo-doc-count` and `mongo-collstats` jobs are UP
  3. Ensure documentdb is healthy: `docker compose ps documentdb`

- **High storage usage**: 
  1. Check storage by collection: `mongodb_collstats_storageSize{db="copilot"}`
  2. Identify largest collections and review data retention policies
  3. Consider collection compaction or archival for old data

- **Slow queries**: 
  1. Review query latency metrics: `mongodb_op_latencies_latency`
  2. Check for missing indexes on frequently queried fields
  3. Use MongoDB explain plans to optimize slow queries

### Direct Database Inspection
```bash
# Connect to MongoDB shell
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin

# Switch to copilot database
use copilot

# Get collection statistics
db.archives.stats()

# Check collection sizes
db.stats()

# List all collections
show collections

# Check indexes for a collection
db.archives.getIndexes()
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
    - Queue depth via RabbitMQ's built-in Prometheus plugin (e.g., `rabbitmq_queue_messages_ready{queue="ingestion"}`).

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

The document processing status exporter starts automatically with the monitoring stack:

```bash
# Start all services (including document processing monitoring)
docker compose up -d

# Or start just the document processing exporter (requires MongoDB to be running)
docker compose up -d document-processing-exporter
```

**Note**: The exporter is enabled by default as part of the core monitoring infrastructure.

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
4. **Avg Pending Archive Age**: Gauge showing how long documents wait for processing (yellow >10 min, red >30 min)
5. **Avg Archive Attempt Count**: Retry distribution indicator
6. **Chunk Embedding Completion Rate**: Percentage of chunks with embeddings
7. **Chunk Embedding Status Over Time**: Trend of embedding generation progress
8. **Stuck Document Detection (Age by Status)**: Multi-line chart showing age of documents in non-completed states (excludes "processed" documents). Yellow alert >10 min, red alert >30 min. Use this to identify documents stuck in pending or failed states.
9. **Archive Status Summary**: Table view with status, count, and age (note: age for processed documents is not useful for stuck detection)
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

# All non-completed documents (detect stuck documents)
copilot_document_age_seconds{collection="archives",status!="processed"}

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
2. Check reporting API for detailed error information
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
2. Review service logs and reporting API for retry context
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
  1. Verify exporter is running: `docker compose ps document-processing-exporter`
  2. If not running, start it: `docker compose up -d document-processing-exporter`
  3. Check exporter logs: `docker compose logs document-processing-exporter`

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
