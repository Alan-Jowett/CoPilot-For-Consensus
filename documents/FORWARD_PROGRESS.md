<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Forward Progress Patterns and Recovery

## Overview

This document describes how the Copilot-for-Consensus system guarantees forward progress in its event-driven architecture. It covers status field lifecycles, idempotency patterns, requeue logic, retry policies, and observability hooks. Understanding these patterns is critical for implementing reliable microservices and ensuring consistent behavior across the system.

## Table of Contents

- [Status Field Lifecycle](#status-field-lifecycle)
- [Idempotent Processing](#idempotent-processing)
- [Requeue Behavior](#requeue-behavior)
- [Retry Policies](#retry-policies)
- [Observability Hooks](#observability-hooks)
- [Implementation Guidelines](#implementation-guidelines)
- [References](#references)

## Status Field Lifecycle

### Archives Collection Status

The `archives` collection uses a `status` field to track processing state:

**Lifecycle:**
```
pending → processed
        ↘ failed
```

**States:**
- **`pending`**: Archive ingested, awaiting parsing
- **`processed`**: Successfully parsed (all messages extracted)
- **`failed`**: Parsing failed after retries

**Schema:** See [`documents/schemas/documents/archives.schema.json`](./schemas/documents/archives.schema.json)

```json
{
  "status": {
    "type": "string",
    "enum": ["pending", "processed", "failed"]
  }
}
```

**Setting the Status:**
- **Ingestion Service** sets `status: "pending"` when creating archive documents
- **Parsing Service** updates to `"processed"` or `"failed"` based on outcome
- No intermediate `"processing"` state - transitions are atomic

**Example from Ingestion Service:**
```python
# ingestion/app/service.py
archive_doc = {
    "archive_id": archive_id,
    "file_hash": file_hash,
    "source": source,
    "ingestion_date": datetime.now(timezone.utc).isoformat(),
    "status": "pending",  # Initial state
    # ... other fields
}
self.document_store.insert_document("archives", archive_doc)
```

### Chunks Collection Embedding Status

The `chunks` collection uses `embedding_generated` to track embedding state:

**Lifecycle:**
```
embedding_generated: false → true
```

**Schema:** See [`documents/schemas/documents/chunks.schema.json`](./schemas/documents/chunks.schema.json)

```json
{
  "embedding_generated": {
    "type": "boolean"
  }
}
```

**Setting the Status:**
- **Chunking Service** sets `embedding_generated: false` when creating chunks
- **Embedding Service** updates to `true` after successful embedding generation

**Example from Embedding Service:**
```python
# embedding/app/service.py
def _update_chunk_status_by_doc_ids(self, doc_ids: List[str]):
    """Update chunk embedding status after successful generation."""
    for doc_id in doc_ids:
        self.document_store.update_document(
            collection="chunks",
            doc_id=doc_id,
            patch={"embedding_generated": True},
        )
```

**Why a Boolean Instead of an Enum?**
- Simpler: only two states needed
- Clear intent: either embedded or not
- Idempotent: setting `true` multiple times is safe

### No Intermediate "Processing" States

**Design Principle:** Services do not use intermediate "processing" states like `"processing"` or `"in_progress"`.

**Rationale:**
1. **Crash Safety**: If a service crashes mid-processing, a "processing" state would require startup cleanup logic
2. **Simplicity**: Binary states (pending/completed or true/false) are easier to reason about
3. **Idempotency**: Retry logic works cleanly without needing to detect and recover from "stuck" processing states
4. **Message Queue Responsibility**: RabbitMQ manages in-flight messages; the database doesn't need to track them

**Recovery Pattern:**
- If a service crashes, RabbitMQ requeues unacknowledged messages
- On restart, services process the requeued messages
- Idempotency ensures duplicate processing is safe

## Idempotent Processing

All services MUST be idempotent - processing the same input multiple times must produce the same result without errors or side effects.

### Why Idempotency Matters

- **Retry Safety**: Services can retry failed operations without data corruption
- **Crash Recovery**: Requeued messages after crashes don't cause duplicate data
- **Operational Flexibility**: Operators can manually requeue failed messages
- **Testing**: Makes integration tests deterministic and repeatable

### Idempotency Patterns by Service

#### Chunking Service: DuplicateKeyError Handling

**Pattern:** Catch `DuplicateKeyError` on insert, log at DEBUG level, continue processing

**Implementation:**
```python
# chunking/app/service.py
from pymongo.errors import DuplicateKeyError

for chunk in all_chunks:
    try:
        self.document_store.insert_document("chunks", chunk)
        chunk_ids.append(chunk["chunk_id"])
    except DuplicateKeyError:
        # Chunk already exists (idempotent retry)
        logger.debug(f"Chunk {chunk.get('chunk_id', 'unknown')} already exists, skipping")
        chunk_ids.append(chunk.get("chunk_id", "unknown"))  # Still include in output
        skipped_duplicates += 1
    except Exception as e:
        # Other errors (transient) should fail the processing
        logger.error(f"Error storing chunk {chunk.get('chunk_id')}: {e}")
        raise
```

**Key Points:**
- Duplicate chunks are **skipped**, not treated as errors
- Chunk IDs are **still included** in the output event
- **Only** DuplicateKeyError is caught; other exceptions re-raise for retry
- Logs at **DEBUG** level to avoid noise during normal retry operations

**Testing Idempotency:** Verify by processing the same event twice and ensuring no errors or duplicate data. See the implementation at `chunking/tests/test_service.py::test_idempotent_chunk_insertion` as an example.

#### Embedding Service: Status Field Updates

**Pattern:** Update chunk status fields to track embedding generation; vectorstore prevents duplicates

**Implementation:**
```python
# embedding/app/service.py
# After generating embeddings, update chunk status
def _update_chunk_status_by_doc_ids(self, doc_ids: List[str]):
    """Update chunk embedding status after successful generation."""
    for doc_id in doc_ids:
        self.document_store.update_document(
            collection="chunks",
            doc_id=doc_id,
            patch={"embedding_generated": True},
        )
```

**Vectorstore Interface:**
```python
# adapters/copilot_vectorstore/copilot_vectorstore/interface.py
def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]):
    """Add a single embedding to the vector store.
    
    Raises:
        ValueError: If id already exists or vector is invalid
    """
    
def add_embeddings(self, ids: List[str], vectors: List[List[float]], metadatas: List[Dict[str, Any]]):
    """Add multiple embeddings in batch.
    
    Raises:
        ValueError: If lengths don't match or any id already exists
    """
```

**Key Points:**
- Vectorstore implementations (Qdrant) **raise ValueError** if ID already exists
- Embedding service relies on **`embedding_generated` status field** to prevent reprocessing
- Chunks with `embedding_generated: true` are skipped in queries
- Idempotency achieved through status field, not vectorstore upsert

**Testing Idempotency:** The embedding service queries only chunks with `embedding_generated: false`, preventing duplicate embedding generation attempts.

#### Parsing Service: Message Key Uniqueness

**Pattern:** Use deterministic message keys; MongoDB unique index prevents duplicates

**Implementation:**
```python
# parsing/app/service.py
message_doc = {
    "message_key": message_key,  # Deterministic hash of Message-ID
    "message_id": message_id,
    # ... other fields
}
# Unique index on message_key prevents duplicates
self.document_store.insert_document("messages", message_doc)
```

**Schema:** Messages collection has unique index on `message_key`

**Key Points:**
- `message_key` is a **deterministic hash** of the email `Message-ID` header
- MongoDB unique index ensures duplicates are rejected
- Parsing service **does not catch** DuplicateKeyError (intentional - indicates data issue)

### Recommended Pattern: Check Before Processing

**Note:** This pattern is recommended but not yet implemented in all services. It's useful for expensive operations like LLM calls.

**Pattern:** Query for existing result before generating a new one (read-before-write)

**Example Implementation:**
```python
def _generate_thread_summary(self, thread_id: str, chunks: List[Dict[str, Any]]):
    # Check if summary already exists
    existing = self.document_store.query_documents(
        collection="summaries",
        query={"thread_id": thread_id},
        limit=1
    )
    
    if existing:
        logger.info(f"Summary for thread {thread_id} already exists, skipping generation")
        return existing[0]
    
    # Generate new summary
    summary = self.summarizer.summarize(chunks)
    # ... store summary
```

**Key Points:**
- **Read-before-write** pattern prevents duplicate work
- Returns existing result if found (idempotent result)
- Useful for expensive operations (LLM calls)
- **Recommended** for future implementations of summarization and orchestration services

### Testing Idempotency

**All services MUST include idempotency tests:**

```python
def test_idempotent_processing(service, mock_store):
    """Verify processing same input twice succeeds without errors."""
    
    # Process once
    service.process_event(test_event)
    
    # Process again - should succeed without errors
    service.process_event(test_event)
    
    # Verify output is consistent (same data, not duplicated)
    results = mock_store.query_documents("output_collection")
    assert len(results) == expected_count  # Not doubled
```

**Test Pattern:** Process → Process again → Verify no errors and no duplicates

## Requeue Behavior

Services use RabbitMQ's **nack with requeue** mechanism for transient failures.

### When to Requeue

**Requeue (nack with requeue=True):**
- Database temporarily unavailable
- Network timeouts
- Vectorstore connection errors
- Any transient infrastructure failure

**Do NOT Requeue (ack or nack with requeue=False):**
- Malformed event data (JSONDecodeError)
- Schema validation failures
- Business logic errors (invalid state transitions)
- Any permanent error that won't be fixed by retry

### Exception Re-raising Pattern

**Pattern:** Event handlers re-raise exceptions to trigger RabbitMQ nack

**Implementation:**
```python
# All services follow this pattern
def _handle_event(self, event: Dict[str, Any]):
    """Handle event from message queue.
    
    This is an event handler for message queue consumption. Exceptions are
    logged and re-raised to allow message requeue for transient failures
    (e.g., database unavailable). Only exceptions due to bad event data
    should be caught and not re-raised.
    
    Args:
        event: Event dictionary
    """
    try:
        # Parse and validate event
        parsed_event = EventClass(data=event.get("data", {}))
        
        # Process the event
        self.process_data(parsed_event.data)
        
    except Exception as e:
        logger.error(f"Error handling event: {e}", exc_info=True)
        if self.error_reporter:
            self.error_reporter.report(e, context={"event": event})
        
        # Re-raise to trigger message requeue for transient failures
        raise
```

**Key Points:**
- **Always re-raise** unless the error is permanent (bad data)
- **Log before re-raising** for observability
- **Report to error tracker** for alerting
- RabbitMQ subscriber catches the exception and nacks the message

### RabbitMQ Subscriber Implementation

**Implementation:**
```python
# adapters/copilot_events/copilot_events/rabbitmq_subscriber.py
def _on_message(self, channel, method, properties, body):
    try:
        event = json.loads(body.decode('utf-8'))
        callback = self.callbacks.get(event.get('event_type'))
        
        if callback:
            try:
                callback(event)
                # Success - acknowledge message
                if not self.auto_ack:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
                # Callback failed - requeue for retry
                if not self.auto_ack:
                    channel.basic_nack(
                        delivery_tag=method.delivery_tag,
                        requeue=True  # Re-deliver to same queue
                    )
                return
                
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON: {e}")
        # Malformed message - ack to remove from queue
        if not self.auto_ack:
            channel.basic_ack(delivery_tag=method.delivery_tag)
```

**Flow:**
1. Deserialize message
2. Call registered callback
3. **If callback raises exception**: nack with `requeue=True`
4. **If JSON is malformed**: ack to prevent infinite loop
5. **If callback succeeds**: ack to remove from queue

### Startup Behavior: No Automatic Requeue

**Important:** Services do NOT automatically requeue pending work on startup.

**Rationale:**
- **Message Queue Owns State**: RabbitMQ maintains in-flight messages
- **No Database Polling**: Services don't scan for "pending" records
- **Crash Recovery**: Unacknowledged messages are automatically redelivered by RabbitMQ
- **Simplicity**: Avoids complex startup logic and race conditions

**Recovery Pattern:**
1. Service crashes while processing message
2. RabbitMQ detects connection loss
3. RabbitMQ requeues unacknowledged message
4. Service restarts and reconnects
5. Service receives requeued message
6. Idempotency ensures safe retry

**Manual Requeue:** Operators can manually requeue failed messages using `scripts/manage_failed_queues.py`

## Retry Policies

Services implement **in-process retry with exponential backoff** before giving up.

### Retry Configuration

**Common Parameters:**
- `max_retries`: Maximum retry attempts (default: 3)
- `retry_backoff_seconds`: Initial backoff delay (default: 5 seconds)
- **Backoff Strategy:** Exponential with cap at 60 seconds

**Configuration Sources:**
- Environment variables (production)
- Service configuration schemas in `documents/schemas/configs/`
- Test fixtures (unit tests)

### Retry Implementation Pattern

**Standard Pattern:**
```python
retry_count = 0
while retry_count < self.max_retries:
    try:
        # Attempt operation
        result = self._do_work(data)
        
        # Success - publish event and return
        self._publish_success_event(result)
        return
        
    except Exception as e:
        retry_count += 1
        error_msg = str(e)
        error_type = type(e).__name__
        
        logger.error(
            f"Operation failed (attempt {retry_count}/{self.max_retries}): {error_msg}",
            exc_info=True
        )
        
        if retry_count >= self.max_retries:
            # Max retries exceeded - publish failure event and re-raise
            self._publish_failure_event(data, error_msg, error_type, retry_count)
            
            if self.error_reporter:
                self.error_reporter.report(e, context={"data": data, "retry_count": retry_count})
            
            if self.metrics_collector:
                self.metrics_collector.increment("failures_total", 1, tags={"error_type": error_type})
            
            # Re-raise to trigger message requeue
            raise
        else:
            # Exponential backoff with cap
            backoff_time = self.retry_backoff_seconds * (2 ** (retry_count - 1))
            capped_backoff_time = min(backoff_time, 60)
            logger.info(f"Retrying in {capped_backoff_time} seconds...")
            time.sleep(capped_backoff_time)
```

**Backoff Schedule (default: 5s initial):**
- Attempt 1: Immediate
- Attempt 2: 5 seconds (5 × 2⁰)
- Attempt 3: 10 seconds (5 × 2¹)
- Attempt 4: 20 seconds (5 × 2²)
- Capped at 60 seconds

**Example from Embedding Service:** See `embedding/app/service.py::process_chunks`

### Failed Event Publishing

**When Max Retries Exceeded:**
1. Publish `*Failed` event to message bus
2. Report error to error tracker
3. Record metric
4. **Re-raise exception** to trigger message requeue to `*.failed` queue

**Failed Event Schema Example:**
```json
{
  "event_type": "EmbeddingGenerationFailed",
  "data": {
    "chunk_ids": ["chunk-123", "chunk-456"],
    "error_message": "Connection to vectorstore timed out",
    "error_type": "TimeoutError",
    "retry_count": 3,
    "failed_at": "2024-01-15T10:30:00Z"
  }
}
```

**Failed Queue Naming:**
- Pattern: `<service>.failed`
- Examples: `parsing.failed`, `embedding.generation.failed`, `summarization.failed`

**Failed Queue Management:** See [FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md)

### Testing Retry Behavior

**Test Pattern:**
```python
def test_retry_with_exponential_backoff(service, mock_store):
    """Verify service retries with exponential backoff."""
    
    # Mock transient failures
    mock_store.insert_document.side_effect = [
        ConnectionError("DB unavailable"),  # Attempt 1
        ConnectionError("DB unavailable"),  # Attempt 2
        "success",                          # Attempt 3
    ]
    
    # Should succeed after retries
    service.process_event(test_event)
    
    # Verify retry count
    assert mock_store.insert_document.call_count == 3

def test_max_retries_exceeded_raises(service, mock_store):
    """Verify exception is raised after max retries."""
    
    # Mock persistent failure
    mock_store.insert_document.side_effect = ConnectionError("DB down")
    
    # Should raise after max_retries attempts
    with pytest.raises(ConnectionError):
        service.process_event(test_event)
    
    # Verify failure event published
    assert_failure_event_published(service.publisher)
```

## Observability Hooks

Services integrate with metrics collection, error reporting, and logging for full observability.

### Metrics Collection Points

**Standard Metrics per Service:**

```python
# Counters (use increment)
metrics_collector.increment("events_processed_total", 1)
metrics_collector.increment("failures_total", 1, tags={"error_type": "TimeoutError"})
metrics_collector.increment("chunks_created_total", chunk_count)

# Histograms/Durations (use observe)
metrics_collector.observe("processing_duration_seconds", duration)
metrics_collector.observe("chunk_size_tokens", avg_chunk_size)

# Gauges (use gauge)
metrics_collector.gauge("queue_depth", queue_size)
```

**Key Patterns:**
- **Counter**: Use for counts that only increase (`_total` suffix)
- **Histogram**: Use for distributions (durations, sizes) with `observe()`
- **Gauge**: Use for current values that can increase/decrease
- **Tags**: Add dimensions for filtering (error_type, service_name)

**Metrics Adapter:** See `adapters/copilot_metrics/copilot_metrics/metrics.py`

**Integration:**
```python
from copilot_metrics import create_metrics_collector

metrics_collector = create_metrics_collector()  # Reads METRICS_BACKEND env var

# In service code
if self.metrics_collector:
    self.metrics_collector.increment("events_processed_total", 1)
```

**Testing:** Metrics are optional; use mock or `NoOpMetricsCollector` in tests

### Error Reporting Integration

**Error Reporter Interface:**

```python
from copilot_reporting import create_error_reporter

error_reporter = create_error_reporter()  # Reads ERROR_REPORTER_TYPE env var

# In exception handler
try:
    # ... operation
except Exception as e:
    if self.error_reporter:
        self.error_reporter.report(
            e, 
            context={"event": event, "retry_count": retry_count}
        )
    raise
```

**Error Reporter Types:**
- `http`: Posts to error reporting service (default)
- `noop`: No-op for testing
- Configured via `ERROR_REPORTER_TYPE` environment variable

**Error Tracking Service:**
- HTTP endpoint: `http://localhost:8081/api/errors`
- Web UI: `http://localhost:8081/ui`
- Stores up to 10,000 recent errors in memory
- See `error-reporting/README.md`

### Logging Guidelines

**Log Levels:**
- **DEBUG**: Duplicate detection, skipped items, verbose tracing
- **INFO**: Normal operations (events processed, metrics)
- **WARNING**: Unexpected but recoverable conditions
- **ERROR**: Exceptions, failures (always with `exc_info=True`)

**Standard Pattern:**
```python
import logging

logger = logging.getLogger(__name__)

# Success path
logger.info(f"Processed {count} items in {duration:.2f}s")

# Duplicate/skip (not an error)
logger.debug(f"Chunk {chunk_id} already exists, skipping")

# Transient error (will retry)
logger.error(f"Processing failed (attempt {retry}/{max}): {error}", exc_info=True)

# Permanent error (giving up)
logger.error(f"Processing failed after {max} retries: {error}", exc_info=True)
```

**Log Aggregation:**
- **Promtail** collects Docker logs
- **Loki** aggregates and indexes logs
- **Grafana** provides log exploration UI
- See [ARCHITECTURE.md#observability-stack](./ARCHITECTURE.md#observability-stack)

### Failed Queue Monitoring

**Prometheus Queries:**
```promql
# Messages in failed queues
rabbitmq_queue_messages_ready{queue=~".*\\.failed"}

# Failed queue message rate
rate(rabbitmq_queue_messages_ready{queue=~".*\\.failed"}[5m])
```

**Grafana Dashboard:**
- Pre-configured dashboard: "Failed Queues"
- Alerts configured in `infra/prometheus/alerts/failed_queues.yml`

**CLI Tool:**
```bash
# Inspect failed messages
python scripts/manage_failed_queues.py inspect parsing.failed --limit 10

# Requeue messages after fix
python scripts/manage_failed_queues.py requeue parsing.failed --dry-run
python scripts/manage_failed_queues.py requeue parsing.failed

# Purge invalid messages
python scripts/manage_failed_queues.py purge parsing.failed --dry-run
```

**See Also:** [FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md)

## Implementation Guidelines

### Checklist for New Services

When implementing a new microservice, ensure:

**Status/State Management:**
- [ ] Use binary states (pending/completed) or boolean flags, not intermediate "processing" states
- [ ] Update status atomically after successful completion
- [ ] Define clear state transitions in schema

**Idempotency:**
- [ ] Implement idempotent processing (same input → same output, no errors)
- [ ] Use appropriate pattern: DuplicateKeyError handling, upsert, or read-before-write
- [ ] Write test: `test_idempotent_<operation>`
- [ ] Handle duplicates gracefully (log at DEBUG, not ERROR)

**Requeue Behavior:**
- [ ] Re-raise exceptions in event handlers for transient failures
- [ ] Ack malformed messages to prevent infinite loops
- [ ] Document which errors are transient vs. permanent
- [ ] Write test: `test_event_handler_reraises_for_requeue`

**Retry Policies:**
- [ ] Implement in-process retry with exponential backoff
- [ ] Configure `max_retries` and `retry_backoff_seconds`
- [ ] Publish `*Failed` event when max retries exceeded
- [ ] Re-raise after failure event to trigger message requeue
- [ ] Write test: `test_retry_with_exponential_backoff`
- [ ] Write test: `test_max_retries_exceeded_raises`

**Observability:**
- [ ] Integrate `MetricsCollector` (optional, use `if self.metrics_collector`)
- [ ] Integrate `ErrorReporter` (optional, use `if self.error_reporter`)
- [ ] Log at appropriate levels (DEBUG for skips, ERROR for exceptions)
- [ ] Always use `exc_info=True` when logging exceptions
- [ ] Define service-specific metrics (counters, histograms)

**Testing:**
- [ ] Unit tests with mocked dependencies
- [ ] Integration tests with real message bus and database
- [ ] Idempotency test (process twice, verify no errors/duplicates)
- [ ] Retry test (simulate transient failures)
- [ ] Requeue test (verify exception re-raising)

### Code Examples and Templates

**Service Template with All Patterns:**

```python
# service.py
import logging
import time
from typing import Optional, Dict, Any

from pymongo.errors import DuplicateKeyError

from copilot_events import EventPublisher, EventSubscriber
from copilot_storage import DocumentStore
from copilot_metrics import MetricsCollector
from copilot_reporting import ErrorReporter

logger = logging.getLogger(__name__)


class MyService:
    def __init__(
        self,
        document_store: DocumentStore,
        publisher: EventPublisher,
        subscriber: EventSubscriber,
        max_retries: int = 3,
        retry_backoff_seconds: int = 5,
        metrics_collector: Optional[MetricsCollector] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        self.document_store = document_store
        self.publisher = publisher
        self.subscriber = subscriber
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter

    def start(self):
        """Start the service and subscribe to events."""
        logger.info("Starting My Service")
        
        self.subscriber.subscribe(
            event_type="TriggerEvent",
            callback=self._handle_event,
            routing_key="trigger.event",
            exchange="copilot.events",
        )
        
        logger.info("My service is ready")

    def _handle_event(self, event: Dict[str, Any]):
        """Handle event from message queue.
        
        This is an event handler for message queue consumption. Exceptions are
        logged and re-raised to allow message requeue for transient failures
        (e.g., database unavailable). Only exceptions due to bad event data
        should be caught and not re-raised.
        
        Args:
            event: Event dictionary
        """
        try:
            # Parse event
            data = event.get("data", {})
            
            # Process with retry
            self._process_with_retry(data)
            
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
            if self.error_reporter:
                self.error_reporter.report(e, context={"event": event})
            
            # Re-raise to trigger message requeue
            raise

    def _process_with_retry(self, data: Dict[str, Any]):
        """Process data with retry logic."""
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                start_time = time.time()
                
                # Check for existing result (idempotency)
                existing = self._check_existing(data)
                if existing:
                    logger.info("Result already exists, skipping")
                    self._publish_success_event(existing)
                    return
                
                # Do work
                result = self._do_work(data)
                
                # Store result (with idempotency handling)
                try:
                    self.document_store.insert_document("results", result)
                except DuplicateKeyError:
                    logger.debug(f"Result {result.get('id')} already exists")
                
                # Publish success
                duration = time.time() - start_time
                self._publish_success_event(result)
                
                # Metrics
                if self.metrics_collector:
                    self.metrics_collector.increment("items_processed_total", 1)
                    self.metrics_collector.observe("processing_duration_seconds", duration)
                
                return
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                error_type = type(e).__name__
                
                logger.error(
                    f"Processing failed (attempt {retry_count}/{self.max_retries}): {error_msg}",
                    exc_info=True
                )
                
                if retry_count >= self.max_retries:
                    # Publish failure event
                    self._publish_failure_event(data, error_msg, error_type, retry_count)
                    
                    if self.error_reporter:
                        self.error_reporter.report(e, context={"data": data, "retry_count": retry_count})
                    
                    if self.metrics_collector:
                        self.metrics_collector.increment("failures_total", 1, tags={"error_type": error_type})
                    
                    # Re-raise to trigger message requeue to failed queue
                    raise
                else:
                    # Exponential backoff
                    backoff_time = self.retry_backoff_seconds * (2 ** (retry_count - 1))
                    capped_backoff_time = min(backoff_time, 60)
                    logger.info(f"Retrying in {capped_backoff_time} seconds...")
                    time.sleep(capped_backoff_time)

    def _check_existing(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if result already exists (idempotency)."""
        # Implement based on your data model
        pass

    def _do_work(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual work."""
        # Implement your business logic
        pass

    def _publish_success_event(self, result: Dict[str, Any]):
        """Publish success event."""
        # Implement based on your event schema
        pass

    def _publish_failure_event(
        self, 
        data: Dict[str, Any], 
        error_msg: str, 
        error_type: str, 
        retry_count: int
    ):
        """Publish failure event."""
        # Implement based on your event schema
        pass
```

## References

### Documentation
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [FAILED_QUEUE_OPERATIONS.md](./FAILED_QUEUE_OPERATIONS.md) - Failed queue management
- [SERVICE_MONITORING.md](./SERVICE_MONITORING.md) - Monitoring and observability
- [PER_MESSAGE_EVENTS_MIGRATION.md](./PER_MESSAGE_EVENTS_MIGRATION.md) - Event granularity patterns
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contributor guidelines

### Schemas
- [archives.schema.json](./schemas/documents/archives.schema.json) - Archive status field
- [chunks.schema.json](./schemas/documents/chunks.schema.json) - Chunk embedding_generated field
- [*Failed.schema.json](./schemas/events/) - Failed event schemas

### Code Examples
- `chunking/app/service.py` - DuplicateKeyError handling
- `embedding/app/service.py` - Upsert semantics, retry logic, status updates
- `orchestrator/app/service.py` - Read-before-write idempotency
- `summarization/app/service.py` - Existing summary checks
- `adapters/copilot_events/copilot_events/rabbitmq_subscriber.py` - Requeue implementation

### Tests
- `chunking/tests/test_service.py::test_idempotent_chunk_insertion` - Verifies DuplicateKeyError handling
- `embedding/tests/test_service.py` - Tests embedding generation with status field updates
- `summarization/tests/test_service.py` - Tests summarization workflow
- `orchestrator/tests/test_service.py` - Tests orchestration workflow

### Utilities
- `scripts/manage_failed_queues.py` - Failed queue CLI tool
- `adapters/copilot_metrics/` - Metrics collection adapter
- `adapters/copilot_reporting/` - Error reporting adapter
