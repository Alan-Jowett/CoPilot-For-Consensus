<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Cascade Cleanup on Source Deletion

## Overview

When a source is deleted with cascade semantics (`cascade=true`), the system performs distributed cleanup across all services and storage backends to completely remove all traces of data derived from that source.

## Event-Driven Cleanup Flow

The cascade cleanup is implemented using an event-driven architecture:

### 1. Deletion Initiated (Ingestion Service)

When `DELETE /api/sources/{source_name}?cascade=true` is called:

1. Ingestion service queries for all archives associated with the source
2. Publishes `SourceDeletionRequested` event containing:
   - `source_name`: Name of the source being deleted
   - `correlation_id`: Unique identifier for tracking this cleanup operation
   - `archive_ids`: List of archive IDs (accelerates downstream cleanup)
   - `delete_mode`: Currently only "hard" is supported
   - `requested_at`: Timestamp of deletion request

3. Ingestion service performs its local cleanup:
   - Deletes archives from document store and archive store
   - Publishes `SourceCleanupProgress` event with status "completed"
   
   **Note**: The ingestion service's current `delete_source_cascade()` method also deletes threads, messages, chunks, and summaries as a legacy synchronous operation. This provides backward compatibility and ensures cleanup happens even if other services are unavailable. The distributed event-driven handlers in parsing, chunking, embedding, and reporting services provide additional resilience and will skip already-deleted data (idempotent behavior).

4. Deletes the source record itself

### 2. Distributed Cleanup (Other Services)

Each service subscribes to `SourceDeletionRequested` events and handles cleanup of its own data:

#### Parsing Service
- Subscribes to: `source.deletion.requested`
- Deletes: Parsing-owned metadata for threads, messages, and archives
- Publishes: `SourceCleanupProgress` event

#### Chunking Service
- Subscribes to: `source.deletion.requested`
- Deletes: Chunks by `source_name` and/or `archive_id`
- Publishes: `SourceCleanupProgress` event

#### Embedding Service
- Subscribes to: `source.deletion.requested`
- Deletes: Embeddings/vectors from vectorstore by `source_name` and/or `archive_id`
- Publishes: `SourceCleanupProgress` event

#### Orchestrator/Reporting Service
- Subscribes to: `source.deletion.requested`
- Deletes: Derived reports and summaries
- Aggregates progress from all services (future enhancement)
- Publishes: `SourceCleanupCompleted` event with overall status (future enhancement)

**Note**: Aggregation logic is not yet implemented. Currently, the reporting service subscribes to `SourceDeletionRequested` events to delete its own summaries. It does not yet aggregate progress events or publish SourceCleanupCompleted. This is planned for a future enhancement.

#### Aggregation Logic (Future Enhancement)

When implemented, the orchestrator/reporting service will:

- Subscribe to `SourceCleanupProgress` events on the `copilot.events` exchange
- Group all progress events by `correlation_id` (one correlation per cascade cleanup operation)
- Maintain a record for each active cleanup that tracks:
  - Expected services (e.g., `["ingestion", "parsing", "chunking", "embedding", "reporting"]`)
  - Per-service deletion counts and status (`in_progress`, `completed`, or `failed`)
  - Running aggregate `total_deletion_counts` across all services
- Update the aggregate record when new `SourceCleanupProgress` events arrive:
  - Increment deletion counters by the deltas in the event
  - Mark the emitting service as `completed` or `failed` based on event payload
- Determine when cleanup is finished (all services completed/failed or timeout reached)
- Publish `SourceCleanupCompleted` event with:
  - `source_name` and `correlation_id` from original request
  - `completed_at` timestamp
  - `total_deletion_counts` aggregated across services
  - `services_completed` list of successful services
  - `services_failed` list of failed services
  - `overall_status`: `"success"`, `"partial_success"`, or `"failed"`

## Event Schemas

### SourceDeletionRequested

Published by: Ingestion Service  
Routing Key: `source.deletion.requested`  
Exchange: `copilot.events`  
Schema: `docs/schemas/events/SourceDeletionRequested.schema.json`

```json
{
  "event_type": "SourceDeletionRequested",
  "event_id": "uuid",
  "timestamp": "2025-01-18T01:00:00Z",
  "version": "1.0",
  "data": {
    "source_name": "example-source",
    "correlation_id": "uuid",
    "requested_at": "2025-01-18T01:00:00Z",
    "archive_ids": ["archive-id-1", "archive-id-2"],
    "delete_mode": "hard",
    "requested_by": "ingestion_service"
  }
}
```

### SourceCleanupProgress

