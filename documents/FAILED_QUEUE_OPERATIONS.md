<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Failed Queue Operations Runbook

## Overview

This document defines the operational procedures for managing failed message queues (`*.failed`) in the Copilot-for-Consensus system. Failed queues accumulate messages when services encounter errors during processing, and proper handling is critical to ensure reliability and prevent data loss.

## Ownership & Responsibilities

### Service Teams
Each microservice team owns their respective failed queue:

| Queue Name | Owning Service | Team Contact |
|-----------|----------------|--------------|
| `archive.ingestion.failed` | Ingestion Service | Ingestion Team |
| `parsing.failed` | Parsing Service | Parsing Team |
| `chunking.failed` | Chunking Service | Chunking Team |
| `embedding.generation.failed` | Embedding Service | Embedding Team |
| `summarization.failed` | Summarization Service | Summarization Team |
| `orchestration.failed` | Orchestrator Service | Orchestrator Team |
| `report.delivery.failed` | Reporting Service | Reporting Team |

### Platform/SRE Team
The Platform/SRE team is responsible for:
- Monitoring all failed queues for buildup
- Alerting service teams when thresholds are exceeded
- Providing tools and infrastructure for queue management
- Escalating persistent issues to service teams
- Maintaining this runbook and related tooling

## Failed Message Handling Strategy

### Automatic Retry Policy

**Current Implementation:** Services perform in-process retries with exponential backoff before publishing to failed queues. Once a message reaches a `*.failed` queue, it requires manual intervention.

**Retry Counts:**
- Most services: 3 retries with exponential backoff (5s, 10s, 20s, capped at 60s)
- Check service-specific configuration for exact values

### Failed Message Schema

All failed events include:
- Original event data (archive_id, chunk_ids, etc.)
- `error_message`: Human-readable error description
- `error_type`: Error classification (e.g., `IOError`, `ValidationError`)
- `retry_count`: Number of retry attempts before failure
- `failed_at`: ISO 8601 timestamp of failure

See event schemas in `documents/schemas/events/*Failed.schema.json` for exact formats.

## Operational Procedures

### 1. Monitoring Failed Queues

#### Via RabbitMQ Management UI
1. Navigate to http://localhost:15672 (default: guest/guest)
2. Click **Queues** tab
3. Filter by `.failed` to view all failure queues
4. Check **Ready** column for message count

#### Via Grafana Dashboard
1. Navigate to http://localhost:3000
2. Select **Failed Queues Dashboard** (if configured)
3. View metrics:
   - Message count per failed queue
   - Message ingestion rate
   - Time since last message

#### Via Prometheus Queries
```promql
# Total messages in failed queues
rabbitmq_queue_messages_ready{queue=~".*\\.failed"}

# Failed queue message rate (messages/sec)
rate(rabbitmq_queue_messages_ready{queue=~".*\\.failed"}[5m])
```

### 2. Inspecting Failed Messages

#### Using RabbitMQ Management UI
1. Go to http://localhost:15672 → **Queues**
2. Click on the failed queue (e.g., `parsing.failed`)
3. Expand **Get messages** section
4. Set **Messages** count (e.g., 10) and **Requeue: No**
5. Click **Get Message(s)**
6. Review message payload, headers, and error details

#### Using CLI Tool (Recommended)
```bash
# Inspect first 10 messages in parsing.failed queue
python scripts/manage_failed_queues.py inspect parsing.failed --limit 10

# Export messages to JSON for analysis
python scripts/manage_failed_queues.py export parsing.failed --output failed_messages.json
```

### 3. Analyzing Failure Root Causes

#### Common Failure Patterns

**Transient Errors** (safe to retry):
- Network timeouts connecting to dependencies (MongoDB, Qdrant, Ollama)
- Temporary resource exhaustion (memory, disk)
- Rate limiting from external APIs

**Permanent Errors** (require fixes):
- Schema validation failures (malformed events)
- Missing or corrupted source data
- Bug in service logic (exceptions, assertion failures)
- Configuration errors (invalid credentials, wrong endpoints)

#### Investigation Steps
1. **Check error_type**: Categorize as transient vs. permanent
2. **Review service logs**: Query Loki for context around `failed_at` timestamp
   ```
   {container="parsing"} |= "archive_id_here" 
   ```
