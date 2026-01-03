<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Forward Progress Patterns and Recovery

How the system guarantees forward progress in the event-driven architecture: status lifecycles, idempotency, requeue logic, retry policies, and observability hooks.

## Status Field Lifecycle
### Archives
Lifecycle: `pending → completed` (or `failed`). Schema enum includes `processing` for compatibility, but services treat transitions atomically.

### Chunks (Embedding)
`embedding_generated`: `false → true`; idempotent updates.

### Design Principle
Avoid intermediate "processing" states—RabbitMQ handles in-flight messages; idempotency plus retries handles recovery.

## Idempotent Processing Patterns
- **Chunking**: catch `DuplicateKeyError`, skip duplicates, keep IDs in output; log at DEBUG.
- **Embedding**: update chunk status to `embedding_generated=True`; vectorstore deduplicates IDs.
- **General**: retries safe, requeues safe, duplicates tolerated.

## Requeue Behavior
- RabbitMQ requeues unacked messages on crash.
- Services must be idempotent; database state remains consistent on replays.

## Retry Policies (see [retry policy](retry-policy.md))
- Exponential backoff with capped delays.
- Max attempts per collection: archives/messages=3, chunks/threads=5.
- Stuck threshold: 24h with attempt count < max.

## Observability Hooks
- Metrics for retries, stuck/failed documents (Pushgateway → Prometheus → Grafana).
- Logs in Loki tied to document IDs; use Explore queries for investigation.
- Alerts: stuck documents, max retries exceeded, retry job failures.

## Implementation Guidelines
- Keep states minimal (pending/completed, booleans for flags).
- Make operations idempotent and safe under retries.
- Use schema defaults and required fields for validation.
- Emit metrics with low-cardinality labels; push on completion.
- Update status fields atomically; avoid long "processing" windows.

## References
- [Retry policy](retry-policy.md)
- [Service monitoring](../observability/service-monitoring.md)
- [Schema versioning](../schemas/schema-versioning.md)
- Schemas: `docs/schemas/documents/v1/*.schema.json`
