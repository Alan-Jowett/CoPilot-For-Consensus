<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Document Retry Policy

## Overview

This document defines the retry policy for stuck or failed documents in the Copilot-for-Consensus pipeline. The policy ensures forward progress without infinite loops, provides clear escalation paths, and enables operators to identify and resolve persistent failures.

## Design Goals

1. **Automatic Recovery**: Transient failures (network, resource constraints) should self-heal without operator intervention
2. **Bounded Retries**: Prevent infinite retry loops with clear attempt limits
3. **Exponential Backoff**: Space out retries to avoid overwhelming dependencies
4. **Visibility**: Emit metrics and alerts for stuck/failed documents
5. **Idempotency**: All retries must be safe and produce consistent results
6. **Escalation Path**: Clear procedures for documents exceeding retry limits

## Retry Tracking Fields

All document collections (archives, messages, chunks, threads) include retry tracking fields:

| Field | Type | Description |
|-------|------|-------------|
| `attemptCount` | Integer | Number of processing attempts (0 = never attempted) |
| `lastAttemptTime` | DateTime or null | Timestamp of most recent processing attempt |

These fields are:
- **Optional** in schemas (backward compatible with existing documents)
- **Initialized** to `attemptCount=0, lastAttemptTime=null` on first insert
- **Updated** by services before each processing attempt
- **Indexed** for efficient retry queries

## Retry Thresholds

### Maximum Retry Attempts

| Document Type | Max Attempts | Rationale |
|--------------|--------------|-----------|
| Archives | 3 | Archive parsing failures are usually permanent (corrupt files) |
| Messages | 3 | Message processing failures often indicate data quality issues |
| Chunks | 5 | Embedding generation may have transient model/network issues |
| Threads | 5 | Summarization depends on external LLM availability |

### Stuck Document Threshold

Documents are considered "stuck" if:
- `status` is "pending" or "processing"
- `lastAttemptTime` is older than **24 hours**
- `attemptCount` < max attempts

Stuck documents are eligible for **consideration** on the next retry job run; however, actual retry will only occur if the exponential backoff delay (see below) has also elapsed. In other words, both the "stuck" threshold and the backoff policy must be satisfied before a retry is attempted.

## Exponential Backoff Strategy

Retry delays use exponential backoff to reduce load on dependencies:

```
delay = min(base_delay * 2^(attemptCount - 1), max_delay)
```

**Parameters:**
- `base_delay` = 5 minutes (300 seconds)
- `max_delay` = 60 minutes (3600 seconds)

**Delay Schedule:**
- Attempt 1: Immediate (no delay)
- Attempt 2: 10 minutes after attempt 1
- Attempt 3: 20 minutes after attempt 2
- Attempt 4: 40 minutes after attempt 3
- Attempt 5: 60 minutes after attempt 4 (capped at max)

**Implementation**: Retry job checks `lastAttemptTime + calculated_delay < now()` before requeuing.

## Retry Job Implementation

### Periodic Execution

The retry job runs as a Docker Compose service:

- **Service Name**: `retry-job`
- **Image**: Python with MongoDB and RabbitMQ clients
- **Schedule**: Every 15 minutes (configurable via restart policy + sleep loop)
- **Dependencies**: documentdb, messagebus

### Retry Logic

For each document collection (archives, messages, chunks, threads):

1. **Query Stuck Documents**:
   ```javascript
   {
     status: { $in: ["pending", "processing"] },
     attemptCount: { $lt: MAX_ATTEMPTS },
     $or: [
       { lastAttemptTime: null },
       { lastAttemptTime: { $lt: new Date(Date.now() - STUCK_THRESHOLD_MS) } }
     ]
   }
   ```

2. **Check Backoff Eligibility**:
   - Calculate `next_attempt_time = lastAttemptTime + backoff_delay`
   - Skip if `next_attempt_time > now()` (backoff not elapsed)

3. **Increment Attempt Counter**:
   ```javascript
   db.collection.updateOne(
     { _id: doc._id },
     { 
       $inc: { attemptCount: 1 },
       $set: { lastAttemptTime: new Date() }
     }
   )
   ```

