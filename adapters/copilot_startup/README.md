# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Copilot Startup Utilities

This adapter provides utilities for service startup behaviors, including requeuing incomplete documents on service startup.

## Overview

The `copilot_startup` adapter enables services to scan for incomplete documents during startup and requeue them for processing. This ensures forward progress after service restarts, crashes, or partial failures.

## Features

- **StartupRequeue**: Scan document store for incomplete items and emit requeue events
- **Configurable Queries**: Customize query criteria per service
- **Observability**: Logging and metrics for requeue operations
- **Idempotent**: Safe to run multiple times without duplication

## Usage

```python
from copilot_startup import StartupRequeue
from copilot_storage import DocumentStore
from copilot_events import EventPublisher
from copilot_metrics import MetricsCollector

# Initialize requeue utility
requeue = StartupRequeue(
    document_store=document_store,
    publisher=publisher,
    metrics_collector=metrics_collector,
)

# Requeue incomplete archives
requeue.requeue_incomplete(
    collection="archives",
    query={"status": {"$in": ["pending", "processing"]}},
    event_type="ArchiveIngested",
    routing_key="archive.ingested",
    id_field="archive_id",
    build_event_data=lambda doc: {
        "archive_id": doc["archive_id"],
        "file_path": doc.get("file_path"),
        "source": doc.get("source"),
        "message_count": doc.get("message_count", 0),
    }
)
```

## Design Decisions

This startup requeue functionality complements the existing `retry-job` service:

- **Retry Job**: Runs periodically (every 15 minutes) to handle stuck documents with exponential backoff
- **Startup Requeue**: Runs once on service startup to handle documents that were in-flight during crash/restart

Both mechanisms work together to ensure forward progress without duplication.

## References

- [FORWARD_PROGRESS.md](../../documents/FORWARD_PROGRESS.md) - Idempotency and retry patterns
- [RETRY_POLICY.md](../../documents/RETRY_POLICY.md) - Retry job configuration
