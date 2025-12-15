# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Ingestion Archives Collection Implementation Summary

## Problem Statement
The ingestion service was successfully fetching archives from rsync sources but was not creating or updating entries in the `archives` collection in the document store, as specified in the architecture documentation.

## Root Cause
The ingestion service lacked:
1. Document store dependency and initialization
2. Logic to write archive metadata to the `archives` collection
3. The parsing service lacked logic to update archive status after parsing

## Solution Overview

### 1. Ingestion Service Changes

#### Configuration Schema Updates
**File:** `documents/schemas/configs/ingestion.json`
- Added `doc_store_type` (default: "mongodb")
- Added `doc_store_host` (default: "documentdb")
- Added `doc_store_port` (default: 27017)
- Added `doc_store_name` (default: "copilot")
- Added `doc_store_user` (default: "root")
- Added `doc_store_password` (default: "example")

#### Main Entry Point Updates
**File:** `ingestion/main.py`
- Imported `create_document_store` and `ValidatingDocumentStore`
- Added document store initialization with connection validation
- Wrapped document store with `ValidatingDocumentStore` (strict=False)
- Passed document store to `IngestionService`
- Added cleanup: `base_document_store.disconnect()`

#### Service Implementation Updates
**File:** `ingestion/app/service.py`

1. **Constructor Changes:**
   - Added `document_store: Optional[DocumentStore]` parameter
   - Stored document store as instance variable