4. **Requeue Event**:
   - Publish original triggering event to message bus
   - For archives: publish `ArchiveIngested` event
   - For messages: publish `JSONParsed` event
   - For chunks: publish `ChunksPrepared` event
   - For threads: publish `SummarizationRequested` event

5. **Emit Metrics**:
   - Increment `retry_job_documents_requeued_total{collection="<name>"}`
   - Observe `retry_job_duration_seconds`

### Failed Documents (Exceeded Retries)

Documents with `attemptCount >= MAX_ATTEMPTS` are:

1. **Marked Permanently Failed**:
   ```javascript
   db.collection.updateOne(
     { _id: doc._id },
     { $set: { status: "failed_max_retries" } }
   )
   ```

2. **Logged for Investigation**:
   - Log at ERROR level with document ID and type
   - Include `lastAttemptTime`, `attemptCount`, and any error context

3. **Emitted to Metrics**:
   - Increment `retry_job_documents_max_retries_exceeded_total{collection="<name>"}`

4. **Alerted (Prometheus)**:
   - Alert if count exceeds threshold (e.g., >10 in 1 hour)

## Metrics

The retry job exposes the following Prometheus metrics via Pushgateway:

### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `retry_job_documents_requeued_total` | collection | Total documents requeued for retry |
| `retry_job_documents_skipped_backoff_total` | collection | Documents skipped due to backoff delay |
| `retry_job_documents_max_retries_exceeded_total` | collection | Documents exceeding max retry attempts |
| `retry_job_runs_total` | status | Retry job executions (status: success/failure) |
| `retry_job_errors_total` | error_type | Errors encountered during retry job |

### Gauges

| Metric | Labels | Description |
|--------|--------|-------------|
| `retry_job_stuck_documents` | collection | Current count of stuck documents |
| `retry_job_failed_documents` | collection | Current count of failed documents (max retries) |

### Histograms

| Metric | Labels | Description |
|--------|--------|-------------|
| `retry_job_duration_seconds` | none | Time taken to complete retry job |

## Alerting

### Prometheus Alert Rules

Alerts are defined in `infra/prometheus/alerts/retry_policy.yml`:

#### StuckDocumentsWarning

```yaml
- alert: StuckDocumentsWarning
  expr: retry_job_stuck_documents > 50
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "High number of stuck documents ({{ $value }})"
    description: "Collection {{ $labels.collection }} has {{ $value }} stuck documents for over 1 hour. Investigate processing pipeline health."
```

#### MaxRetriesExceededCritical

```yaml
- alert: MaxRetriesExceededCritical
  expr: rate(retry_job_documents_max_retries_exceeded_total[1h]) > 10
  for: 15m
  labels:
    severity: critical
  annotations:
    summary: "Documents exceeding max retries ({{ $value }}/hr)"
    description: "Collection {{ $labels.collection }} has documents failing permanently. Review failed queue and error logs."
```

#### RetryJobFailed

```yaml
- alert: RetryJobFailed
  expr: retry_job_runs_total{status="failure"} > 0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Retry job execution failed"
    description: "Retry job encountered errors. Check logs for details."
```

### Grafana Dashboard

A dedicated dashboard `Retry Policy Monitoring` (to be created) includes:

1. **Stuck Documents Panel** (Gauge):
   - Query: `retry_job_stuck_documents`
   - Breakdown by collection
   - Threshold: Warning at 50, Critical at 200

2. **Retry Rate Panel** (Graph):
   - Query: `rate(retry_job_documents_requeued_total[5m])`
   - Per-collection timeseries

3. **Max Retries Exceeded Panel** (Counter):
   - Query: `retry_job_documents_max_retries_exceeded_total`
   - Alert if increasing

4. **Backoff Skipped Panel** (Graph):
   - Query: `retry_job_documents_skipped_backoff_total`
   - Shows backoff effectiveness

5. **Job Duration Panel** (Histogram):
   - Query: `retry_job_duration_seconds`
   - Identify performance degradation

## Escalation Paths

### Tier 1: Automatic Retry (0-24 hours)

