<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Identifier Standardization Analysis (Issue #372)

## Objective
Standardize on `_key` (removing mixed `_id`/`_key`) across all services, schemas, and databases, ensuring every `_key` is derived from ingested source material or transitively derived from another `_key` plus content-derived data.

## Current State Analysis

### 1. Database Collections (MongoDB)

#### ✅ Collections Already Using `_key` (Documented in SCHEMA.md):
- **archives**: Primary key is `archive_id` (SHA256 hash of mbox file, 16 chars)
- **messages**: Primary key is `message_key` (SHA256 hash of archive_id|message_id|date|sender|subject, 16 chars)
- **chunks**: Primary key is `chunk_key` (SHA256 hash of message_key|chunk_index, 16 chars)
- **threads**: Primary key is `thread_id` (root message_id)

#### ⚠️ Collections Using MongoDB `_id`:
- **chunks**: Uses MongoDB `_id` field for queries (e.g., `embedding/app/service.py:242`)
  - Current: `batch_doc_ids = [chunk["_id"] for chunk in batch]`
  - Should use: `chunk_key` instead
- **Test fixtures**: Many test files insert documents with `"_id": "chunk-000000000001"` (embedding integration tests)
  - These should be `chunk_key` instead

### 2. Schema Definitions

#### Current State (from documents/SCHEMA.md):
- **Archives collection**: `archive_id` (primary) - deterministic
- **Messages collection**: `message_key` (primary) - deterministic from (archive_id|message_id|date|sender|subject)
- **Chunks collection**: `chunk_key` (primary) - deterministic from (message_key|chunk_index)
- **Threads collection**: `thread_id` (primary) - root message_id

**Status**: Good alignment on `_key` naming, but MongoDB's `_id` is still being used in queries.

### 3. Event Schemas

#### Events Using Deterministic IDs:
- **ArchiveIngested**: Uses `archive_id` (SHA256 hash, 16 chars) ✅
- **ChunksPrepared**: Uses `chunk_id` fields (should verify consistency with `chunk_key`)
- **EmbeddingsGenerated**: Uses `chunk_id` references
- **SummaryComplete**: Uses `summary_id` and `thread_id`
- **ReportPublished**: Uses `summary_id` for identification

#### Identified Issues:
- **summary_id**: Generated as `uuid.uuid4()` in summarization/app/service.py:270
  - Current: `summary_id = self._generate_summary_id(thread_id, formatted_citations)`
  - Issue: Not consistently derived from source material
  - Should be: SHA256(thread_id|summary_content|timestamp) for deterministic reproducibility

- **report_id**: Uses `uuid.uuid4()` in reporting/app/service.py:158
  - Issue: Non-deterministic
  - Should be: Derived from summary_id and content

### 4. Service Code Usage

#### embedding/app/service.py:
- Line 220: `chunks_without_id = [c.get("chunk_id", "unknown") for c in chunks if not c.get("_id")]`
  - **Issue**: Checking for MongoDB `_id` instead of `chunk_key`
  - **Fix**: Change to check for `chunk_key`

- Line 242: `batch_doc_ids = [chunk["_id"] for chunk in batch]`
  - **Issue**: Using MongoDB `_id` for updates
  - **Fix**: Use `chunk_key` instead

#### orchestrator/app/service.py:
- Uses `thread_id`, `archive_id`, `chunk_thread_id` consistently ✅
- No obvious `_id` usage found

#### chunking/app/service.py:
- Uses `message_key`, `archive_id` ✅
- No obvious `_id` usage found

#### summarization/app/service.py:
- Line 270: `summary_id = self._generate_summary_id(thread_id, formatted_citations)`
  - **Issue**: UUID-based, not deterministic from source
  - **Fix**: Use SHA256-based derivation

#### reporting/app/service.py:
- Line 155: `report_id = event_data["summary_id"]`
- Line 158: Falls back to `report_id = str(uuid.uuid4())`
  - **Issue**: Should always use summary_id or derive consistently
  - **Fix**: Remove UUID fallback or make deterministic

### 5. Test Fixtures

#### embedding/tests/test_integration.py, test_service.py:
- Multiple test documents use `"_id": "chunk-000000000001"`
- Should be updated to use `chunk_key` consistently

#### summarization/tests/test_service.py:
- Uses `thread_id`, `message_key` ✅

### 6. API/Response Models

#### copilot_schema_validation/models.py:
- Line 41: `self.event_id = str(uuid4())`
- Should be deterministic if tied to event content

---

## Migration Plan

### Phase 1: Inventory & Documentation ✅
- [x] Catalog all `_id` and `_key` usage
- [x] Identify derivation rules
- [ ] Document deterministic key generation rules

### Phase 2: Update Models & Schemas
**Services to update:**
1. **Embedding Service**
   - Replace `chunk["_id"]` with `chunk["chunk_key"]`
   - Update MongoDB queries to use `chunk_key` as primary identifier

2. **Summarization Service**
   - Replace UUID-based `summary_id` with deterministic SHA256 derivation
   - Update event schema to reflect deterministic summary_id

3. **Reporting Service**
   - Use `summary_id` consistently (no UUID fallback)
   - Ensure `report_id` is deterministic or tied to summary_id

4. **All Services**
   - Update any remaining `_id` references to use appropriate `_key` fields

### Phase 3: Schema Migrations
- Update event schemas to document `_key` derivation rules
- Add constraints to validate deterministic key generation
- Update SCHEMA.md with complete derivation formulas

### Phase 4: Data Migration
- Create migration script for embedding updates (change `_id` to `chunk_key` tracking)
- Backfill `summary_id` values with deterministic hashes (if needed)
- Migrate any legacy UUID-based identifiers

### Phase 5: Tests & Documentation
- Update all test fixtures to use consistent `_key` naming
- Update SCHEMA.md with final reference
- Add documentation of key derivation rules
- Update validation schemas and code comments

---

## Key Derivation Rules (Deterministic)

### Archive Key
```
archive_id = SHA256_16(mbox_file_contents)
```
**Source**: File content from ingestion source
**Status**: ✅ Already implemented

### Message Key
```
message_key = SHA256_16(archive_id | message_id | date | sender | subject)
```
**Source**: Email headers + archive_id
**Status**: ✅ Already defined in SCHEMA.md

### Chunk Key
```
chunk_key = SHA256_16(message_key | chunk_index)
```
**Source**: message_key + position in message
**Status**: ✅ Already defined in SCHEMA.md

### Thread ID
```
thread_id = root_message_id  (first message in thread)
```
**Source**: Original message thread root
**Status**: ✅ Already implemented

### Summary ID (TO STANDARDIZE)
```
summary_id = SHA256_16(thread_id | summary_content | generation_timestamp)
```
**Current**: UUID-based (non-deterministic) ❌
**Proposed**: Deterministic from content + timestamp

### Report ID (TO STANDARDIZE)
```
report_id = summary_id  (or SHA256_16(summary_id | metadata) if independent tracking needed)
```
**Current**: UUID-based or summary_id ⚠️
**Proposed**: Deterministic, preferably = summary_id

---

## Acceptance Criteria

- [ ] No remaining `_id` usage for primary identifiers in service code
- [ ] All collections use `_key`-based identification (archive_id, message_key, chunk_key, etc.)
- [ ] `summary_id` and `report_id` are deterministically derived from source material
- [ ] All MongoDB queries updated to use `_key` fields instead of `_id`
- [ ] Test fixtures updated to use consistent `_key` naming
- [ ] Event schemas document derivation rules
- [ ] Data migration completed or deemed unnecessary
- [ ] Documentation (SCHEMA.md) updated with complete key derivation reference
- [ ] All tests passing with new identifier scheme

---

## Files to Update

### Service Code
- [ ] `embedding/app/service.py` - Replace `_id` with `chunk_key`
- [ ] `summarization/app/service.py` - Standardize `summary_id` derivation
- [ ] `reporting/app/service.py` - Remove UUID fallback for report_id
- [ ] `orchestrator/app/service.py` - Verify consistent `_key` usage

### Test Code
- [ ] `embedding/tests/test_integration.py` - Update fixtures
- [ ] `embedding/tests/test_service.py` - Update fixtures
- [ ] All other service test files with `_id` fields

### Schema & Documentation
- [ ] `documents/SCHEMA.md` - Add key derivation rules section
- [ ] `documents/schemas/events/*.schema.json` - Document deterministic derivation
- [ ] `adapters/copilot_schema_validation/models.py` - Update event_id handling if needed

### Database Scripts
- [ ] `scripts/manage_failed_queues.py` - Update queries to use `_key` fields
- [ ] `scripts/retry_stuck_documents.py` - Update queries to use `_key` fields
- [ ] Create migration script if needed for existing data

---

## Next Steps

1. Update SCHEMA.md with key derivation rules (Phase 1 completion)
2. Start Phase 2: Update embedding service to use chunk_key
3. Standardize summary_id generation
4. Run test suite to validate changes
5. Create PR with migration script and documentation