3. **Check upstream data**: Verify source data integrity (archives, chunks, etc.)
4. **Reproduce locally**: Use message payload to replay processing
5. **Correlate with incidents**: Check Grafana/Prometheus for service outages

### 4. Requeuing Failed Messages

#### When to Requeue
- Transient errors have been resolved (network restored, dependency healthy)
- Service bug has been fixed and deployed
- Configuration issues corrected
- Resource constraints addressed

#### Requeue Process

**Via CLI Tool (Recommended):**
```bash
# Requeue all messages in parsing.failed
python scripts/manage_failed_queues.py requeue parsing.failed

# Requeue with dry-run first (recommended)
python scripts/manage_failed_queues.py requeue parsing.failed --dry-run

# Requeue after confirmation
python scripts/manage_failed_queues.py requeue parsing.failed
```

**Manual Requeue (RabbitMQ Shovel):**
1. Navigate to RabbitMQ Management UI → **Admin** → **Shovel Management**
2. Create new shovel:
   - Source: `parsing.failed` queue
   - Destination: `archive.ingested` queue (original trigger)
   - **Note:** Adjust destination based on event type
3. Start shovel to move messages
4. Monitor processing in target service
5. Delete shovel after completion

#### Post-Requeue Monitoring
- Watch target service logs for processing
- Monitor success/failure rates in Grafana
- Verify failed queue count decreases
- Check for re-failures (indicates issue not resolved)

### 5. Purging Failed Messages

#### When to Purge
- Messages are beyond retention policy (e.g., >30 days old)
- Data is no longer relevant (obsolete archives)
- Permanent errors cannot be fixed (corrupted source data)
- After confirming data loss is acceptable

#### Purge Process

**⚠️ WARNING: Purging is irreversible. Always export messages first.**

```bash
# Export messages for backup
python scripts/manage_failed_queues.py export parsing.failed \
  --output parsing_failed_backup_$(date +%Y%m%d).json

# Purge with dry-run first (safer)
python scripts/manage_failed_queues.py purge parsing.failed \
  --limit 100 \
  --dry-run

# Purge after confirmation
python scripts/manage_failed_queues.py purge parsing.failed \
  --limit 100 \
  --confirm

# Purge entire queue (omit --limit to purge all messages)
python scripts/manage_failed_queues.py purge parsing.failed --confirm
```

**Via RabbitMQ Management UI:**
1. Navigate to http://localhost:15672 → **Queues**
2. Click on failed queue
3. Click **Purge** or **Delete** (removes queue and messages)
4. Confirm action

### 6. Escalation Procedures

#### Threshold-Based Escalation

**Warning Threshold:** 50 messages in any failed queue
- Action: SRE team investigates and notifies service team
- SLA: Investigation within 4 business hours

**Critical Threshold:** 200 messages in any failed queue
- Action: Page on-call engineer for owning service
- SLA: Response within 1 hour
- Escalation: If unresolved in 4 hours, escalate to engineering lead

**Emergency Threshold:** 1000+ messages
- Action: Incident declared, all-hands investigation
- Impact: Pipeline degradation, potential data loss
- Response: Immediate triage, consider disabling affected service

#### Communication Template
```
Subject: [ALERT] Failed Queue Threshold Exceeded: <queue_name>

Queue: <queue_name>
Current Count: <count>
Threshold: <threshold>
Time Detected: <timestamp>
Recent Error Types: <top_3_error_types>

Grafana: <link_to_dashboard>
Logs: <link_to_loki_query>

Next Steps:
1. Review recent deployments/changes to <service>
2. Inspect failed messages: python scripts/manage_failed_queues.py inspect <queue>
3. Check service health: docker compose logs <service>
4. Correlate with incidents in Grafana
```

## Monitoring & Alerting

### Prometheus Alerts

Alerts are defined in `infra/prometheus/alerts/failed_queues.yml`:

- **FailedQueueWarning**: >50 messages for 15 minutes
- **FailedQueueCritical**: >200 messages for 5 minutes
- **FailedQueueStagnant**: No change in count for 24 hours (indicates no processing)

### Grafana Dashboards