- **Action**: Retry job automatically requeues eligible documents
- **Owner**: Automated system
- **SLA**: None (best-effort retry)

### Tier 2: Warning Alert (24-48 hours)

- **Trigger**: Documents stuck >24 hours or >50 stuck documents
- **Action**: Platform/SRE team investigates
- **Owner**: Platform/SRE team
- **SLA**: Investigation within 4 business hours
- **Response**:
  1. Check service health (logs, metrics, resource usage)
  2. Review recent deployments/changes
  3. Inspect stuck documents for patterns
  4. Escalate to service team if needed

### Tier 3: Critical Alert (Max Retries Exceeded)

- **Trigger**: Documents reach max retry attempts
- **Action**: Service team investigation
- **Owner**: Service team (parsing, chunking, embedding, summarization)
- **SLA**: Response within 1 hour
- **Response**:
  1. Review error logs and failed queue messages
  2. Identify root cause (bug, data quality, dependency failure)
  3. Fix issue and deploy if needed
  4. Decide: requeue (if fixable) or purge (if permanent failure)
  5. Document decision in incident log

### Tier 4: Escalation to Engineering Lead (>1000 failures)

- **Trigger**: >1000 documents in failed state or stuck >7 days
- **Action**: Engineering lead coordinates cross-team response
- **Owner**: Engineering lead
- **SLA**: Immediate response, resolution within 24 hours
- **Response**:
  1. Declare incident
  2. Assemble on-call team (SRE + service teams)
  3. Root cause analysis
  4. Implement emergency fixes (hotfix deployment, manual requeue, purge)
  5. Post-mortem and process improvements

## Operational Procedures

### Checking Stuck Documents

**Via MongoDB Query**:
```javascript
db.archives.find({
  status: { $in: ["pending", "processing"] },
  lastAttemptTime: { $lt: new Date(Date.now() - 24*60*60*1000) }
}).count()
```

**Via Grafana**:
- Navigate to "Retry Policy Monitoring" dashboard
- View "Stuck Documents" panel

**Via Prometheus**:
```promql
retry_job_stuck_documents{collection="archives"}
```

### Manual Retry Trigger

If retry job is not running or immediate retry needed:

```bash
# Run retry job manually
docker compose run --rm retry-job

# Or trigger requeue via manage_failed_queues.py
python scripts/manage_failed_queues.py requeue parsing.failed
```

### Purging Permanently Failed Documents

For documents with `attemptCount >= MAX_ATTEMPTS`:

1. **Export for Analysis**:
   ```bash
   python scripts/manage_failed_queues.py export archives.failed --output archives_failed.json
   ```

2. **Review and Decide**:
   - If data is corrupt/invalid: Purge
   - If bug is fixed: Reset `attemptCount` and requeue
   - If still investigating: Leave in failed state

3. **Reset Attempt Counter (if reprocessing)**:
   ```javascript
   db.archives.updateMany(
     { status: "failed_max_retries" },
     { $set: { attemptCount: 0, lastAttemptTime: null, status: "pending" } }
   )
   ```

4. **Purge (if permanent)**:
   ```javascript
   db.archives.deleteMany({ status: "failed_max_retries" })
   ```

### Testing Retry Logic

**Integration Test**:
1. Insert test document with `attemptCount=0, status="pending"`
2. Run retry job
3. Verify `attemptCount=1, lastAttemptTime` updated
4. Verify event published to message bus
5. Verify metrics incremented

**Backoff Test**:
1. Insert document with `attemptCount=2, lastAttemptTime=now() - 5min`
2. Run retry job
3. Verify document skipped (backoff not elapsed)
4. Wait 10 minutes, run retry job again
5. Verify document requeued

**Max Retries Test**:
1. Insert document with `attemptCount=3` (max for archives)
2. Run retry job
3. Verify `status="failed_max_retries"`
4. Verify alert triggered
5. Verify metric incremented

## Service Integration

### Services Update Attempt Fields

All services (parsing, chunking, embedding, orchestrator, summarization) must:

1. **Initialize on Insert**:
   ```python
   document = {
       "archive_id": archive_id,
       "status": "pending",
       "attemptCount": 0,
       "lastAttemptTime": None,
       # ... other fields
   }
   document_store.insert(collection, document)
   ```

