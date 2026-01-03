<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Failed Queue Operations Runbook

Operational procedures for managing `*.failed` queues.

## Ownership
| Queue | Owning Service | Team |
|-------|----------------|------|
| archive.ingestion.failed | Ingestion | Ingestion Team |
| parsing.failed | Parsing | Parsing Team |
| chunking.failed | Chunking | Chunking Team |
| embedding.generation.failed | Embedding | Embedding Team |
| summarization.failed | Summarization | Summarization Team |
| orchestration.failed | Orchestrator | Orchestrator Team |
| report.delivery.failed | Reporting | Reporting Team |

Platform/SRE monitors thresholds, alerts, and maintains tooling.

## Handling Strategy
- Services already retry with exponential backoff before failing.
- Messages landing in failed queues require manual action.

## Failed Event Shape
Contains original event data plus `error_message`, `error_type`, `retry_count`, `failed_at`. See `documents/schemas/events/*Failed.schema.json` for details.

## Procedures
### Monitor
- RabbitMQ UI: http://localhost:15672 → Queues → filter `.failed`.
- Grafana dashboard (if configured): message counts/rates.
- PromQL:
```promql
rabbitmq_queue_messages_ready{queue=~".*\\.failed"}
rate(rabbitmq_queue_messages_ready{queue=~".*\\.failed"}[5m])
```

### Inspect
- RabbitMQ UI: Queues → failed queue → Get messages (Requeue: No).
- CLI (recommended):
```bash
python scripts/manage_failed_queues.py inspect parsing.failed --limit 10
python scripts/manage_failed_queues.py export parsing.failed --output failed_messages.json
```

### Analyze Root Cause
- Classify transient (network/timeouts/resource) vs permanent (schema, bad data, code bug, config).
- Check logs in Loki around `failed_at`.
- Verify upstream data; reproduce locally if needed.

### Requeue
- When issue fixed/resolved:
```bash
python scripts/manage_failed_queues.py requeue parsing.failed --dry-run
python scripts/manage_failed_queues.py requeue parsing.failed
```
- RabbitMQ shovel as fallback.
- Monitor target service logs and metrics; ensure queue counts drop.

### Purge
⚠️ Irreversible—export first.
```bash
python scripts/manage_failed_queues.py export parsing.failed --output parsing_failed_backup.json
python scripts/manage_failed_queues.py purge parsing.failed --limit 100 --dry-run
python scripts/manage_failed_queues.py purge parsing.failed --limit 100 --confirm
```
UI: Queues → failed queue → Purge/Delete.

## Escalation
- Warning: 50 messages → SRE investigates, notify owning team (SLA 4 business hours).
- Critical: 200 messages → page owning team (SLA 1 hour); escalate to lead if unresolved in 4 hours.
- Emergency: 1000+ messages → incident, cross-team response.

## References
- Retry policy: [docs/operations/retry-policy.md](../retry-policy.md)
- Service monitoring: [docs/observability/service-monitoring.md](../../observability/service-monitoring.md)
- Failed queue schemas: `documents/schemas/events/*Failed.schema.json`