**Failed Queues Overview Dashboard** includes:
- Message count per queue (timeseries)
- Failed message ingestion rate
- Top error types (breakdown by error_type field)
- Time since last failure per queue
- Alert status indicators

Access: http://localhost:3000 → **Dashboards** → **Failed Queues**

### Log Queries (Loki)

```logql
# All failed event publications
{container=~"parsing|chunking|embedding|summarization"} |= "Failed event"

# Failed messages by error type
{container="parsing"} | json | error_type="NetworkTimeout"

# Failed messages in time range
{container="embedding"} 
  |= "EmbeddingGenerationFailed" 
  | json 
  | line_format "{{.failed_at}} {{.error_message}}"
```

## Retention & Data Governance

### Message Retention Policy
- **Failed queues:** Messages retained for **30 days** (configurable)
- **Exported backups:** Retained for **90 days** in blob storage
- **Metrics/logs:** Per Prometheus/Loki retention settings (default: 15 days)

### Compliance & Auditing
- All purge operations logged to audit trail
- Exported message backups tagged with operator, timestamp, reason
- Monthly reports on failed message statistics (count, categories, resolution rate)

## Tools & Scripts

### Queue Management CLI

Location: `scripts/manage_failed_queues.py`

**Installation:**
```bash
pip install -r scripts/requirements.txt
```

**Usage:**
```bash
# Show help
python scripts/manage_failed_queues.py --help

# List all failed queues
python scripts/manage_failed_queues.py list

# Inspect messages
python scripts/manage_failed_queues.py inspect <queue> [--limit N]

# Export messages
python scripts/manage_failed_queues.py export <queue> --output <file.json>

# Requeue messages
python scripts/manage_failed_queues.py requeue <queue> [--dry-run]

# Purge messages
python scripts/manage_failed_queues.py purge <queue> [--limit N] [--confirm]
```

**Configuration:**
Set environment variables or use `--rabbitmq-host`, `--rabbitmq-port`, `--rabbitmq-user`, `--rabbitmq-password` flags.

## Best Practices

### Do's ✅
- **Export before purging**: Always back up messages before deletion
- **Use dry-run**: Test requeue/purge operations with `--dry-run` first
- **Filter wisely**: Use filters to target specific error types or time ranges
- **Monitor post-requeue**: Verify messages process successfully after requeue
- **Document decisions**: Record reasons for purging in audit logs
- **Review regularly**: Weekly review of failed queue trends

### Don'ts ❌
- **Don't ignore alerts**: Escalate when thresholds are exceeded
- **Don't mass-purge blindly**: Analyze failure patterns before purging
- **Don't requeue without fixing**: Ensure root cause is resolved
- **Don't skip backups**: Message data may be irrecoverable
- **Don't bypass tooling**: Use CLI tool instead of manual queue manipulation
- **Don't delete queues**: Purge messages, but keep queue definitions

## Troubleshooting

### Failed Queue Not Draining After Requeue
**Symptoms:** Messages requeued but not processing
**Causes:**
- Target queue consumers not running
- Service still experiencing same error
- Message schema incompatible with consumer
**Resolution:**
1. Check consumer health: `docker compose ps <service>`
2. Review service logs for errors
3. Verify message schema matches consumer expectations
4. Consider reverting recent changes if persistent

### High Failure Rate After Deployment
**Symptoms:** Failed queue grows rapidly after service update
**Causes:**
- Introduced bug in new code
- Configuration change broke dependency
- Schema migration incompatibility
**Resolution:**
1. Rollback deployment if critical
2. Review deployment changes and logs
3. Test with single message before mass requeue
4. Fix issue and redeploy before requeuing

### Messages Stuck in Failed Queue Forever
**Symptoms:** Old messages never processed or purged
**Causes:**
- Forgotten alerts disabled
- No operational process followed
- Ownership unclear
**Resolution:**
1. Review this runbook
2. Enable/fix alerting
3. Assign ownership per table above
4. Establish regular review cadence

## Related Documentation

- [SERVICE_MONITORING.md](./SERVICE_MONITORING.md) - General monitoring guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [SCHEMA.md](./SCHEMA.md) - Event schema definitions
- [TESTING_MESSAGE_BUS.md](./TESTING_MESSAGE_BUS.md) - Message bus testing

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-13 | GitHub Copilot | Initial runbook creation |