2. **Update Before Processing**:
   ```python
   document_store.update(
       collection,
       {"archive_id": archive_id},
       {
           "$inc": {"attemptCount": 1},
           "$set": {"lastAttemptTime": datetime.now(timezone.utc)}
       }
   )
   ```

3. **Update on Success**:
   ```python
   document_store.update(
       collection,
       {"archive_id": archive_id},
       {"$set": {"status": "processed"}}
   )
   ```

4. **Update on Failure**:
   ```python
   # Service does NOT update attemptCount on failure
   # Retry job will handle incrementing attemptCount and requeue
   # Service only publishes *Failed event to failed queue
   ```

### Idempotency Requirements

All retry operations must be idempotent:

- **Parsing**: Skip already-parsed messages (check message document exists by `_id`)
- **Chunking**: Skip duplicate chunks (DuplicateKeyError handling)
- **Embedding**: Use upsert semantics (vectorstore `add_embedding`)
- **Summarization**: Check for an existing summary (e.g., `threads.summary_id` referencing `summaries._id`) before generating

See `documents/CONTRIBUTING.md` for idempotency patterns.

## Configuration

### Environment Variables

The retry job uses these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRY_JOB_INTERVAL_SECONDS` | 900 (15 min) | How often to run retry job |
| `RETRY_JOB_BASE_DELAY_SECONDS` | 300 (5 min) | Base delay for exponential backoff |
| `RETRY_JOB_MAX_DELAY_SECONDS` | 3600 (60 min) | Maximum backoff delay |
| `RETRY_JOB_STUCK_THRESHOLD_HOURS` | 24 | Hours before document is "stuck" |
| `RETRY_JOB_MAX_ATTEMPTS_ARCHIVES` | 3 | Max retries for archives |
| `RETRY_JOB_MAX_ATTEMPTS_MESSAGES` | 3 | Max retries for messages |
| `RETRY_JOB_MAX_ATTEMPTS_CHUNKS` | 5 | Max retries for chunks |
| `RETRY_JOB_MAX_ATTEMPTS_THREADS` | 5 | Max retries for threads |

### Docker Compose Service

```yaml
retry-job:
  build:
    context: ./scripts
    dockerfile: Dockerfile.retry-job
  depends_on:
    documentdb:
      condition: service_healthy
    messagebus:
      condition: service_healthy
    pushgateway:
      condition: service_started
  environment:
    - MONGODB_HOST=documentdb
    - MONGODB_PORT=27017
    - MONGODB_DATABASE=${MONGO_APP_DB:-copilot}
    - MONGODB_USERNAME=${DOC_DB_ADMIN_USERNAME:-root}
    - MONGODB_PASSWORD=${DOC_DB_ADMIN_PASSWORD:-example}
    - RABBITMQ_HOST=messagebus
    - RABBITMQ_PORT=5672
    - RABBITMQ_USERNAME=guest
    - RABBITMQ_PASSWORD=guest
    - METRICS_BACKEND=prometheus_pushgateway
    - PUSHGATEWAY_URL=http://pushgateway:9091
    - RETRY_JOB_INTERVAL_SECONDS=900
  restart: unless-stopped
```

## Future Enhancements

1. **Per-Document Error Context**: Store last error message in document for debugging
2. **Retry Priority Queue**: Retry critical documents (e.g., recent archives) before old ones
3. **Dynamic Backoff**: Adjust backoff based on dependency health metrics
4. **Retry Scheduling**: Allow operators to schedule retries for specific documents
5. **Dead Letter Archive**: Move permanently failed documents to separate collection for analysis
6. **Automated Root Cause Analysis**: Use ML to classify failure patterns and suggest fixes

## Related Documentation

- [FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md) - Failed queue management
- [SERVICE_MONITORING.md](./SERVICE_MONITORING.md) - Service monitoring guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [SCHEMA.md](./SCHEMA.md) - Document schema definitions
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Idempotency patterns

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-16 | GitHub Copilot | Initial retry policy design and documentation |
