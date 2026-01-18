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
   - Deletes threads from document store
   - Deletes messages from document store
   - Deletes chunks from document store
   - Deletes summaries from document store
   - Deletes archives from document store and archive store
   - Publishes `SourceCleanupProgress` event with status "completed"

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
- Subscribes to: `source.cleanup.progress`
- Deletes: Derived reports and summaries
- Aggregates progress from all services
- Publishes: `SourceCleanupCompleted` event with overall status

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
- Services track completed cleanup operations to avoid duplicate work

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
- ✅ Tests for ingestion service event publishing

### Future Work
- ⏳ Parsing service: Subscribe and implement cleanup handler
- ⏳ Chunking service: Subscribe and implement cleanup handler
- ⏳ Embedding service: Subscribe and implement cleanup handler
- ⏳ Orchestrator/Reporting: Aggregate progress and publish completion events
- ⏳ Add vectorstore metadata tagging for efficient deletion by source_name/archive_id
- ⏳ Implement cleanup status tracking and API endpoint
- ⏳ Add integration tests for full cascade flow

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
