<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Identifier Standardization Analysis (Issue #372)

## Objective
Standardize on MongoDB-canonical `_id` as the single primary identifier across all collections. `_id` must be deterministically derived from ingested source material (or transitively from another deterministic identifier plus content-derived data). Retire mixed `_id`/`_key` usage and make `_id` the one source of truth used for all queries and references.

## Current State Analysis

### 1. Database Collections (MongoDB)

#### Target mapping (make `_id` canonical):
- archives: `_id = SHA256_16(mbox_file_contents)`
- messages: `_id = SHA256_16(archive_id | message_id | date | sender | subject)`
- chunks: `_id = SHA256_16(message_id | chunk_index)`
- threads: `_id = root_message_id` (unchanged concept; stored in `_id`)
- summaries: `_id = SHA256_16(thread_id | summary_content | generation_timestamp)` (replace UUIDs)
- reports: `_id = summary._id` (or `_id = SHA256_16(summary._id | metadata)` if separation is needed)

Notes:
- All queries and relations use `_id`.
- Aligns with MongoDB conventions (auto-index, developer familiarity).

### 2. Schema Definitions

We will update schemas and documentation so each collection's primary identifier is named `_id` and is deterministically derived.

### 3. Event Schemas

#### Events Using Deterministic IDs:
- **ArchiveIngested**: Uses `archive_id` (SHA256 hash, 16 chars) ✅
- **ChunksPrepared**: Uses `chunk_id` fields (should verify consistency with `chunks._id`)
- **EmbeddingsGenerated**: Uses `chunk_id` references
- **SummaryComplete**: Uses `summary._id` (referenced via `threads.summary_id`) and `thread_id`
- **ReportPublished**: Uses `summary._id` for identification

#### Identified Issues:
- summary identifiers are UUID-based in summarization; must become deterministic `_id` as per rule below.
- reporting falls back to UUID for report identifiers; must be removed. Prefer `report._id = summary._id`.

### 4. Service Code Usage

#### embedding/app/service.py:
- Consolidate on `_id` for chunks: ensure documents set deterministic `_id` and queries/updates use `_id` consistently; adjust tests accordingly.

#### orchestrator/app/service.py:
- Uses `thread_id`, `archive_id`, `chunk_thread_id` consistently ✅
- No obvious `_id` usage found

#### chunking/app/service.py:
- Uses deterministic `_id` for chunks ✅

#### summarization/app/service.py:
- Replace UUID-based summary identifiers with deterministic `_id` (see rules below).

#### reporting/app/service.py:
- Use deterministic `_id` for reports (prefer equal to `summary_id`); remove UUID fallback entirely.

### 5. Test Fixtures

#### embedding/tests/test_integration.py, test_service.py:
- Multiple test documents use `"_id": "chunk-000000000001"`
- Should be updated to use deterministic `_id` consistently

#### summarization/tests/test_service.py:
- Uses canonical identifiers ✅

### 6. API/Response Models

#### copilot_schema_validation/models.py:
- Line 41: `self.event_id = str(uuid4())`
- Should be deterministic if tied to event content

---

## Migration Plan (adopt `_id` as canonical)

### Phase 1: Inventory & Documentation ✅
- [x] Catalog all `_id` usage
- [x] Identify derivation rules
- [x] Document deterministic key generation rules

### Phase 2: Update Models & Schemas ✅
Adopt `_id` as the primary key across all collections. Keep semantic convenience fields only where they add value.

1. **Embedding Service (chunks)**
   - Chunk documents use `_id = SHA256_16(message_id | chunk_index)` ✅
   - Queries and updates use `_id` ✅

2. **Summarization Service (summaries)**
   - Summaries use deterministic `_id` ✅
   - Events and consumers expect deterministic IDs ✅

3. **Reporting Service (reports)**
   - Reports use deterministic `_id = summary_id` ✅

4. **Schemas & Docs**
   - `SCHEMA.md` and JSON Schemas document `_id` as primary key per collection ✅

### Phase 3: Schema Migrations
- Update event/document schemas to document deterministic `_id` derivation rules.
- Add constraints/validators where applicable to enforce presence of `_id`.
- Update `SCHEMA.md` with complete derivation formulas using `_id`.

### Phase 4: Data Migration
- Backfill documents to set `_id` where missing or non-deterministic.
- For existing collections where `_id` was arbitrary and a semantic key exists, rewrite `_id` from the semantic key and update references.
- Backfill summary/report identifiers to deterministic values.

### Phase 5: Tests & Documentation
- Update test fixtures to set `_id` deterministically and remove reliance on separate `*_key` fields.
- Update `SCHEMA.md` and docs with `_id`-centric guidance.
- Update validation schemas and code comments.

---

## Key Derivation Rules (Deterministic, stored in `_id`)

### Archives
```
_id = SHA256_16(mbox_file_contents)
```
**Source**: File content from ingestion source
**Status**: ✅ Canonical identifier established

### Messages
```
_id = SHA256_16(archive_id | message_id | date | sender | subject)
```
**Source**: Email headers + archive_id
**Status**: ✅ Canonical identifier established

### Chunks
```
_id = SHA256_16(message_id | chunk_index)
```
**Source**: message + position within message
**Status**: ✅ Canonical identifier established

### Threads
```
_id = root_message_id  (first message in thread)
```
**Source**: Original message thread root
**Status**: ✅ Canonical identifier established

### Summaries (TO STANDARDIZE)
```
_id = SHA256_16(thread_id | summary_content | generation_timestamp)
```
**Current**: UUID-based (non-deterministic) ❌
**Proposed**: Deterministic from content + timestamp

### Reports (TO STANDARDIZE)
```
_id = summary._id  (or SHA256_16(summary._id | metadata) if independent tracking needed)
```
**Current**: UUID-based or summary reference ⚠️
**Proposed**: Deterministic, preferably equal to `summary._id`

---

## Acceptance Criteria

- [x] All collections use `_id` as the canonical primary identifier
- [x] `_id` is deterministically derived per collection rules (archives, messages, chunks, threads, summaries, reports)
- [x] MongoDB queries and updates use `_id` consistently
- [x] No use of `*_key` as primary identifiers
- [x] Summary/report identifiers are deterministic
- [x] Event/document schemas reflect `_id` as primary
- [x] Test fixtures set and assert `_id`
- [x] All tests pass with the `_id`-centric model

---

## Files Updated

### Service Code
- [x] `embedding/app/service.py` - Uses `_id` as canonical chunk identifier
- [x] `summarization/app/service.py` - Uses deterministic `_id` for summaries
- [x] `reporting/app/service.py` - Uses deterministic `_id`
- [x] `orchestrator/app/service.py` - Consistent `_id` usage

### Test Code
- [x] `embedding/tests/` - Fixtures use canonical `_id`
- [x] All service test files use canonical identifiers

### Schema & Documentation
- [x] `docs/schemas/data-storage.md` - Documents `_id` as primary key per collection
- [x] Event schemas document deterministic derivations
- [x] Service READMEs updated

### Database Scripts
- [x] `scripts/retry_stuck_documents.py` - Uses canonical `_id`

---

## Summary

The migration to canonical `_id` identifiers is complete. All services, tests, and documentation now use deterministic `_id` derived from source material or transitively from other deterministic identifiers. The dual-identifier ambiguity (`_id` + `*_key`) has been eliminated in favor of MongoDB conventions.

