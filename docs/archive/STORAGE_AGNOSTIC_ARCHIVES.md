<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Storage-Agnostic Archive Handling

## Overview

This document describes the storage-agnostic approach to archive handling in Copilot-for-Consensus. As of this implementation, the `file_path` field is **optional** in archive documents and events, enabling support for non-path-based storage backends like Azure Blob Storage with managed identity.

## Background

### The Problem

The original design tied archive documents to path-based storage by requiring `file_path` in:
- `archives` collection schema
- `ArchiveIngested` event schema
- `ParsingFailed` event schema

This created issues for storage backends that don't use local filesystem paths:
- **Azure Blob Storage**: Uses blob URLs or managed identity without local paths
- **MongoDB GridFS**: Uses GridFS identifiers, not filesystem paths
- **S3**: Uses object keys, not filesystem paths

Storage-agnostic deployments had to manufacture fake paths or carry meaningless `file_path` values.

## Solution: Optional file_path

### Schema Changes

#### archives Collection Schema

```json
{
  "properties": {
    "file_path": {
      "type": "string",
      "minLength": 1,
      "description": "Optional file path for local storage backends. Not required for storage-agnostic backends (e.g., Azure Blob). Archive location is determined by archive_id and backend type."
    }
  },
  "required": ["_id", "file_hash", "file_size_bytes", "source", "ingestion_date", "status"]
}
```

**Note**: `file_path` is **NOT** in the `required` array.

#### ArchiveIngested Event Schema

```json
{
  "data": {
    "properties": {
      "file_path": {
        "type": "string",
        "minLength": 1,
        "description": "Optional file path for local storage backends. Not required for storage-agnostic backends (e.g., Azure Blob)."
      }
    },
    "required": [
      "archive_id",
      "source_name",
      "source_type",
      "source_url",
      "file_size_bytes",
      "file_hash_sha256",
      "ingestion_started_at",
      "ingestion_completed_at"
    ]
  }
}
```

**Note**: `file_path` is **NOT** in the `required` array.

#### ParsingFailed Event Schema

```json
{
  "data": {
    "properties": {
      "file_path": {
        "type": "string",
        "minLength": 1,
        "description": "Optional file path for local storage backends. For storage-agnostic backends, this field should be omitted entirely."
      }
    },
    "required": [
      "archive_id",
      "error_message",
      "error_type",
      "messages_parsed_before_failure",
      "retry_count",
      "failed_at"
    ]
  }
}
```

**Note**: `file_path` is **NOT** in the `required` array.

## Archive Location Representation

### By Storage Backend

Archive location is represented differently depending on the backend:

| Backend | Location Identifier | file_path Value |
|---------|-------------------|-----------------|
| **Local Filesystem** | File path | `/data/raw_archives/source/file.mbox` |
| **Azure Blob** | archive_id + container | **Omitted** (field not included) |
| **MongoDB GridFS** | archive_id | **Omitted** (field not included) |
| **AWS S3** | archive_id + bucket | **Omitted** (field not included) |

**Note**: For storage-agnostic backends, the `file_path` field should be omitted entirely from documents and events, not set to a placeholder value.

## Service Implementation

### Ingestion Service

The ingestion service:
1. ✅ Stores archives using `ArchiveStore.store_archive()` which returns `archive_id`
2. ✅ Creates archive documents with `archive_id` as the primary locator
3. ✅ **Omits** `file_path` from `ArchiveIngested` events (line 935 in `service.py`)
4. ✅ Tracks backend type in `storage_backend` field for observability

```python
# ingestion/app/service.py line 935
event_data.pop('file_path', None)  # Remove file_path - not storage-agnostic
```

### Parsing Service

The parsing service:
1. ✅ Retrieves archives using `ArchiveStore.get_archive(archive_id)` - no path needed
2. ✅ Handles `ArchiveIngested` events **without** `file_path` field
3. ✅ Omits `file_path` from `ParsingFailed` events when it's None (storage-agnostic mode)

```python
# parsing/app/service.py
# Only include file_path if provided (local filesystem storage)
if file_path is not None:
    event_data["file_path"] = file_path
```

## Migration Path

### For Existing Deployments

**No breaking changes**. Existing deployments with local filesystem storage continue to work:
- `file_path` is still stored in archive documents (just not required)
- Services handle both with and without `file_path`
- Events work with or without `file_path` field

### For New Azure Blob Deployments

1. Configure ArchiveStore with Azure backend:
   ```bash
   export ARCHIVE_STORE_TYPE=azure_blob
   export AZURE_STORAGE_ACCOUNT_NAME=mystorageaccount
   ```

2. Events will automatically omit `file_path`
3. Archive documents will use `archive_id` as the locator
4. Parsing service retrieves via `ArchiveStore.get_archive(archive_id)`

## Testing

### Test Coverage

New tests validate storage-agnostic behavior:

1. **`test_storage_agnostic.py`** (parsing service)
   - ParsingFailed events with file_path truly omitted (not present in event data)
   - ParsingFailed events with file_path included for local storage
   - Processing archives without file_path in ArchiveIngested event data
   - Archive not found error handling with file_path omitted

2. **`test_service.py`** (ingestion service)
   - ArchiveIngested events do not include file_path
   - Schema validation passes without file_path

### Running Tests

```bash
# Parsing service tests
cd parsing
pytest tests/test_storage_agnostic.py -v

# Ingestion service tests
cd ingestion
pytest tests/test_service.py::test_archive_ingested_event_without_file_path -v
```

## Benefits

### Deployment Flexibility

- ✅ **Azure Blob Storage**: Use managed identity without fake paths
- ✅ **MongoDB GridFS**: Store archives in MongoDB without filesystem
- ✅ **AWS S3**: Use object keys without local paths
- ✅ **Multi-cloud**: Same code works across all backends

### Cleaner Architecture

- ✅ **Single source of truth**: `archive_id` is the canonical identifier
- ✅ **Backend abstraction**: Services don't need to know storage implementation
- ✅ **Event simplicity**: Events carry only essential metadata
- ✅ **No fake values**: No need to manufacture meaningless paths

### Future-Proof

- ✅ New storage backends can be added without schema changes
- ✅ Services remain storage-agnostic
- ✅ Clear separation between storage and processing layers

## Best Practices

### When to Include file_path

**Include** `file_path` when:
- Using local filesystem storage (current default)
- Path information is meaningful for debugging
- Legacy systems require it

**Omit** `file_path` when:
- Using Azure Blob, S3, or MongoDB GridFS
- Path would be meaningless or fake
- Backend uses non-path identifiers

### Logging and Debugging

Always log `archive_id` for traceability:

```python
logger.info(
    "Processing archive",
    archive_id=archive_id,
    source=source_name,
    # file_path is optional - may not be present
    file_path=archive_data.get("file_path", "N/A")
)
```

### Error Messages

Use `archive://` URI for user-facing messages when path is unavailable:

```python
error_msg = f"Failed to process archive {archive_id}"
# Not: f"Failed to process archive at {file_path}"
```

## References

- [ArchiveStore Implementation Summary](./archive-store-implementation-summary.md)
- [Archive Store Adapter README](../../adapters/copilot_archive_store/README.md)
- [Schema Documentation](../schemas/data-storage.md)

## Related Issues

- GitHub Issue: "Make archive documents storage-agnostic (remove required file_path)"

---

**Implementation Date**: January 2025
**Status**: ✅ Complete
**Breaking Changes**: None (backward compatible)
