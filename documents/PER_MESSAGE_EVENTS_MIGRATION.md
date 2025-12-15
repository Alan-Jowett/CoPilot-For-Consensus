<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Per-Message Event Publishing Migration

## Overview

As of commit `c42a7a1`, the parsing service now publishes **per-message events** instead of per-archive batch events. This change enables fine-grained retry granularity and prevents full archive reprocessing when a single message fails in downstream services.

## What Changed

### Before (Per-Archive Events)

The parsing service published **one** `JSONParsed` event per archive containing all message IDs:

```json
{
  "event_type": "JSONParsed",
  "data": {
    "archive_id": "abc123",
    "message_count": 231,
    "parsed_message_ids": ["msg-1", "msg-2", ..., "msg-231"],
    "thread_count": 132,
    "thread_ids": ["thread-1", "thread-2", ...],
    "parsing_duration_seconds": 0.99
  }
}
```

**Problem**: If chunking failed on message #150, the entire batch of 231 messages was retried.

### After (Per-Message Events)

The parsing service now publishes **one** `JSONParsed` event per message:

```json
{
  "event_type": "JSONParsed",
  "data": {
    "archive_id": "abc123",
    "message_count": 1,
    "parsed_message_ids": ["msg-1"],
    "thread_count": 1,
    "thread_ids": ["thread-1"],
    "parsing_duration_seconds": 0.99
  }
}
```

**Benefit**: If chunking fails on message #150, only that message is retried, not all 231.

## Impact on Services

### Parsing Service

- **Changed**: `_publish_json_parsed()` method renamed to `_publish_json_parsed_per_message()`
- **Behavior**: Now publishes N events for N messages instead of 1 event for all messages
- **Logging**: New log message: `Published N JSONParsed events for archive {archive_id}`

### Chunking Service

- **No API changes**: Continues to accept `parsed_message_ids` as an array
- **New**: Idempotency handling for duplicate chunk insertions
  - Skips `DuplicateKeyError` gracefully (logs at DEBUG level)
  - Still includes duplicate chunks in `chunk_ids` output
  - Logs: `Created X chunks, skipped Y duplicates`

### Message Bus (RabbitMQ)

- **Event Volume**: Increased by factor of average messages per archive (e.g., 231x for large archives)
- **Queue Throughput**: Higher event count but smaller payloads
- **Retry Behavior**: Nack/requeue now affects single messages, not entire archives

## Migration Guide

### For Operators

1. **Monitor RabbitMQ**: Expect higher message counts but lower payload sizes
   - Check queue depths and throughput metrics
   - Adjust prefetch count if needed (currently defaults to 1)

2. **No data migration required**: Change is backward compatible with event schema
   - Both single-message and multi-message arrays are valid per schema

3. **Log volume**: Expect more "Published JSONParsed event" logs from parsing service
   - Set `app.service` logger to INFO or higher to reduce verbosity

### For Developers

1. **Event handlers**: No changes required
   - Chunking service already processes `parsed_message_ids` as an array
   - Single-item arrays work identically to multi-item arrays

2. **Testing**: 
   - Update tests that assert on event count (see `parsing/tests/test_service.py`)
   - Verify per-message event publishing in integration tests

3. **Metrics**:
   - `parsing_messages_parsed_total` still tracks total messages
   - No new metrics added for per-message events

## Benefits

1. **Fine-grained retry**: Only failed messages are retried, not entire archives
2. **Reduced waste**: Successfully chunked messages aren't re-chunked
3. **Better isolation**: Easier to identify and skip permanently broken messages
4. **Idempotency**: Duplicate chunk insertions handled gracefully

## Trade-offs

1. **Higher event count**: More RabbitMQ overhead for event routing
2. **Lost batch context**: Archive context less visible in individual events (still in logs)
3. **Ordering**: Messages processed in order but completion may vary

## Rollback

If rollback is needed:

1. Revert commits `766bdb3` and `c42a7a1`
2. Redeploy parsing and chunking services
3. No data cleanup required (idempotency ensures no duplicates)

## Related Issues

- Issue: Parsing publishes per-archive events forcing full reprocessing (#TBD)
- PR: Implement per-message JSONParsed events (#TBD)

## Testing

All existing tests pass with the new implementation:

- Parsing service: 28/28 tests pass
- Chunking service: 23/23 tests pass

New tests added:

- `test_event_publishing_on_success`: Verifies per-message event publishing
- `test_idempotent_chunk_insertion`: Verifies duplicate handling in chunking

## Questions?

Contact the development team or open an issue on GitHub.
