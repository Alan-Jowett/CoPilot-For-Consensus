# Event Retry Mechanism for Race Condition Handling

## Overview

The Copilot-for-Consensus services implement a robust retry mechanism to handle race conditions that occur when events arrive before the corresponding CosmosDB documents are fully queryable. This is a common issue in distributed systems where:

1. A service writes a document to the database
2. The service publishes an event about the document
3. A downstream service receives the event
4. The document is not yet queryable due to eventual consistency

## Architecture

### Retry Utility Module (`copilot_event_retry`)

A shared adapter provides retry logic that can be integrated into any service:

- **Location**: `adapters/copilot_event_retry/`
- **Key Components**:
  - `RetryConfig`: Configuration for retry behavior
  - `RetryPolicy`: Implements exponential backoff with jitter
  - `handle_event_with_retry`: Wrapper function for event handlers
  - `DocumentNotFoundError`: Exception to trigger retries

### Integration Points

The retry mechanism is integrated into:

1. **Chunking Service** (`chunking/app/service.py`)
   - Wraps `_handle_json_parsed` event handler
   - Retries when messages are not found in the database

2. **Embedding Service** (`embedding/app/service.py`)
   - Wraps `_handle_chunks_prepared` event handler
   - Retries when chunks are not found in the database

## Configuration

### Environment Variables

Retry behavior can be configured via environment variables (without requiring redeployment):

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRY_MAX_ATTEMPTS` | `8` | Maximum number of retry attempts before giving up |
| `RETRY_BASE_DELAY_MS` | `250` | Initial delay in milliseconds before first retry |
| `RETRY_BACKOFF_FACTOR` | `2.0` | Exponential backoff multiplier for each retry |
| `RETRY_MAX_DELAY_SECONDS` | `60` | Maximum delay cap between retries (in seconds) |
| `RETRY_TTL_MINUTES` | `30` | Total time-to-live for retries (abandon after this duration) |

### Default Retry Schedule

With default settings, the retry delays follow this pattern (with jitter):

| Attempt | Delay (approx) |
|---------|----------------|
| 1 | 250ms |
| 2 | 500ms |
| 3 | 1s |
| 4 | 2s |
| 5 | 4s |
| 6 | 8s |
| 7 | 16s |
| 8 | 32s |

Maximum cumulative wait time: ~1 minute (before TTL timeout)

## Retry Strategy

### Exponential Backoff with Full Jitter

The retry policy implements exponential backoff with full jitter to:
- Reduce contention under high load
- Spread retries over time
- Prevent thundering herd problems

**Formula**: `delay = random(0, min(base_delay * factor^attempt, max_delay))`

### Retryable vs Non-Retryable Errors

**Retryable Errors** (will trigger retry):
- `DocumentNotFoundError`: Document not yet queryable (race condition)

**Non-Retryable Errors** (sent to DLQ immediately):
- Validation errors
- Data integrity errors
- Programming errors (TypeError, AttributeError, etc.)

### Abandonment Conditions

Retries are abandoned when:
1. Maximum attempts reached (`max_attempts`)
2. Total TTL exceeded (`ttl_minutes`)

## Idempotency

### Idempotency Keys

Each event is assigned an idempotency key to prevent duplicate processing:

- **Chunking**: `"chunking-{message_id_1}-{message_id_2}-{message_id_3}"`
- **Embedding**: `"embedding-{chunk_id_1}-{chunk_id_2}-{chunk_id_3}"`

The idempotency key is included in:
- Retry attempts (ensures same event is retried)
- Dead letter queue entries (for diagnostics)
- Metrics (for tracking duplicate detection)

## Dead Letter Queue (DLQ)

### When Events Go to DLQ

Events are sent to the dead letter queue when:
1. Maximum retry attempts exhausted
2. TTL exceeded
3. Non-retryable error encountered

### DLQ Payload

Each DLQ entry includes diagnostic information:

```json
{
  "original_event": { /* full event data */ },
  "idempotency_key": "chunking-abc-def-ghi",
  "attempt_count": 8,
  "last_error": "DocumentNotFoundError: No messages found...",
  "error_type": "DocumentNotFoundError",
  "abandoned_reason": "max_attempts_exceeded",
  "service_name": "chunking",
  "timestamp": "2026-01-17T05:00:00Z"
}
```

## Observability

### Metrics

The retry mechanism emits metrics for monitoring and alerting:

#### Success Metrics
- `event_retry_success_total{service="chunking|embedding", attempt="N"}` - Counter of successful retries
- `event_retry_latency_seconds{service="chunking|embedding"}` - Histogram of total retry duration

#### Failure Metrics
- `event_retry_dlq_total{service="chunking|embedding", reason="max_attempts|ttl_exceeded"}` - Counter of DLQ events
- `event_retry_attempt_count{service="chunking|embedding"}` - Histogram of retry attempts per event

### Logging

The retry mechanism logs at appropriate levels:

- **INFO**: Retry attempts, success after retry
- **WARNING**: Approaching max attempts, approaching TTL
- **ERROR**: DLQ submission, non-retryable errors

**Example Log Output**:
```
INFO: Retry attempt 3/8 for event with idempotency key: chunking-123-456-789
INFO: Event processed successfully after 3 retry attempts (total latency: 1.75s)
ERROR: Event sent to DLQ after 8 attempts (reason: max_attempts_exceeded)
```

## Testing

### Unit Tests

The retry utility includes comprehensive unit tests (28 tests):

- **Location**: `adapters/copilot_event_retry/tests/`
- **Coverage**:
  - Retry policy calculation
  - Exponential backoff with jitter
  - TTL enforcement
  - Idempotency key handling
  - DLQ integration
  - Metrics collection

**Run tests**:
```bash
cd adapters/copilot_event_retry
pytest tests/ -v
```

### Integration Testing

Integration tests should verify:
1. End-to-end retry behavior with real message queue
2. Document eventually becoming queryable
3. Metrics being emitted correctly
4. DLQ receiving abandoned events

## Best Practices

### For Service Developers

1. **Raise `DocumentNotFoundError`** when a document is expected but not found
2. **Let other exceptions propagate** - they will be handled appropriately
3. **Use consistent idempotency keys** - based on stable document identifiers
4. **Monitor DLQ metrics** - high DLQ rates indicate systemic issues

### For Operations

1. **Tune retry parameters** based on observed behavior:
   - Increase `max_attempts` if documents take longer to become queryable
   - Increase `ttl_minutes` for slower backends
   - Adjust `base_delay_ms` based on typical latency

2. **Alert on DLQ metrics**:
   - High DLQ rate may indicate database performance issues
   - Consistent DLQ entries suggest configuration problems

3. **Review DLQ entries** periodically for patterns

## Architectural Considerations

### Alternative Approaches

While the retry mechanism solves the immediate problem, consider these architectural improvements:

1. **Transactional Outbox Pattern**:
   - Write document and event together
   - Guarantee event only published after commit

2. **CosmosDB Change Feed**:
   - Subscribe to change feed instead of publishing events manually
   - Guarantees document is queryable before event is emitted

3. **Read-Your-Writes Consistency**:
   - Use session consistency with session tokens
   - Pass token from writer to reader via event

## References

- [Azure Cosmos DB Consistency Levels](https://docs.microsoft.com/azure/cosmos-db/consistency-levels)
- [Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Dead Letter Queue Pattern](https://www.enterpriseintegrationpatterns.com/patterns/messaging/DeadLetterChannel.html)
