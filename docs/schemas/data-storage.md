<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Data Storage Schema

High-level schema for the document database (MongoDB/Cosmos) and vector store (Qdrant/FAISS/Azure Cognitive Search). JSON schemas remain the source of truth under [documents/schemas](../../documents/schemas).

## Stores and identifiers
- Document DB: canonical store for archives, messages, threads, chunks, and summaries.
- Vector store: embeddings keyed by `chunks._id` with rich payload metadata.
- Identifiers: `_id` is a deterministic 16-char SHA256 short hash per collection; RFC headers keep their native names (`message_id`, `in_reply_to`, `references`). Cross-collection references reuse the canonical `_id` values (e.g., `chunks.message_id` → `messages.message_id`).

## Document collections (MongoDB/Cosmos)
- **archives**: `_id`, `file_hash`, `source`, `ingestion_date`, `status`, `attemptCount`, `lastAttemptTime`, `lastUpdated`; indexes on `_id`, `source`, `file_hash`, `ingestion_date`, `status`, `lastUpdated`.
- **messages**: `_id`, `message_id`, `archive_id`, `thread_id`, `in_reply_to`, `references`, `subject`, sender/recipient fields, normalized bodies, draft mentions, `status`, `attemptCount`, `lastUpdated`; indexes on `_id`, `archive_id`, `thread_id`, `date`, `in_reply_to`, `draft_mentions`, `created_at`, `status`, `lastUpdated`.
- **chunks**: `_id` (message hash + chunk index), `message_doc_id`, `message_id`, `thread_id`, chunk text/offsets, `token_count`, `embedding_generated`, `status`, `attemptCount`, `lastUpdated`; indexes on `_id`, `message_doc_id`, `message_id`, `thread_id`, `created_at`, `embedding_generated`, `status`, `lastUpdated`.
- **threads**: `_id` (root message), `archive_id`, participants, message counts, first/last message dates, draft mentions, consensus flags, `summary_id`, `status`, `attemptCount`, `lastUpdated`; indexes on `_id`, `archive_id`, `first_message_date`, `last_message_date`, `draft_mentions`, `has_consensus`, `summary_id`, `created_at`, `status`, `lastUpdated`.
- **summaries**: `_id`, `thread_id`, `summary_type`, titles/content, citations, `generated_by`, `generated_at`, metadata; indexes on `_id`, `thread_id`, `summary_type`, `generated_at`.

> `status`, `attemptCount`, `lastAttemptTime`, and `lastUpdated` fields are optional in JSON schemas but indexed for observability and retry workflows; consumers should tolerate documents missing these fields.

## Vector store (message_embeddings)
- **Key**: `id` = `chunks._id`.
- **Payload essentials**: `chunk_id`, `message_id`, `thread_id`, `archive_id`, `chunk_index`, `text`, `sender`, `date`, `subject`, `draft_mentions`, `token_count`, `embedding_model`, `embedding_date`.
- **Use**: Enables filtering (by thread, archive, draft, sender), preserves ordering via `chunk_index`, and keeps provenance for retrieval-augmented generation.

## Message bus event schemas
Event JSON schemas live under [documents/schemas/events](../../documents/schemas/events). Headings below keep legacy anchors for service README links; use them as a quick payload summary and follow the JSON for exact fields.

- Envelope: `event-envelope.schema.json` describes common metadata used by all events.

### 1. ArchiveIngested
- Payload: `archive_id`, `source`, `file_path`, `ingestion_date`, `message_count` (see `ArchiveIngested.schema.json`).

### 2. ArchiveIngestionFailed
- Payload: `archive_id`, `source`, `error`, `timestamp` (see `ArchiveIngestionFailed.schema.json`).

### 3. JSONParsed
- Payload: `archive_id`, `message_id`, `thread_id`, `parsed_at` plus message metadata (see `JSONParsed.schema.json`).

### 4. ParsingFailed
- Payload: `archive_id`, `message_id`, `error`, `timestamp` (see `ParsingFailed.schema.json`).

### 5. ChunksPrepared
- Payload: `archive_id`, `message_id`, `chunk_ids`, `chunk_count`, `chunks_ready`, `timestamp` (see `ChunksPrepared.schema.json`).

### 6. ChunkingFailed
- Payload: `archive_id`, `message_id`, `error`, `timestamp` (see `ChunkingFailed.schema.json`).

### 7. EmbeddingsGenerated
- Payload: `chunk_ids`, `embedding_model`, `vector_store_updated`, `timestamp` (see `EmbeddingsGenerated.schema.json`).

### 8. EmbeddingGenerationFailed
- Payload: `chunk_ids`, `error`, `timestamp` (see `EmbeddingGenerationFailed.schema.json`).

### 9. SummarizationRequested
- Payload: `thread_ids`, `summary_type`, `request_id`, `timestamp` (see `SummarizationRequested.schema.json`).

### 10. OrchestrationFailed
- Payload: `thread_ids`, `error`, `timestamp` (see `OrchestrationFailed.schema.json`).

### 11. SummaryComplete
- Payload: `thread_ids`, `summary_content` or summary reference, `report_id`, `timestamp` (see `SummaryComplete.schema.json`).

### 12. SummarizationFailed
- Payload: `thread_ids`, `error`, `timestamp` (see `SummarizationFailed.schema.json`).

### 13. ReportPublished
- Payload: `report_id`, `source`, `timestamp` (see `ReportPublished.schema.json`).

### 14. ReportDeliveryFailed
- Payload: `report_id`, `error`, `timestamp` (see `ReportDeliveryFailed.schema.json`).

## Relationships and flows
- Archive → Messages (1:N) via `messages.archive_id`.
- Message → Chunks (1:N) via `chunks.message_id`; Chunk → Embedding (1:1) via vector `id`.
- Thread aggregates messages; optional Summary references thread and cites chunk IDs.
- Retrieval path: Vector search → payload.chunk_id → `chunks` → `messages`; reverse lookup: `messages.message_id` → chunks → embeddings.

## Operational guidance
- Validate changes against JSON schemas in [documents/schemas](../../documents/schemas); bump `metadata.version` there when altering contracts.
- Keep indexes aligned with retry and observability queries (`status`, `lastUpdated`), and avoid removing optional fields without migration handling.
- For new fields, keep cardinality bounded (especially labels used in metrics) and update both document DB schemas and vector payload filters accordingly.