2. **Archive Record Creation:**
   - Added `_write_archive_record()` method
   - Called after each file is successfully ingested
   - Creates document with schema-compliant structure:
     ```python
     {
         "archive_id": str(uuid4()),
         "source": source.name,
         "source_url": source.url,
         "format": file_ext or "mbox",
         "ingestion_date": ISO8601_timestamp,
         "message_count": 0,
         "file_path": file_path,
         "status": "pending"
     }
     ```
   - Uses best-effort error handling (logs warnings but doesn't fail)

3. **Default Configuration:**
   - Updated `DEFAULT_CONFIG` with document store fields

#### Docker Compose Updates
**File:** `docker-compose.yml`
- Changed `DOCUMENT_STORE_TYPE` to `DOC_STORE_TYPE` for consistency
- Added dependency on `documentdb` service with health check
- Added dependency on `db-validate` service

### 2. Parsing Service Changes

#### Service Implementation Updates
**File:** `parsing/app/service.py`

1. **Status Update Method:**
   - Added `_update_archive_status()` method
   - Updates archive document with new status and message_count
   - Uses best-effort error handling (logs warnings but doesn't fail parsing)

2. **Success Flow:**
   - Calls `_update_archive_status(archive_id, "processed", message_count)` after successful parsing
   - Updates occur after messages and threads are stored

3. **Failure Flow:**
   - Calls `_update_archive_status(archive_id, "failed", 0)` on parsing errors
   - Updates occur in both "no messages" case and exception handler

### 3. Test Updates

#### Unit Tests
**File:** `ingestion/tests/test_service.py`
- Updated `service` fixture to create `InMemoryDocumentStore`
- Added `test_archives_collection_populated()` test
- Verifies archive document structure:
  - Has `archive_id`
  - Has `source` matching source name
  - Has `status` = "pending"
  - Has `message_count` = 0
  - Has `ingestion_date` and `file_path`

#### Integration Tests
**File:** `ingestion/tests/test_integration.py`
- Updated `test_end_to_end_ingestion()` to create document store
- Added assertions to verify archives collection is populated
- Verifies correct number of archive documents created
- Verifies document structure for all archives

### 4. Verification Tooling

#### MongoDB Verification Script
**File:** `scripts/verify_archives_collection.py`
- Connects to MongoDB using environment variables
- Counts total archives
- Shows sample archive document
- Displays status breakdown (pending/processed/failed)
- Exit code 0 on success, 1 on failure

**Usage:**
```bash
# Set environment variables
export DOC_DB_HOST=localhost
export DOC_DB_PORT=27017
export DOC_DB_USER=root
export DOC_DB_PASSWORD=example
export DOC_DB_NAME=copilot

# Run verification
python scripts/verify_archives_collection.py
```

## Testing Results

### Unit Tests
- **Ingestion Service:** 20/20 tests passing
- **Parsing Service:** 28/28 tests passing

### Integration Tests
- **Ingestion Service:** All integration tests passing
- Archive collection population verified
- Document structure validated

### Manual Testing Commands
```bash
# Run ingestion unit tests
cd ingestion
pytest tests/test_service.py -v -m "not integration"

# Run specific archive test
pytest tests/test_service.py::TestIngestionService::test_archives_collection_populated -v

# Run integration tests
pytest tests/test_integration.py -v

# Verify with docker-compose (after system is running)
docker-compose exec ingestion python /app/scripts/verify_archives_collection.py
```

## Architecture Compliance

This implementation aligns with:

1. **documents/ARCHITECTURE.md (line 271):**
   - ArchiveIngested event payload includes `archive_id`
   - Ingestion service publishes event after storing metadata

2. **documents/SCHEMA.md (lines 15-27):**
   - Archives collection has all required fields
   - Uses correct data types (UUID for archive_id, DateTime for ingestion_date)
   - Status enum matches schema ("pending", "processed", "failed")

3. **Event Flow:**
   ```
   Ingestion → Create archive record (status=pending) → Publish ArchiveIngested event
   Parsing → Process archive → Update status to "processed" or "failed"
   ```

## Database Schema

### Archives Collection
```json
{
  "archive_id": "uuid-v4",
  "source": "source-name",
  "source_url": "rsync://...",
  "format": "mbox",
  "ingestion_date": "2023-10-15T14:30:00Z",
  "message_count": 150,
  "file_path": "/data/raw_archives/source/file.mbox",
  "status": "processed"
}
```

### Status Lifecycle
1. **pending**: Created by ingestion service after file download
2. **processed**: Updated by parsing service after successful parsing
3. **failed**: Updated by parsing service if parsing fails

## Error Handling

### Ingestion Service
- Document store write failures are logged as warnings
- Ingestion continues even if archive record write fails
- Event is still published to allow parsing to proceed
- Error reporter is notified (if configured)

### Parsing Service
- Archive status update failures are logged as warnings
- Parsing continues even if status update fails
- Messages and threads are still stored
- JSONParsed event is still published

## Observability

### Metrics
No new metrics added; existing ingestion and parsing metrics remain unchanged.

### Logs
New log messages:
- `"Wrote archive record to document store"` (info)
- `"Failed to write archive record to document store"` (warning)
- `"Updated archive {archive_id} status to '{status}'"` (info)
- `"Failed to update archive {archive_id} status"` (warning)

### Verification
Use the verification script to check:
- Total archive count
- Status distribution
- Sample document structure

## Dependencies

### New Dependencies
None - uses existing `copilot_storage` adapter

### Updated Services
- **ingestion**: Now requires document store connection
- **parsing**: Already had document store; added status update logic

## Deployment Notes

### Environment Variables
Ensure these are set for ingestion service:
- `DOC_STORE_TYPE=mongodb`
- `DOC_DB_HOST=documentdb`
- `DOC_DB_PORT=27017`
- `DOC_DB_NAME=copilot`
- `DOC_DB_USER=root`
- `DOC_DB_PASSWORD=example`

### Docker Compose
The ingestion service now depends on:
- `messagebus` (existing)
- `documentdb` (new)
- `db-validate` (new)

### Migration
No data migration required - this is a new feature that starts populating the archives collection going forward.

## Known Limitations

1. **Existing Archives**: Archives ingested before this change will not have records in the archives collection
2. **Partial Updates**: If parsing fails partway through, the archive status remains "pending" or "failed"
3. **No Retry**: Failed archive record writes are not retried (by design - best effort)

## Future Enhancements

1. **Backfill Script**: Create a script to backfill archives collection from ingestion logs
2. **Archive Metrics**: Add metrics for archive status transitions
3. **Dashboard**: Create Grafana dashboard showing archive processing status
4. **Archive Cleanup**: Implement cleanup for old archives based on retention policy

## References

- Issue: "Ingestion does not update `archives` collection in document store"
- Architecture: `documents/ARCHITECTURE.md`
- Schema: `documents/SCHEMA.md`
- Archives Schema: `documents/schemas/documents/archives.schema.json`
