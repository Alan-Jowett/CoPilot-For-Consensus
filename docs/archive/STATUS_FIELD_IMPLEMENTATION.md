<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Document Status Field Implementation Summary

## Overview
This implementation adds a `DocumentStatus` enum and tracking fields to the document schema for forward progress tracking across the Copilot-for-Consensus system.

## Problem Statement
Services needed a standardized way to:
- Track document processing state (pending, processing, completed, failed)
- Detect incomplete work and retry safely
- Observe which worker is processing documents
- Monitor document age and detect stale processing

## Solution

### 1. Python Enum Definition
Created `DocumentStatus` enum in `copilot_schema_validation/models.py`:

```python
class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_MAX_RETRIES = "failed_max_retries"
```

**Features:**
- Inherits from `str` for seamless integration with MongoDB queries
- Provides type safety and IDE autocompletion
- Exported from `copilot_schema_validation` package for use across services

### 2. Schema Updates
Added fields to all document schemas (archives, messages, chunks, threads):

**New Fields:**
- `lastUpdated` (DateTime, optional): Timestamp of last status/field update
- `workerId` (String, nullable): Identifier of worker processing the document

**Existing Fields Enhanced:**
- `status` enum values now match Python enum
- `attemptCount` tracks retry attempts
- `lastAttemptTime` tracks last processing attempt

### 3. Documentation
Updated `docs/schemas/data-storage.md` with:
- Detailed field descriptions
- Index recommendations for `lastUpdated`
- All status enum values documented
- Forward progress tracking use cases

### 4. Examples
Created `examples/document_status_tracking.py` demonstrating:
- Document retry logic with attempt counting
- Status update patterns with worker tracking
- Query builders for finding work
- Detecting stale documents stuck in processing

## Benefits

### Developer Experience
- **Type Safety**: Python enum prevents typos and provides IDE support
- **Clear API**: Explicit status values replace magic strings
- **Consistency**: Same enum used across all services

### Operations
- **Observability**: `workerId` shows which service instance is processing
- **Debugging**: `lastUpdated` helps identify stuck documents
- **Monitoring**: Can query by status to track processing pipeline

### Reliability
- **Safe Retries**: `attemptCount` prevents infinite retry loops
- **Progress Tracking**: `status` field enables workflow orchestration
- **Recovery**: Can detect and reset stale documents

## Backward Compatibility

✅ All new fields are optional - existing documents remain valid
✅ Services can adopt new fields incrementally
✅ No breaking changes to existing schemas

## Testing

### Unit Tests
- 5 new tests for `DocumentStatus` enum
- All 56 tests passing in `copilot_schema_validation`
- Schema validation tests confirm JSON schema validity

### Integration Tests
- Documents with new fields validate correctly
- Documents without new fields validate correctly (backward compatible)
- Enum integrates with MongoDB query syntax

### Example Validation
- Example script runs successfully
- Demonstrates all status transitions
- Shows retry logic and query patterns

## Files Modified

1. **Python Code:**
   - `adapters/copilot_schema_validation/copilot_schema_validation/models.py`
   - `adapters/copilot_schema_validation/copilot_schema_validation/__init__.py`
   - `adapters/copilot_schema_validation/tests/test_models.py`

2. **JSON Schemas:**
   - `docs/schemas/documents/archives.schema.json`
   - `docs/schemas/documents/messages.schema.json`
   - `docs/schemas/documents/chunks.schema.json`
   - `docs/schemas/documents/threads.schema.json`

3. **Documentation:**
   - `docs/schemas/data-storage.md`
   - `examples/document_status_tracking.py` (new)

## Usage Examples

### Import the enum:
```python
from copilot_schema_validation import DocumentStatus
```

### Check document status:
```python
status = DocumentStatus(document["status"])
if status == DocumentStatus.PENDING:
    # Process the document
    pass
```

### Update with tracking:
```python
document["status"] = DocumentStatus.PROCESSING.value
document["lastUpdated"] = datetime.now(timezone.utc).isoformat()
document["workerId"] = "worker-001"
```

### Query for work:
```python
query = {
    "status": {"$in": [DocumentStatus.PENDING.value, DocumentStatus.FAILED.value]}
}
```

### Detect stale documents:
```python
threshold = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
query = {
    "status": DocumentStatus.PROCESSING.value,
    "lastUpdated": {"$lt": threshold}
}
```

## Next Steps (Optional Future Work)

1. **Service Integration:**
   - Update services to populate `workerId` field
   - Add monitoring dashboards for document status
   - Implement automatic stale document recovery

2. **Metrics:**
   - Export Prometheus metrics by status
   - Track processing duration via `lastUpdated`
   - Monitor worker utilization via `workerId`

3. **Schema Evolution:**
   - Consider making `lastUpdated` required in v2.0
   - Add `errorMessage` field for failed documents
   - Add `processingStartedAt` for duration tracking

## Conclusion

This implementation provides a solid foundation for forward progress tracking across the Copilot-for-Consensus system. The Python enum ensures consistency, the tracking fields enable observability, and backward compatibility ensures smooth adoption.

All changes are minimal, well-tested, and follow existing repository conventions.
