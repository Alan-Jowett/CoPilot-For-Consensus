<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Document Processing Status Observability Implementation

## Overview

This implementation adds comprehensive observability for document processing status across all pipeline stages. It enables operators to monitor document flows, detect stuck documents, and troubleshoot processing failures.

## Components Added

### 1. Document Processing Status Exporter
**File**: `scripts/document_processing_exporter.py`

A custom Prometheus exporter that queries MongoDB to expose document processing metrics:

- **Metrics Exposed**:
  - `copilot_document_status_count{collection, status}` - Document counts by status
  - `copilot_document_processing_duration_seconds{collection}` - Average processing time
  - `copilot_document_age_seconds{collection, status}` - Time since last update
  - `copilot_document_attempt_count{collection}` - Average retry attempts
  - `copilot_chunks_embedding_status_count{embedding_generated}` - Embedding completion

- **Configuration**:
  - Port: 9502
  - Scrape interval: 5 seconds
  - Requires MongoDB connectivity

### 2. Docker Compose Service
**File**: `docker-compose.yml` (lines 252-269)

Added `document-processing-exporter` service:
- Starts automatically with the monitoring stack
- Depends on MongoDB
- Exposes metrics on port 9502

### 3. Prometheus Configuration
**File**: `infra/prometheus/prometheus.yml` (lines 61-67)

Added scrape job for the exporter:
```yaml
- job_name: 'document-processing'
  static_configs:
    - targets: ['document-processing-exporter:9502']
```

### 4. Grafana Dashboard
**File**: `infra/grafana/dashboards/document-processing-status.json`

Comprehensive dashboard with 10 panels:
1. Archive Processing Status (bar gauge)
2. Archive Status Over Time (stacked area chart)
3. Avg Archive Processing Duration (gauge with thresholds)
4. Avg Pending Archive Age (gauge)
5. Avg Archive Attempt Count (gauge)
6. Chunk Embedding Completion Rate (gauge)
7. Chunk Embedding Status Over Time (line chart)
8. Document Age by Status (multi-line chart)
9. Archive Status Summary (table)
10. Archive Processing & Failure Rates (rate chart)

**Access**: http://localhost:8080/grafana/ → "Document Processing Status"
**UID**: `copilot-document-processing-status`

### 5. Prometheus Alert Rules
**File**: `infra/prometheus/alerts/document_processing.yml`

Seven alert rules for common failure scenarios:

| Alert | Threshold | Duration | Severity |
|-------|-----------|----------|----------|
| HighDocumentFailureRate | >10% failure rate | 15min | warning |
| DocumentsStuckPending | >1 hour pending | 30min | warning |
| LongDocumentProcessingDuration | >10 minutes | 20min | warning |
| LowEmbeddingCompletionRate | <80% embedded | 20min | warning |
| HighDocumentAttemptCount | >2.5 avg attempts | 15min | warning |
| FailedDocumentsAccumulating | >0.5/sec failures | 10min | critical |
| DocumentsStuckProcessing | >2 hours processing | 1hour | critical |

Each alert includes:
- Actionable description
- Troubleshooting steps
- Related commands/queries

### 6. Service Metrics Emission
**Files**: `parsing/app/service.py`, `chunking/app/service.py`, `embedding/app/service.py`, `ingestion/app/service.py`

Added status transition metrics to services:

- **Ingestion**: `ingestion_archive_status_transitions_total{status="pending"}`
- **Parsing**: `parsing_archive_status_transitions_total{status="processed|failed"}`
- **Chunking**: `chunking_chunk_status_transitions_total{embedding_generated="false"}`
- **Embedding**: `embedding_chunk_status_transitions_total{embedding_generated="true"}`

Also added:
- `updated_at` timestamps to all document updates
- `created_at` timestamps to new documents

### 7. Documentation
**File**: `documents/SERVICE_MONITORING.md` (section 9.4)

Added comprehensive documentation including:
- How to enable the exporter
- Key metrics and their interpretation
- Dashboard panel descriptions
- Prometheus query examples
- Alert rules and thresholds
- Operational triage guide with 5 detailed scenarios:
  1. High failure rate
  2. Documents stuck in pending
  3. Low embedding completion rate
  4. Long processing duration
  5. High attempt count
- MongoDB direct inspection queries
- Troubleshooting guide

### 8. Tests
**File**: `tests/test_document_processing_exporter.py`

Unit tests for the exporter:
- Configuration reading
- Metric definitions
- Archive status counting
- Chunk embedding status counting
- Metrics collection with mock database

All tests pass (6/6).

## How to Use

### Enable the Exporter

```bash
# Start all services (including document processing monitoring)
docker compose up -d

# Or start just the document processing exporter
docker compose up -d document-processing-exporter
```

### Access the Dashboard

1. Open Grafana: http://localhost:8080/grafana/ (admin/admin)
2. Navigate to "Document Processing Status" dashboard
3. Select time range (default: last 1 hour)
4. Refresh automatically every 10 seconds

### Query Metrics Directly

