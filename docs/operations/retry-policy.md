<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Document Retry Policy

Defines the retry policy for stuck or failed documents to ensure forward progress, bounded retries, and clear escalation paths.

## Overview
- Automatic recovery for transient failures
- Bounded retries with exponential backoff
- Visibility via metrics and alerts
- Idempotent operations
- Escalation procedures for persistent failures

## Retry Tracking Fields
| Field | Type | Description |
|-------|------|-------------|
| `attemptCount` | Integer | Number of processing attempts (0 = never attempted) |
| `lastAttemptTime` | DateTime or null | Timestamp of most recent processing attempt |

Notes:
- Optional in schemas (backward compatible)
- Initialized to `attemptCount=0, lastAttemptTime=null` on insert
- Updated before each processing attempt; indexed for queries

## Retry Thresholds
### Maximum Retry Attempts
| Document Type | Max Attempts | Rationale |
|--------------|--------------|-----------|
| Archives | 3 | Archive parsing failures are usually permanent |
| Messages | 3 | Message processing failures often indicate data quality issues |
| Chunks | 5 | Embedding generation may have transient issues |
| Threads | 5 | Summarization depends on external LLM availability |

### Stuck Document Threshold
Document considered stuck when:
- `status` in {pending, processing}
- `lastAttemptTime` older than 24 hours
- `attemptCount` < max attempts

## Exponential Backoff
```
delay = min(base_delay * 2^(attemptCount - 1), max_delay)
```
Parameters: `base_delay=300s`, `max_delay=3600s`.
Schedule: immediate, 10m, 20m, 40m, 60m (capped).
Retry job checks `lastAttemptTime + delay < now()` before requeue.

## Retry Job Implementation
- Service: `retry-job` (Docker Compose), depends on documentdb/messagebus.
- Runs ~every 15 minutes.
- Logic per collection: query stuck docs → check backoff → increment attempt → requeue event → emit metrics.

## Metrics
Counters: `retry_job_documents_requeued_total`, `..._skipped_backoff_total`, `..._max_retries_exceeded_total`, `retry_job_runs_total{status}`, `retry_job_errors_total{error_type}`.
Gauges: `retry_job_stuck_documents`, `retry_job_failed_documents`.
Histograms: `retry_job_duration_seconds`.

## Alerting (Prometheus)
- `StuckDocumentsWarning`: `retry_job_stuck_documents > 50` for 1h.
- `MaxRetriesExceededCritical`: `rate(retry_job_documents_max_retries_exceeded_total[1h]) > 10`.
- `RetryJobFailed`: `retry_job_runs_total{status="failure"} > 0` for 5m.

## Grafana Dashboard (planned)
Panels for stuck documents, retry rate, max retries exceeded, backoff skipped, job duration.

## Escalation Paths
- Tier 1 (auto): retry job handles.
- Tier 2 (warning): >24h or >50 stuck → Platform/SRE investigates.
- Tier 3 (critical): max retries exceeded → Service team within 1h.
- Tier 4: >1000 failures or >7 days → engineering lead coordinates incident.

## Operational Procedures
- Query stuck docs via MongoDB or Prometheus/Grafana.
- Manual retry: `docker compose run --rm retry-job` or `scripts/manage_failed_queues.py requeue`.
- Purge or reset attempt counters based on investigation.
- Testing patterns: integration/backoff/max-retries scenarios.

## Service Integration
Services initialize attempt fields, increment before processing, set status on success, and avoid incrementing on failure (retry job handles). Ensure idempotency across parsing/chunking/embedding/summarization.

## Configuration
Key env vars: `RETRY_JOB_INTERVAL_SECONDS`, `RETRY_JOB_BASE_DELAY_SECONDS`, `RETRY_JOB_MAX_DELAY_SECONDS`, `RETRY_JOB_STUCK_THRESHOLD_HOURS`, per-collection max attempts, and Pushgateway settings.

Compose service snippet:
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
- Per-document error context
- Retry priority queue
- Dynamic backoff based on dependency health
- Scheduling retries
- Dead letter archive for analysis
- Automated root cause suggestions

## Related Docs
- [Failed queue operations](../../documents/FAILED_QUEUE_OPERATIONS.md)
- [Service monitoring](../observability/service-monitoring.md)
- [Architecture overview](../architecture/overview.md)