Published by: All services handling cleanup  
Routing Key: `source.cleanup.progress`  
Exchange: `copilot.events`  
Schema: `docs/schemas/events/SourceCleanupProgress.schema.json`

```json
{
  "event_type": "SourceCleanupProgress",
  "event_id": "uuid",
  "timestamp": "2025-01-18T01:00:00Z",
  "version": "1.0",
  "data": {
    "source_name": "example-source",
    "correlation_id": "uuid",
    "service_name": "ingestion",
    "status": "completed",
    "deletion_counts": {
      "archives_docstore": 10,
      "archives_archivestore": 10,
      "threads": 5,
      "messages": 100,
      "chunks": 500,
      "summaries": 5
    },
    "completed_at": "2025-01-18T01:00:05Z"
  }
}
```

### SourceCleanupCompleted

Published by: Orchestrator or Reporting Service  
Routing Key: `source.cleanup.completed`  
Exchange: `copilot.events`  
Schema: `docs/schemas/events/SourceCleanupCompleted.schema.json`

```json
{
  "event_type": "SourceCleanupCompleted",
  "event_id": "uuid",
  "timestamp": "2025-01-18T01:00:10Z",
  "version": "1.0",
  "data": {
    "source_name": "example-source",
    "correlation_id": "uuid",
    "completed_at": "2025-01-18T01:00:10Z",
    "total_deletion_counts": {
      "archives": 10,
      "threads": 5,
      "messages": 100,
      "chunks": 500,
      "embeddings": 500,
      "summaries": 5
    },
    "services_completed": ["ingestion", "parsing", "chunking", "embedding", "reporting"],
    "services_failed": [],
    "overall_status": "success"
  }
}
```

## Key Design Decisions

### Idempotency
- Each handler uses `correlation_id` as the idempotency key
- Deleting already-deleted data is a no-op success
- Services rely on idempotent delete operations; they do not currently persist per-`correlation_id` completion state, so repeated events may trigger redundant but safe cleanup work
- Future enhancement: Implement correlation_id tracking to skip already-processed cleanup requests

### Partial Failure Handling
- Cleanup continues even if some operations fail
- Progress events include error summaries (non-sensitive)
- System may be left in partially deleted state on failure
- Retry the operation to clean up remaining data

### Observability
- All deletion operations record counts per collection
- Progress events enable tracking cleanup status
- Correlation ID allows tracing cleanup across services
- Metrics emitted for monitoring

### Fan-out Pattern
- All services listen to `SourceDeletionRequested` directly
- No strict dependency chain (avoids blocking on single service)
- Each service is responsible for its own data
- Services can also listen to downstream events for optimization

## Implementation Status

### Completed
- ✅ Event schemas defined
- ✅ Event models added to schema validation
- ✅ Ingestion service publishes `SourceDeletionRequested` and `SourceCleanupProgress` events
- ✅ Parsing service subscribes and implements cleanup handler
- ✅ Chunking service subscribes and implements cleanup handler
- ✅ Embedding service subscribes and implements cleanup handler
- ✅ Reporting service subscribes and implements cleanup handler
- ✅ Tests for ingestion service event publishing
- ✅ All services emit metrics and progress events

### Future Work
- ⏳ Orchestrator: Aggregate progress events and publish `SourceCleanupCompleted`
- ⏳ Add vectorstore metadata tagging for efficient deletion by source_name/archive_id
- ⏳ Implement cleanup status tracking and API endpoint
- ⏳ Add integration tests for full cascade flow
- ⏳ Add per-service tests for cleanup handlers

## Usage Example

```bash
# Delete a source with cascade cleanup
curl -X DELETE "http://localhost:8080/ingestion/api/sources/example-source?cascade=true"

# Response includes deletion counts
{
  "success": true,
  "message": "Source deleted",
  "cascade": true,
  "deletion_counts": {
    "archives_docstore": 10,
    "archives_archivestore": 10,
    "threads": 5,
    "messages": 100,
    "chunks": 500,
    "embeddings": 0,
    "summaries": 5
  }
}
```

## Monitoring

Key metrics to monitor:
- `ingestion_cascade_delete_total`: Total cascade delete operations
- `ingestion_cascade_delete_{collection}`: Deletion counts per collection
- Event publication success/failure rates
- Cleanup completion times by correlation_id

## See Also

- Issue #913: Original feature request
- `docs/schemas/events/`: Event schema definitions
- `adapters/copilot_message_bus/`: Message bus adapter
- `adapters/copilot_schema_validation/models.py`: Event dataclass definitions
