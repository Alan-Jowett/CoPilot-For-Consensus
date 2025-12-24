<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Observability RFC: Production-Ready Metrics, Logs, and Tracing

**Status**: Draft  
**Author**: Copilot-for-Consensus Team  
**Date**: 2025-12-24  
**Version**: 1.0

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Goals and Non-Goals](#goals-and-non-goals)
3. [Architecture Overview](#architecture-overview)
4. [Metrics Standards](#metrics-standards)
5. [Logging Standards](#logging-standards)
6. [Alerting Strategy](#alerting-strategy)
7. [Service Level Objectives (SLOs)](#service-level-objectives-slos)
8. [Dashboards and Visualization](#dashboards-and-visualization)
9. [Distributed Tracing](#distributed-tracing)
10. [Resource Management](#resource-management)
11. [Retention Policies](#retention-policies)
12. [Implementation Guide](#implementation-guide)
13. [Operational Runbooks](#operational-runbooks)
14. [Open Questions](#open-questions)
15. [Glossary](#glossary)

---

## Executive Summary

This RFC establishes a production-ready observability strategy for Copilot-for-Consensus, covering metrics collection, log aggregation, alerting, and distributed tracing. The goal is to provide operators with actionable insights into system health, performance, and reliability while maintaining bounded resource usage and clear operational procedures.

**Key Deliverables:**
- Standardized metrics naming and labeling conventions
- Comprehensive alert rules with SLO-based thresholds
- Structured logging with consistent schema
- Production-hardened exporters and collectors
- Operator runbooks with troubleshooting guides
- Distributed tracing evaluation and implementation plan

---

## Goals and Non-Goals

### Goals

1. **Standardization**: Consistent metrics names, labels, and types across all services
2. **Actionability**: Every alert must be actionable with clear remediation steps
3. **Bounded Cardinality**: Prevent metric explosion through careful label design
4. **Production Readiness**: Resource limits, health checks, and fail-fast behavior
5. **Operator Empowerment**: Clear runbooks and dashboards for troubleshooting
6. **Incremental Adoption**: Phased rollout without requiring big-bang changes

### Non-Goals

1. **Real-time Log Analytics**: Loki is for log aggregation, not real-time SIEM
2. **APM Features**: This RFC focuses on metrics/logs/traces, not full APM
3. **Cost Optimization**: Cloud cost management is out of scope (local/dev focus)
4. **Multi-Cluster**: Single-cluster observability only (no federation)

---

## Architecture Overview

### Current State

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   Services      │────▶│ Pushgateway  │────▶│ Prometheus  │
│ (Push Metrics)  │     │  (Aggregator)│     │  (TSDB)     │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                      │
┌─────────────────┐                                  │
│  Exporters      │                                  │
│  (Pull Model)   │──────────────────────────────────┘
│ - MongoDB       │                                  │
│ - RabbitMQ      │                                  ▼
│ - Qdrant        │                            ┌──────────┐
│ - cAdvisor      │                            │ Grafana  │
└─────────────────┘                            │(Dashboards)│
                                               └──────────┘
┌─────────────────┐     ┌──────────────┐           │
│ Docker Logs     │────▶│  Promtail    │────▶      │
│ (Container Out) │     │ (Shipper)    │     │     │
└─────────────────┘     └──────────────┘     ▼     │
                                         ┌──────────┘
                                         │   Loki    │
                                         │(Log Store)│
                                         └───────────┘
```

### Components

| Component | Purpose | Port | Health Check |
|-----------|---------|------|--------------|
| **Prometheus** | Metrics storage & querying | 9090 | `/-/ready` |
| **Pushgateway** | Metrics aggregation for batch jobs | 9091 | `/-/ready` |
| **Grafana** | Dashboards & visualization | 3000 | `/api/health` |
| **Loki** | Log aggregation | 3100 | `/ready` |
| **Promtail** | Log shipping | 9080 | TCP check |
| **Custom Exporters** | Domain-specific metrics | 9500+ | `/metrics` |
| **RabbitMQ Exporter** | Built-in plugin | 15692 | `/metrics` |
| **MongoDB Exporter** | Community exporter | 9216 | `/metrics` |
| **cAdvisor** | Container metrics | 8080 | `/healthz` |

---

## Metrics Standards

### Naming Conventions

All metrics MUST follow this pattern:

```
<namespace>_<subsystem>_<metric>_<unit>_<type>
```

**Examples:**
- `copilot_parsing_messages_parsed_total` (counter)
- `copilot_embedding_generation_duration_seconds` (histogram)
- `copilot_queue_depth_messages` (gauge)

### Namespace Hierarchy

| Namespace | Usage |
|-----------|-------|
| `copilot_*` | Application metrics (services) |
| `rabbitmq_*` | Message bus metrics |
| `mongodb_*` | Database metrics |
| `qdrant_*` | Vector store metrics |
| `container_*` | Resource usage (cAdvisor) |

### Label Schema

#### Required Labels (All Metrics)

```yaml
service: <service_name>  # e.g., "parsing", "embedding", "orchestrator"
environment: <env>       # e.g., "dev", "staging", "prod"
```

#### Domain-Specific Labels

**Queue Metrics:**
```yaml
queue: <queue_name>      # e.g., "parsing", "chunking.failed"
vhost: <vhost>           # RabbitMQ virtual host (default: "/")
```

**Database Metrics:**
```yaml
collection: <name>       # MongoDB collection or Qdrant collection
database: <db_name>      # Database name
```

**Status Metrics:**
```yaml
status: <state>          # e.g., "pending", "processed", "failed"
outcome: <result>        # e.g., "success", "failure", "timeout"
```

**Error Metrics:**
```yaml
error_type: <class>      # e.g., "ConnectionError", "TimeoutError"
error_code: <code>       # HTTP status code or error code
```

### Cardinality Bounds

| Label Type | Max Cardinality | Notes |
|------------|-----------------|-------|
| `service` | ~20 | One per microservice |
| `queue` | ~30 | Work + failed queues |
| `collection` | ~10 | MongoDB/Qdrant collections |
| `status` | ~6 | pending/processing/processed/failed/retrying/archived |
| `error_type` | ~50 | Exception class names only |
| `error_code` | ~60 | HTTP codes (200-599) |

**Prohibited High-Cardinality Labels:**
- ❌ `user_id`, `email`, `ip_address`
- ❌ `message_id`, `document_id`, `thread_id`
- ❌ `timestamp`, `request_id`, `trace_id`

Use exemplars or structured logs for high-cardinality data.

### Metric Types

#### Counter
**Definition**: Monotonically increasing value (resets on restart).  
**Use Cases**: Total messages processed, errors, requests.  
**Suffix**: `_total`

```python
copilot_parsing_messages_parsed_total{service="parsing", status="success"} 1234
```

#### Gauge
**Definition**: Value that can increase or decrease.  
**Use Cases**: Queue depth, active connections, memory usage.  
**Suffix**: None (or `_current`, `_bytes`, `_messages`)

```python
copilot_queue_depth_messages{queue="parsing", service="parsing"} 42
```

#### Histogram
**Definition**: Distribution of values (buckets + sum/count).  
**Use Cases**: Latencies, sizes, durations.  
**Suffix**: `_seconds`, `_bytes`, `_tokens`

```python
copilot_parsing_duration_seconds_bucket{le="0.1", service="parsing"} 100
copilot_parsing_duration_seconds_bucket{le="0.5", service="parsing"} 450
copilot_parsing_duration_seconds_sum{service="parsing"} 123.45
copilot_parsing_duration_seconds_count{service="parsing"} 500
```

**Standard Buckets:**
- **Latency**: `[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5, 10, 30, 60]` (seconds)
- **Size**: `[1024, 10240, 102400, 1048576, 10485760]` (bytes)
- **Tokens**: `[100, 500, 1000, 2000, 4000, 8000, 16000]`

#### Summary
**Not recommended** (use histogram instead for better aggregation).

### Per-Service Metrics Checklist

Every service MUST expose:

#### Required Metrics (Baseline)
- [ ] `<service>_messages_processed_total{status}` - Total messages processed
- [ ] `<service>_processing_duration_seconds` - Message processing latency (histogram)
- [ ] `<service>_failures_total{error_type}` - Total failures by error type
- [ ] `<service>_active_workers_current` - Current active worker count (gauge)

#### Optional Metrics (Recommended)
- [ ] `<service>_queue_depth_messages{queue}` - Current queue depth (if applicable)
- [ ] `<service>_retry_attempts_total` - Total retry attempts
- [ ] `<service>_batch_size_messages` - Batch size distribution (histogram)
- [ ] `<service>_dependency_call_duration_seconds{dependency}` - External call latency

---

## Logging Standards

### Log Levels

| Level | Usage | Examples |
|-------|-------|----------|
| **DEBUG** | Development only, never in production | Variable values, detailed traces |
| **INFO** | Normal operations, state transitions | "Processing message X", "Archive parsed" |
| **WARNING** | Recoverable errors, degraded performance | "Retry attempt 2/3", "Queue depth high" |
| **ERROR** | Failures requiring attention | "Failed to parse message", "Database timeout" |
| **CRITICAL** | Service-impacting failures | "Unable to connect to MongoDB" |

### Structured Logging Schema

All logs MUST be JSON-formatted with these fields:

```json
{
  "timestamp": "2025-12-24T12:34:56.789Z",
  "level": "INFO",
  "service": "parsing",
  "logger": "app.service",
  "message": "Archive processed successfully",
  "trace_id": "abc123",
  "span_id": "def456",
  "labels": {
    "archive_id": "ietf-123",
    "status": "processed",
    "duration_ms": 1234
  },
  "error": {
    "type": "ConnectionError",
    "message": "Connection refused",
    "stack_trace": "..."
  }
}
```

**Required Fields:**
- `timestamp` (ISO 8601 with milliseconds)
- `level` (uppercase)
- `service` (service name)
- `message` (human-readable)

**Optional Fields:**
- `trace_id`, `span_id` (for distributed tracing)
- `labels` (contextual key-value pairs)
- `error` (for ERROR/CRITICAL levels)

### Log Aggregation

**Loki Configuration:**
- Stream labels: `{service="<name>", environment="<env>", level="<level>"}`
- Do NOT use high-cardinality labels (message_id, trace_id) in streams
- Use LogQL queries to filter by trace_id or other dynamic fields

**Example LogQL Queries:**
```logql
# All errors from parsing service
{service="parsing", level="ERROR"}

# Errors with specific trace ID
{service="parsing"} |= "trace_id=abc123" | json | level="ERROR"

# Failed archives
{service="parsing"} | json | labels_status="failed"
```

---

## Alerting Strategy

### Alert Severity Levels

| Severity | Response Time | Notification | Examples |
|----------|---------------|--------------|----------|
| **Info** | None (FYI) | Slack, Email | Deployment completed |
| **Warning** | 4 hours | Slack, Ticket | Queue depth elevated |
| **Error** | 1 hour | PagerDuty (daytime) | High failure rate |
| **Critical** | 30 minutes | PagerDuty (24/7) | Service down |
| **Emergency** | Immediate | PagerDuty + Escalation | Data loss risk |

### Alert Design Principles

1. **Symptom-Based**: Alert on user/business impact, not internal states
2. **Actionable**: Every alert must have clear remediation steps
3. **Non-Flapping**: Use `for` clauses to prevent flapping (min 5 minutes)
4. **Grouped**: Use `group_by` to reduce alert fatigue
5. **Contextual**: Include relevant labels and annotations

### Alert Template

```yaml
- alert: <AlertName>
  expr: <PromQL expression>
  for: <duration>
  labels:
    severity: <warning|error|critical|emergency>
    component: <message_bus|document_processing|vectorstore>
    service: <service_name>
  annotations:
    summary: "One-line description with {{ $value }}"
    description: |
      Detailed explanation with context.
      
      Impact: What users/operators will observe.
      
      Actions:
        1. Check X
        2. Verify Y
        3. Escalate if Z
      
      Runbook: documents/<RUNBOOK>.md
      Dashboard: <Grafana dashboard link>
```

---

## Service Level Objectives (SLOs)

### Definition

An SLO defines the target reliability for a service metric over a time window.

**Format**: `<metric> <comparator> <target> over <window>`

**Example**: `99% of requests complete in < 1s over 30 days`

### Core SLOs

#### 1. Request Latency

| Service | P95 Latency Target | P99 Latency Target |
|---------|-------------------|-------------------|
| Ingestion API | < 500ms | < 1s |
| Parsing | < 5s/message | < 10s/message |
| Chunking | < 2s/message | < 5s/message |
| Embedding | < 10s/chunk | < 30s/chunk |
| Summarization | < 30s/thread | < 60s/thread |
| Reporting API | < 200ms | < 500ms |

**Alert**: Fire when P95 exceeds target for 10 minutes.

#### 2. Error Rate

| Service | Error Budget (30d) | Critical Threshold |
|---------|-------------------|-------------------|
| All Services | < 1% (99% success) | > 5% over 15 min |
| Ingestion | < 0.1% (99.9%) | > 1% over 15 min |

**Alert**: Fire when error rate exceeds critical threshold.

#### 3. Queue Lag

| Queue | Max Age (Pending) | Critical Threshold |
|-------|------------------|-------------------|
| Parsing | < 5 minutes | > 30 minutes |
| Chunking | < 2 minutes | > 15 minutes |
| Embedding | < 10 minutes | > 60 minutes |
| Summarization | < 15 minutes | > 120 minutes |

**Alert**: Fire when oldest message exceeds critical threshold.

#### 4. Throughput

| Service | Min Throughput | Critical Threshold |
|---------|---------------|-------------------|
| Parsing | > 10 msg/min | < 1 msg/min for 10 min |
| Chunking | > 50 msg/min | < 5 msg/min for 10 min |
| Embedding | > 100 chunks/min | < 10 chunks/min for 10 min |

**Alert**: Fire when throughput drops below critical for sustained period.

#### 5. Availability

| Component | Uptime Target | Alert Threshold |
|-----------|--------------|----------------|
| MongoDB | 99.9% | Down for 1 minute |
| RabbitMQ | 99.9% | Down for 1 minute |
| Qdrant | 99.5% | Down for 5 minutes |
| Ollama | 99% | Down for 10 minutes |

**Alert**: Fire immediately when component is unhealthy.

### SLO Dashboard

Create a dedicated **SLO Dashboard** in Grafana showing:
- Current SLO compliance (% within target)
- Error budget remaining (30-day rolling window)
- Trend charts (7-day, 30-day)
- Burn rate alerts (4x, 10x normal rate)

---

## Dashboards and Visualization

### Dashboard Standards

#### Naming Convention
```
<domain>-<view>.json
```

**Examples:**
- `system-health.json` - Overall system status
- `queue-status.json` - RabbitMQ queues
- `service-metrics.json` - Per-service metrics
- `slo-dashboard.json` - SLO compliance

#### Required Elements

1. **Title Row**: Service name, refresh interval, time range
2. **Key Metrics Row**: Most important metrics at the top
3. **Details Rows**: Breakdown by component/queue/status
4. **Logs Row**: Link to Loki logs (Explore view)
5. **Variables**: `service`, `environment`, `time_range`

#### Templating

Use variables for:
- `$service` - Service name (multi-select)
- `$environment` - Environment (dev/staging/prod)
- `$queue` - Queue name (for queue dashboards)
- `$collection` - Collection name (for database dashboards)

**Example Query with Variables:**
```promql
rate(copilot_${service}_messages_processed_total{environment="$environment"}[5m])
```

#### Panel Guidelines

**Color Scheme:**
- Green: Healthy (< threshold)
- Yellow: Warning (> warning threshold)
- Orange: Error (> error threshold)
- Red: Critical (> critical threshold)

**Thresholds:**
- Use absolute values or percentages consistently
- Align with alert thresholds
- Show threshold lines on graphs

**Annotations:**
- Deployment events (from CI/CD)
- Alert firing events
- Manual incident markers

### Core Dashboards

| Dashboard | Purpose | Panels |
|-----------|---------|--------|
| **System Health** | Overall system status | Service health, resource usage, error rates |
| **Queue Status** | RabbitMQ monitoring | Queue depth, consumer count, message rates |
| **Service Metrics** | Per-service performance | Latency, throughput, errors by service |
| **MongoDB Status** | Database monitoring | Connection pool, collection stats, query times |
| **Vectorstore Status** | Qdrant monitoring | Vector count, collection size, search latency |
| **Document Processing** | Pipeline flow | Status counts, processing duration, failure rates |
| **SLO Dashboard** | SLO compliance | Error budget, burn rate, compliance percentage |
| **Failed Queues** | DLQ monitoring | Failed message counts, age, error types |
| **Resource Usage** | Container resources | CPU, memory, disk, network by service |
| **Logs Overview** | Log aggregation | Error counts, log volume, search interface |

---

## Distributed Tracing

### Goals

1. **End-to-End Visibility**: Trace requests from ingestion → reporting
2. **Latency Breakdown**: Identify slow components in the pipeline
3. **Error Correlation**: Link failures across service boundaries
4. **Dependency Mapping**: Visualize service interactions

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Services   │────▶│ OTLP Exporter│────▶│   Tempo     │
│ (OpenTelemetry)   │ (gRPC/HTTP)  │     │ (Trace Store)│
└─────────────┘     └──────────────┘     └─────────────┘
                                                │
                                                ▼
                                          ┌──────────┐
                                          │ Grafana  │
                                          │(Trace UI)│
                                          └──────────┘
```

### Instrumentation Strategy

#### Phase 1: Critical Path (Immediate)
1. **Ingestion → Parsing**: Track archive processing latency
2. **Parsing → Chunking**: Track message chunking latency
3. **Chunking → Embedding**: Track embedding generation latency
4. **Orchestrator → Summarization**: Track RAG workflow latency

**Implementation**: Auto-instrumentation for RabbitMQ consumer spans.

#### Phase 2: External Dependencies (Next)
1. MongoDB queries (read/write latency)
2. Qdrant searches (vector search latency)
3. Ollama API calls (LLM inference latency)
4. HTTP API requests (ingestion, reporting)

**Implementation**: Manual instrumentation with OpenTelemetry SDK.

#### Phase 3: Fine-Grained (Future)
1. Function-level spans for complex operations
2. Database connection pool metrics
3. Cache hit/miss rates
4. Retry and circuit breaker events

### Span Attributes

**Standard Attributes:**
```python
{
    "service.name": "parsing",
    "span.kind": "consumer",
    "messaging.system": "rabbitmq",
    "messaging.destination": "parsing",
    "messaging.message_id": "abc123",
    "db.system": "mongodb",
    "db.operation": "find",
    "db.collection": "archives",
    "http.method": "POST",
    "http.url": "/api/sources",
    "http.status_code": 200
}
```

**Custom Attributes:**
```python
{
    "copilot.archive_id": "ietf-123",
    "copilot.message_count": 42,
    "copilot.chunk_count": 156,
    "copilot.embedding_model": "all-MiniLM-L6-v2",
    "copilot.llm_backend": "ollama",
    "copilot.llm_model": "mistral"
}
```

### Sampling Strategy

**Development**: 100% sampling (all traces)  
**Staging**: 50% sampling (performance testing)  
**Production**: 10% sampling (reduce storage costs)  
**On Error**: 100% sampling (always sample failed requests)

### Trace Backend Options

| Backend | Pros | Cons | Recommendation |
|---------|------|------|----------------|
| **Grafana Tempo** | OSS, Grafana integration, low cost | Newer project, smaller community | ✅ Recommended |
| **Jaeger** | Mature, feature-rich, good docs | More complex setup, higher resource usage | Alternative |
| **Zipkin** | Lightweight, easy setup | Limited features, less active | Not recommended |

**Decision**: Use **Grafana Tempo** for consistency with existing Grafana stack.

---

## Resource Management

### Exporter Resource Limits

All exporters MUST have resource limits defined:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
    reservations:
      cpus: '0.1'
      memory: 128M
```

#### Recommended Limits

| Service | CPU Limit | Memory Limit | Notes |
|---------|-----------|--------------|-------|
| Prometheus | 2 cores | 2GB | Increase for high cardinality |
| Pushgateway | 0.5 cores | 512MB | Stateless, can scale horizontally |
| Grafana | 1 core | 1GB | Increase for many dashboards |
| Loki | 2 cores | 2GB | Increase for high log volume |
| Promtail | 0.5 cores | 256MB | Low overhead |
| MongoDB Exporter | 0.25 cores | 256MB | Lightweight |
| Qdrant Exporter | 0.25 cores | 256MB | Lightweight |
| cAdvisor | 0.5 cores | 512MB | Privileged, monitor carefully |

### Health and Readiness Checks

All exporters and collectors MUST have health checks:

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:9090/-/ready || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 30s
```

#### Exporter Health Endpoints

| Exporter | Health Check |
|----------|--------------|
| Prometheus | `/-/ready`, `/-/healthy` |
| Pushgateway | `/-/ready` |
| Custom Python Exporters | `/metrics` (HTTP 200) |
| RabbitMQ | `/api/health/checks/alarms` |
| MongoDB Exporter | `/metrics` (HTTP 200) |

### Fail-Fast Behavior

Exporters SHOULD:
1. Exit on startup if dependencies are unavailable (fail-fast)
2. Log errors but continue if transient failures occur during operation
3. Expose `up` metric (1 = healthy, 0 = unhealthy)

**Example:**
```python
exporter_up = Gauge('exporter_up', 'Exporter health status (1=up, 0=down)')

try:
    collect_metrics()
    exporter_up.set(1)
except Exception as e:
    logger.error(f"Metric collection failed: {e}")
    exporter_up.set(0)
```

---

## Retention Policies

### Metrics Retention

| Environment | Retention Period | Scrape Interval | Storage Size (est) |
|-------------|-----------------|-----------------|-------------------|
| **Development** | 7 days | 15s | ~5GB |
| **Staging** | 30 days | 15s | ~20GB |
| **Production** | 90 days | 10s | ~100GB |

**Configuration** (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

storage:
  tsdb:
    retention.time: 30d
    retention.size: 20GB
```

### Logs Retention

| Environment | Retention Period | Storage Size (est) | Notes |
|-------------|-----------------|-------------------|-------|
| **Development** | 3 days | ~1GB | Short for rapid iteration |
| **Staging** | 14 days | ~5GB | Enough for debugging |
| **Production** | 30 days | ~20GB | Compliance/forensics |

**Configuration** (`loki-config.yml`):
```yaml
limits_config:
  retention_period: 720h  # 30 days

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
  retention_enabled: true
  retention_delete_delay: 2h
```

### Trace Retention

| Environment | Retention Period | Sampling Rate | Storage Size (est) |
|-------------|-----------------|---------------|-------------------|
| **Development** | 3 days | 100% | ~2GB |
| **Staging** | 7 days | 50% | ~3GB |
| **Production** | 14 days | 10% | ~5GB |

**Configuration** (Tempo):
```yaml
storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
    pool:
      max_workers: 100
      queue_depth: 10000

retention:
  retention_period: 336h  # 14 days
```

### Storage Monitoring

Add alerts for storage usage:
```yaml
- alert: PrometheusStorageAlmostFull
  expr: prometheus_tsdb_storage_blocks_bytes / prometheus_tsdb_retention_limit_bytes > 0.9
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Prometheus storage is {{ $value | humanizePercentage }} full"
```

---

## Implementation Guide

### Phase 1: Metrics Standardization (Week 1-2)

#### Tasks
1. [ ] Audit existing metrics across all services
2. [ ] Rename metrics to follow naming conventions
3. [ ] Add missing required labels (`service`, `environment`)
4. [ ] Document metrics in per-service README files
5. [ ] Update Grafana dashboard queries to use new names

#### Checklist
- [ ] Update `adapters/copilot_metrics/` with new label schema
- [ ] Add `METRICS.md` to each service directory
- [ ] Update `SERVICE_MONITORING.md` with new conventions
- [ ] Update existing dashboards to use new metric names

### Phase 2: Alert Rules (Week 2-3)

#### Tasks
1. [ ] Define SLO targets for each service
2. [ ] Write alert rules for each SLO
3. [ ] Add annotations with runbook links
4. [ ] Test alerts with mock data
5. [ ] Deploy to staging environment

#### Files to Create/Update
- [ ] `infra/prometheus/alerts/service_health.yml`
- [ ] `infra/prometheus/alerts/queue_lag.yml`
- [ ] `infra/prometheus/alerts/resource_limits.yml`
- [ ] `infra/prometheus/alerts/slo_latency.yml`
- [ ] `infra/prometheus/alerts/slo_errors.yml`

### Phase 3: Dashboards (Week 3-4)

#### Tasks
1. [ ] Add variables to existing dashboards
2. [ ] Standardize panel colors/thresholds
3. [ ] Add runbook links to panels
4. [ ] Create SLO dashboard
5. [ ] Version control all dashboards (Git)

#### Dashboards to Update
- [ ] `system-health.json` - Add SLO indicators
- [ ] `queue-status.json` - Add age/lag metrics
- [ ] `service-metrics.json` - Add latency histograms
- [ ] `resource-usage.json` - Add limit lines
- [ ] Create `slo-dashboard.json` (new)

### Phase 4: Logging (Week 4-5)

#### Tasks
1. [ ] Implement structured logging in all services
2. [ ] Add trace_id propagation
3. [ ] Configure Loki retention policies
4. [ ] Create log parsing rules (Promtail)
5. [ ] Add log-based alerts (Loki + Prometheus)

### Phase 5: Tracing (Week 6-8)

#### Tasks
1. [ ] Deploy Grafana Tempo
2. [ ] Add OpenTelemetry SDK to services
3. [ ] Instrument critical path (Phase 1)
4. [ ] Configure sampling strategy
5. [ ] Create trace dashboard in Grafana

---

## Operational Runbooks

### Runbook Template

Each alert MUST link to a runbook with this structure:

```markdown
# Runbook: <Alert Name>

## Symptoms
- What the alert indicates
- What users/operators observe

## Impact
- Severity of impact (user-facing, internal)
- Affected services/workflows

## Diagnosis
1. Check dashboard: <link>
2. Query metrics: <PromQL>
3. Check logs: <LogQL>
4. Verify dependencies: <commands>

## Resolution
1. Short-term mitigation (stop the bleeding)
2. Verify fix (commands/queries)
3. Long-term solution (prevent recurrence)

## Escalation
- When to escalate: <criteria>
- Who to contact: <team/oncall>
- Incident severity: <warning/error/critical>

## References
- Related alerts: <links>
- Architecture docs: <links>
- Recent incidents: <links>
```

### Core Runbooks

Create these runbooks in `documents/runbooks/`:

1. **High Queue Lag** (`high-queue-lag.md`)
2. **Service Down** (`service-down.md`)
3. **High Error Rate** (`high-error-rate.md`)
4. **Database Connection Failures** (`database-connection-failures.md`)
5. **Memory Exhaustion** (`memory-exhaustion.md`)
6. **Disk Space Low** (`disk-space-low.md`)
7. **Failed Queue Growing** (`failed-queue-growing.md`)

---

## Open Questions

### 1. Pushgateway vs Pull-Only Metrics

**Question**: Keep Pushgateway for batch jobs or migrate to pull-only?

**Options:**
1. **Keep Pushgateway** (current)
   - Pros: Works for batch jobs, simple integration
   - Cons: Single point of failure, stale metrics, no backpressure
2. **Migrate to Pull-Only**
   - Pros: Simpler architecture, consistent scraping
   - Cons: Requires exposing `/metrics` on all services

**Recommendation**: Keep Pushgateway for now, revisit if it becomes a bottleneck.

**Decision**: TBD (pending team discussion)

### 2. Tracing Backend

**Question**: Use Tempo or Jaeger for distributed tracing?

**Analysis:**
- Tempo: Better Grafana integration, lower cost, newer
- Jaeger: More mature, feature-rich, larger community

**Recommendation**: Start with Tempo for consistency with Grafana stack.

**Decision**: TBD (pilot Tempo in staging)

### 3. Metrics and Logs Retention

**Question**: What retention windows are appropriate for dev vs prod?

**Proposal:**
- Dev: 7 days metrics, 3 days logs (fast iteration)
- Staging: 30 days metrics, 14 days logs (integration testing)
- Prod: 90 days metrics, 30 days logs (compliance)

**Decision**: TBD (pending storage capacity analysis)

### 4. Alert Routing

**Question**: How should alerts be routed (Slack, email, PagerDuty)?

**Proposal:**
- Info/Warning → Slack (#monitoring)
- Error → Slack + Email (daytime hours)
- Critical → PagerDuty (24/7 on-call)
- Emergency → PagerDuty + Escalation

**Decision**: TBD (pending on-call rotation setup)

---

## Glossary

| Term | Definition |
|------|------------|
| **SLO** | Service Level Objective - Target reliability metric |
| **SLI** | Service Level Indicator - Measured metric for SLO |
| **SLA** | Service Level Agreement - Contractual commitment |
| **Error Budget** | Allowed % of failures before violating SLO |
| **Burn Rate** | Rate at which error budget is consumed |
| **Cardinality** | Number of unique time series for a metric |
| **Exemplar** | Sample trace linked to metric data point |
| **Histogram** | Distribution of values across buckets |
| **Gauge** | Point-in-time value (can go up/down) |
| **Counter** | Monotonically increasing value |
| **Pull Model** | Prometheus scrapes `/metrics` endpoint |
| **Push Model** | Service pushes metrics to Pushgateway |
| **LogQL** | Loki query language (like PromQL for logs) |
| **PromQL** | Prometheus query language |
| **TSDB** | Time-series database (Prometheus storage) |
| **OTLP** | OpenTelemetry Protocol (for traces/metrics) |
| **DLQ** | Dead Letter Queue (failed messages) |
| **P95/P99** | 95th/99th percentile (latency) |

---

## Appendix: Example Queries

### Metrics (PromQL)

```promql
# Service throughput (requests/sec)
rate(copilot_parsing_messages_processed_total[5m])

# P95 latency
histogram_quantile(0.95, rate(copilot_parsing_duration_seconds_bucket[5m]))

# Error rate (%)
(rate(copilot_parsing_failures_total[5m]) / rate(copilot_parsing_messages_processed_total[5m])) * 100

# Queue lag (oldest message age)
max(rabbitmq_queue_message_age_seconds{queue="parsing"})

# Memory usage per service
sum by (service) (container_memory_usage_bytes{name=~"copilot-.*"})
```

### Logs (LogQL)

```logql
# All errors from parsing service
{service="parsing", level="ERROR"}

# Errors with specific error type
{service="parsing"} | json | error_type="ConnectionError"

# Error count per 5 minutes
sum by (service) (rate({level="ERROR"}[5m]))

# Slow queries (> 1s)
{service="parsing"} | json | labels_duration_ms > 1000

# Trace correlation
{service="parsing"} |= "trace_id=abc123"
```

---

## References

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Google SRE Book - Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [OpenTelemetry Instrumentation](https://opentelemetry.io/docs/instrumentation/)
- [The Four Golden Signals](https://sre.google/sre-book/monitoring-distributed-systems/#xref_monitoring_golden-signals)
- Existing docs: `documents/SERVICE_MONITORING.md`, `documents/DOCUMENT_PROCESSING_OBSERVABILITY.md`
