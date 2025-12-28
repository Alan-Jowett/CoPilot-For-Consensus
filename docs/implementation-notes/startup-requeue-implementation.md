# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Startup Requeue Implementation Summary

## Overview

This document summarizes the implementation of startup requeue logic for incomplete documents across all processing services. This feature ensures forward progress after service crashes or restarts by automatically requeuing incomplete work on startup.

## Implementation Details

### New Adapter: `copilot_startup`

Created a new adapter module `copilot_startup` that provides:

- **`StartupRequeue` utility class**: Reusable component for scanning and requeuing incomplete documents
- **Configurable queries**: Supports custom MongoDB queries per service
- **Event publishing**: Publishes appropriate events to the message bus
- **Observability**: Comprehensive logging and metrics
- **Error handling**: Graceful failure handling that doesn't crash services

### Service-Specific Implementations

#### 1. Parsing Service
- **Query**: Archives with `status` in `["pending", "processing"]`
- **Event**: `ArchiveIngested`
- **Limit**: 1000 archives
- **Logic**: Simple status-based query

#### 2. Chunking Service
- **Query**: Messages without corresponding chunks
- **Event**: `JSONParsed`
- **Logic**:
  - Queries all messages
  - Checks for existing chunks
  - Identifies messages without chunks
  - Groups by archive for efficient requeue

#### 3. Embedding Service
- **Query**: Chunks with `embedding_generated: false`
- **Event**: `ChunksPrepared`
- **Limit**: 1000 chunks
- **Logic**: Simple boolean flag check

#### 4. Summarization Service
- **Query**: Threads with `summary_id: null`
- **Event**: `SummarizationRequested`
- **Limit**: 500 threads
- **Logic**: Null check on summary reference

#### 5. Orchestrator Service
- **Query**: Threads without summaries that have complete embeddings
- **Event**: `SummarizationRequested`
- **Limit**: 500 threads
- **Logic**:
  - Queries threads without summaries
  - For each thread, verifies all chunks have embeddings
  - Only requeues threads ready for summarization

### Configuration

All services support disabling startup requeue via:
```python
service.start(enable_startup_requeue=False)
```

Default: `enable_startup_requeue=True`

### Observability

#### Metrics
- `startup_requeue_documents_total` (Counter): Total documents requeued, labeled by collection
- `startup_requeue_errors_total` (Counter): Errors during requeue, labeled by collection and error_type

#### Logging
- INFO: Requeue summary (count of documents requeued)
- DEBUG: Individual document requeue actions
- ERROR: Failures during requeue (non-fatal)

### Testing

Created comprehensive unit tests for `StartupRequeue` utility:
1. `test_requeue_incomplete_archives` - Verifies successful requeue
2. `test_requeue_incomplete_chunks` - Tests chunk requeue
3. `test_requeue_no_incomplete_documents` - Handles empty results
4. `test_requeue_handles_individual_failures` - Continues on partial failures
5. `test_requeue_with_limit` - Respects limit parameter
6. `test_requeue_emits_error_metrics_on_failure` - Error metric emission

All tests passing ✅

### Docker Integration

Updated all service Dockerfiles to install `copilot_startup` adapter:
- parsing/Dockerfile
- chunking/Dockerfile
- embedding/Dockerfile
- summarization/Dockerfile
- orchestrator/Dockerfile

### Documentation

Updated documentation:
- **FORWARD_PROGRESS.md**: Changed design decision to reflect new startup behavior
- **parsing/README.md**: Added "Startup Requeue" section
- **embedding/README.md**: Added "Startup Requeue" section
- **adapters/copilot_startup/README.md**: Complete adapter documentation

## Design Decisions

### 1. Complement, Don't Replace Retry Job

The startup requeue mechanism works alongside the existing periodic retry job:
- **Startup Requeue**: Runs once on service startup for immediate recovery
- **Retry Job**: Runs periodically (every 15 minutes) with exponential backoff
- Both mechanisms are idempotent and safe to run concurrently

### 2. Graceful Degradation

Startup requeue failures do NOT crash services:
- Errors are logged at ERROR level
- Metrics track failures
- Service continues normal operation
- This ensures services remain available even if requeue fails

### 3. Idempotency First

All requeue operations are idempotent:
- Requeuing the same document multiple times is safe
- Services handle duplicate events gracefully
- Follows existing idempotency patterns in the codebase

### 4. Service-Specific Logic

Each service implements custom logic appropriate to its domain:
- Parsing: Simple status check
- Chunking: Cross-collection query to find messages without chunks
- Embedding: Boolean flag check
- Summarization: Null reference check
- Orchestrator: Validates embedding completeness before requeue

## Code Quality

### Code Review Feedback Addressed

1. ✅ Improved chunking service requeue logic to properly identify messages without chunks
2. ✅ Enhanced orchestrator to verify all chunks have embeddings before requeuing threads
3. ⚠️ Minor documentation inconsistencies in summarization config (pre-existing, not introduced by this PR)

### Adherence to Standards

- Follows PEP 8 coding standards
- Includes SPDX license headers
- Comprehensive docstrings
- Type hints where appropriate
- Error handling best practices

## Impact

### Benefits
1. **Improved Resilience**: Services recover automatically from crashes
2. **Faster Recovery**: Immediate requeue on startup vs waiting for retry job
3. **Observability**: Clear metrics and logging for monitoring
4. **Flexibility**: Can be disabled per service if needed

### Risks
1. **Startup Time**: May increase service startup time when many incomplete documents exist
2. **Resource Usage**: Query load on document store during startup
3. **Message Bus Load**: Burst of events published at startup

### Mitigation
- Configurable limits prevent unbounded queries
- Graceful error handling prevents cascading failures
- Services remain responsive during requeue
- Metrics enable monitoring and tuning

## Future Enhancements

Potential improvements for future work:
1. Configurable query limits via environment variables
2. Prioritization logic (e.g., requeue recent documents first)
3. Rate limiting for event publishing
4. Dashboard for startup requeue metrics
5. Integration tests for end-to-end requeue flow

## References

- Issue: [Implement requeue-on-startup logic for incomplete documents]
- Documentation: [FORWARD_PROGRESS.md](../../documents/FORWARD_PROGRESS.md)
- Retry Policy: [RETRY_POLICY.md](../../documents/RETRY_POLICY.md)
- Service Monitoring: [SERVICE_MONITORING.md](../../documents/SERVICE_MONITORING.md)