In Prometheus (http://localhost:9090):

```promql
# Current status distribution
copilot_document_status_count{collection="archives"}

# Failure rate
copilot_document_status_count{collection="archives",status="failed"}
/ (copilot_document_status_count{collection="archives",status="failed"}
   + copilot_document_status_count{collection="archives",status="processed"})

# Embedding completion
copilot_chunks_embedding_status_count{embedding_generated="True"}
/ (copilot_chunks_embedding_status_count{embedding_generated="True"}
   + copilot_chunks_embedding_status_count{embedding_generated="False"})
```

### Monitor Alerts

View active alerts:
- Prometheus UI: http://localhost:9090/alerts
- Filter by group: `document_processing`

## Operational Scenarios

### Scenario 1: High Failure Rate Alert Fires

**Symptoms**:
- `HighDocumentFailureRate` alert active
- Dashboard shows increasing failed count

**Actions**:
1. Check dashboard "Archive Processing Status" panel
2. Review parsing service logs: `docker compose logs parsing | grep -i error`
3. Query failed archives in MongoDB:
   ```javascript
   db.archives.find({status: "failed"}).limit(10)
   ```
4. Check reporting service or logs for error details
5. If transient, reprocess; if systematic, fix root cause first

### Scenario 2: Documents Stuck in Pending

**Symptoms**:
- `DocumentsStuckPending` alert active
- "Avg Pending Archive Age" gauge is red

**Actions**:
1. Check RabbitMQ ingestion queue: http://localhost:15672
2. Verify parsing service running: `docker compose ps parsing`
3. Check for consumer issues in RabbitMQ UI
4. Restart parsing service if needed: `docker compose restart parsing`
5. Monitor dashboard to confirm pending count decreases

### Scenario 3: Low Embedding Completion Rate

**Symptoms**:
- `LowEmbeddingCompletionRate` alert active
- "Chunk Embedding Completion Rate" gauge below 80%

**Actions**:
1. Check embedding service: `docker compose ps embedding`
2. Verify Qdrant: `curl http://localhost:6333/collections`
3. Check Ollama: `docker compose ps ollama`
4. Review embedding logs: `docker compose logs embedding`
5. Scale embedding service if needed

## Architecture Notes

### Exporter Design

The exporter uses MongoDB aggregation pipelines to efficiently calculate metrics:
- Groups by status for counts
- Calculates averages for age/duration/attempts
- Uses `$ifNull` to handle missing timestamps gracefully
- Runs every 5 seconds to balance freshness vs. database load

### Metric Naming Convention

All metrics follow the pattern:
- `copilot_<component>_<metric>_<type>`
- Labels: `{collection, status, embedding_generated}`
- Type suffixes: `_count`, `_seconds`, `_total`

### Alert Rule Philosophy

Alerts use graduated severity:
- **Warning**: Requires investigation within hours
- **Critical**: Requires immediate action (within 30 minutes)
- **Emergency**: All-hands incident (immediate)

Each alert includes:
- Clear symptom description
- Quantified thresholds
- Step-by-step remediation
- Links to relevant dashboards/docs

## Future Enhancements

Potential additions for future iterations:

1. **Worker ID Tracking**: Add `workerId` field to documents to track which service instance processed them
2. **Processing History**: Store status transition history in a separate collection
3. **Correlation with Failed Queues**: Link document failures to failed queue messages
4. **SLA Tracking**: Add P95/P99 processing time metrics
5. **Predictive Alerts**: Use rate of change to predict future failures
6. **Auto-Remediation**: Automatically requeue stuck documents after threshold

## Testing

### Unit Tests
Run exporter tests:
```bash
python tests/test_document_processing_exporter.py
```

### Integration Testing
1. Start full stack: `docker compose up -d`
2. Ingest test data: `docker compose run --rm ingestion`
3. Verify metrics appear in Prometheus
4. Check dashboard displays data
5. Trigger alert conditions to test alerting

### Validation Checklist
- [x] Exporter script syntax valid
- [x] Dashboard JSON valid
- [x] Alert rules YAML valid
- [x] Service files compile
- [x] Unit tests pass
- [ ] Integration tests with live data (requires full environment)
- [ ] Alert rules fire correctly (requires triggering conditions)

## References

- Prometheus exporter pattern: Based on `qdrant_exporter.py` and `mongo_doc_count_exporter.py`
- Grafana dashboard: Follows same structure as `vectorstore-status.json`
- Alert rules: Consistent with `failed_queues.yml` pattern
- Documentation: Extends `SERVICE_MONITORING.md` section 9 series

## Troubleshooting

**Exporter not running**:
```bash
docker compose ps document-processing-exporter
docker compose logs document-processing-exporter
```

**No metrics in Prometheus**:
- Check targets: http://localhost:9090/targets (should show `document-processing` UP)
- Verify MongoDB connectivity from exporter
- Check for errors in exporter logs

**Dashboard shows no data**:
- Verify time range is appropriate
- Ensure MongoDB has documents with expected fields
- Check Prometheus has data: query `copilot_document_status_count`

**Alerts not firing**:
- Verify alert rules loaded: http://localhost:9090/rules
- Check actual metric values meet threshold
- Review alert `for` duration hasn't elapsed yet
