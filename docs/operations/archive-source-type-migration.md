# Archive source_type Migration

## Overview

This migration backfills the `source_type` field for legacy archives in the database that don't have this field set. The parsing service requires this field and defaults to 'local' when missing, but logs a warning on every occurrence.

## Problem

Before this migration:
- Legacy archives in the database were missing the `source_type` field
- Parsing service logged WARNING for every legacy archive encountered
- High volume (3072+ occurrences in production) drowned out real issues
- The service defaults to 'local' but this creates unnecessary log noise

## Solution

### 1. Rate-Limited Logging (Code Change)

Modified `parsing/app/service.py` to:
- Log WARNING once per service instance for first legacy archive
- Log subsequent occurrences at INFO level to reduce noise
- Include helpful message about backfilling in first warning

### 2. Migration Script

Created `scripts/backfill_archive_source_type.py` to:
- Query archives missing `source_type` field
- Set `source_type='local'` for these legacy documents
- Support dry-run mode for safe preview
- Support batch processing with `--limit` parameter

## Running the Migration

### Prerequisites

- Access to the document database (MongoDB/Cosmos DB)
- Appropriate environment variables configured:
  - `DOCUMENT_DATABASE_HOST`
  - `DOCUMENT_DATABASE_PORT`
  - `DOCUMENT_DATABASE_NAME`
  - Authentication credentials if required

### Dry Run (Recommended First)

Preview what will be changed without modifying the database:

```bash
cd /home/runner/work/CoPilot-For-Consensus/CoPilot-For-Consensus
python scripts/backfill_archive_source_type.py --dry-run
```

### Live Migration (All Documents)

Backfill all legacy archives:

```bash
python scripts/backfill_archive_source_type.py
```

### Batch Processing

Process documents in batches to avoid long-running operations:

```bash
# Process first 1000 documents
python scripts/backfill_archive_source_type.py --limit 1000

# Run multiple times until no more documents found
python scripts/backfill_archive_source_type.py --limit 1000
```

## Running from Docker Compose Environment

If you are running the document database via Docker Compose (for example, using the `documentdb` service), you should run the migration script from your local checkout, not inside the `parsing` container. The `parsing` image does not include the `scripts/` directory.

A typical workflow is:

1. Start the Docker Compose stack so the database is available:

   ```bash
   docker compose up -d documentdb
   ```

2. From the repository root on your host, set the environment variables so the script can reach the database exposed by Docker, then run the script:

   ```bash
   # Example values; adjust to match your docker-compose.yml
   export DOCUMENT_DATABASE_HOST=localhost
   export DOCUMENT_DATABASE_PORT=27017
   export DOCUMENT_DATABASE_NAME=copilot

   # Dry run
   python scripts/backfill_archive_source_type.py --dry-run

   # Live migration
   python scripts/backfill_archive_source_type.py

   # With limit
   python scripts/backfill_archive_source_type.py --limit 1000
   ```

3. Alternatively, if you have access to the MongoDB container directly:

   ```bash
   # Run from inside the documentdb container (if pymongo is installed)
   docker compose exec documentdb python /path/to/backfill_archive_source_type.py --dry-run
   ```

## Verification

After running the migration:

1. **Check migration output**: The script reports:
   - Total documents found
   - Documents updated
   - Any errors encountered

2. **Verify in database**: Query to confirm all archives have source_type:
   ```javascript
   // MongoDB query
   db.archives.find({ source_type: { $exists: false } }).count()
   // Should return 0 after migration
   ```

3. **Check parsing service logs**: After migration, you should see:
   - No more WARNING messages about missing source_type
   - Or at most one WARNING per service restart (rate-limited)

## Rollback

If needed, you can revert the changes:

```javascript
// MongoDB - remove source_type from migrated documents
// Note: Only do this if migration caused issues
db.archives.updateMany(
  { source_type: "local" },
  { $unset: { source_type: "" } }
)
```

⚠️ **Warning**: Only rollback if absolutely necessary. The parsing service works correctly with the default behavior, but logs will be noisy again.

## Impact

### Before Migration
- 3072+ WARNING logs per 6-hour window in production
- Legitimate warnings potentially missed due to noise
- No functional impact (service defaults to 'local')

### After Migration
- Zero or one WARNING per service instance (rate-limited)
- Subsequent legacy documents logged at INFO level
- Clean logs with better signal-to-noise ratio
- Database properly reflects actual source type

## Testing

The migration has been tested with:
- Unit tests in `scripts/test_backfill_archive_source_type.py`
- Dry-run mode verification
- Limit parameter functionality
- Error handling for database failures

All 6 migration tests pass, plus 101 parsing service tests.

## Timeline

- **Discovery**: 01/22/2026 - High log volume detected in Azure Monitor
- **Implementation**: 01/23/2026 - Migration script created
- **Testing**: 01/23/2026 - All tests pass
- **Deployment**: TBD - Run migration in dev/staging before production

## Related Files

- `parsing/app/service.py` - Rate-limited logging implementation
- `scripts/backfill_archive_source_type.py` - Migration script
- `scripts/test_backfill_archive_source_type.py` - Migration tests
- `parsing/tests/test_forward_progress.py` - Rate-limiting tests
