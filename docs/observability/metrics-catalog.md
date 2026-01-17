<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Metrics Catalog (Azure / OpenTelemetry + Prometheus)

This document is the *source of truth* for metrics emitted by the Copilot-for-Consensus codebase.

It covers:
- Metrics emitted via the shared `copilot_metrics` `MetricsCollector` abstraction (these map cleanly to Azure Monitor via OpenTelemetry).
- Metrics emitted directly by exporter scripts under `scripts/` (these are Prometheus-native).

## Naming: Prometheus vs Azure Monitor / OpenTelemetry

### `MetricsCollector`-emitted metrics

All service metrics in this section use *base names* like `parsing_duration_seconds`.

The exported names are determined by the metrics driver configuration:
- `namespace` default is `copilot` (see `DriverConfig_Metrics_*` in `adapters/copilot_config/.../metrics.py`).

| Backend | Final metric name |
|---------|--------------------|
| Prometheus / Pushgateway | `${namespace}_${base_name}` (example: `copilot_parsing_duration_seconds`) |
| Azure Monitor (OpenTelemetry) | `${namespace}.${base_name}` (example: `copilot.parsing_duration_seconds`) |

Tags/labels passed in code become:
- Prometheus labels
- OpenTelemetry attributes (Azure Monitor “dimensions”)

### Exporter script metrics

Metrics exposed by `scripts/*exporter*.py` and `scripts/retry_stuck_documents.py` are defined directly as Prometheus metrics (their names are exactly what the scripts declare).

If you ingest Prometheus into Azure using **Azure Managed Prometheus**, the metric names stay Prometheus-native (e.g., `qdrant_collection_vectors_count`).

If you want these metrics to appear as **OpenTelemetry/Azure Monitor custom metrics**, they must be re-emitted via the `MetricsCollector` (or otherwise instrumented with OpenTelemetry).

## Service metrics (via `MetricsCollector`)

Tables list the *base name* and the canonical names produced by default `namespace=copilot`.

### Auth service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `login_initiated_total` | Counter | `copilot_login_initiated_total` | `copilot.login_initiated_total` | `provider`, `audience` | Login flow started |
| `callback_success_total` | Counter | `copilot_callback_success_total` | `copilot.callback_success_total` | `audience` | OAuth callback succeeded |
| `callback_failed_total` | Counter | `copilot_callback_failed_total` | `copilot.callback_failed_total` | `error` | `error` is a bounded string (e.g., `validation_error`) |
| `logout_total` | Counter | `copilot_logout_total` | `copilot.logout_total` | (none) | Logout endpoint called |
| `userinfo_success_total` | Counter | `copilot_userinfo_success_total` | `copilot.userinfo_success_total` | `audience` | Userinfo endpoint succeeded |
| `userinfo_failed_total` | Counter | `copilot_userinfo_failed_total` | `copilot.userinfo_failed_total` | `error` | Userinfo endpoint failed |
| `jwks_requests_total` | Counter | `copilot_jwks_requests_total` | `copilot.jwks_requests_total` | (none) | JWKS endpoint requests |
| `public_key_requests_total` | Counter | `copilot_public_key_requests_total` | `copilot.public_key_requests_total` | (none) | Public key endpoint requests |
| `admin_list_pending_total` | Counter | `copilot_admin_list_pending_total` | `copilot.admin_list_pending_total` | `admin` | Admin list pending approvals |
| `admin_search_users_total` | Counter | `copilot_admin_search_users_total` | `copilot.admin_search_users_total` | `admin`, `search_by` | `search_by` is a bounded enum |
| `admin_view_roles_total` | Counter | `copilot_admin_view_roles_total` | `copilot.admin_view_roles_total` | `admin` | Admin views roles |
| `admin_assign_roles_total` | Counter | `copilot_admin_assign_roles_total` | `copilot.admin_assign_roles_total` | `admin`, `roles` | `roles` is a comma-joined list; keep role sets small to avoid high cardinality |
| `admin_revoke_roles_total` | Counter | `copilot_admin_revoke_roles_total` | `copilot.admin_revoke_roles_total` | `admin`, `roles` | Same caveat as above |

### Ingestion service

Common source tags:
- `source_name`
- `source_type`

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `ingestion_files_total` | Counter | `copilot_ingestion_files_total` | `copilot.ingestion_files_total` | `source_name`, `source_type`, `status` | `status` is `success` or `skipped` |
| `ingestion_documents_total` | Counter | `copilot_ingestion_documents_total` | `copilot.ingestion_documents_total` | `source_name`, `source_type`, `status` | Currently increments on successful archive ingestion |
| `ingestion_file_size_bytes` | Histogram | `copilot_ingestion_file_size_bytes` | `copilot.ingestion_file_size_bytes` | `source_name`, `source_type` | Observed per ingested file |
| `ingestion_sources_total` | Counter | `copilot_ingestion_sources_total` | `copilot.ingestion_sources_total` | `source_name`, `source_type`, `status` | `status` is `success` or `failure` |
| `ingestion_duration_seconds` | Histogram | `copilot_ingestion_duration_seconds` | `copilot.ingestion_duration_seconds` | `source_name`, `source_type` | Duration of ingesting a single source |
| `ingestion_files_processed` | Gauge | `copilot_ingestion_files_processed` | `copilot.ingestion_files_processed` | `source_name`, `source_type` | Latest per-run processed count |
| `ingestion_files_skipped` | Gauge | `copilot_ingestion_files_skipped` | `copilot.ingestion_files_skipped` | `source_name`, `source_type` | Latest per-run skipped count |
| `ingestion_deduplication_check_failed_total` | Counter | `copilot_ingestion_deduplication_check_failed_total` | `copilot.ingestion_deduplication_check_failed_total` | (none) | Document store query for deduplication failed |
| `ingestion_archive_status_transitions_total` | Counter | `copilot_ingestion_archive_status_transitions_total` | `copilot.ingestion_archive_status_transitions_total` | `status`, `collection` | `collection` is currently `archives` |

### Parsing service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `parsing_archives_processed_total` | Counter | `copilot_parsing_archives_processed_total` | `copilot.parsing_archives_processed_total` | `status` | `status` is `success` or `failed` |
| `parsing_messages_parsed_total` | Counter | `copilot_parsing_messages_parsed_total` | `copilot.parsing_messages_parsed_total` | (none) | Count of messages parsed |
| `parsing_threads_created_total` | Counter | `copilot_parsing_threads_created_total` | `copilot.parsing_threads_created_total` | (none) | Count of threads created |
| `parsing_duration_seconds` | Histogram | `copilot_parsing_duration_seconds` | `copilot.parsing_duration_seconds` | (none) | Duration of parsing an archive |
| `parsing_failures_total` | Counter | `copilot_parsing_failures_total` | `copilot.parsing_failures_total` | `error_type` | Error classification |
| `parsing_messages_skipped_total` | Counter | `copilot_parsing_messages_skipped_total` | `copilot.parsing_messages_skipped_total` | `reason` | `reason`: `empty_body`, `validation_error`, `duplicate` |
| `parsing_threads_skipped_total` | Counter | `copilot_parsing_threads_skipped_total` | `copilot.parsing_threads_skipped_total` | `reason` | `reason`: `validation_error`, `duplicate` |
| `parsing_archive_status_transitions_total` | Counter | `copilot_parsing_archive_status_transitions_total` | `copilot.parsing_archive_status_transitions_total` | `status`, `collection` | `collection` is currently `archives` |

### Chunking service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `startup_requeue_documents_total` | Counter | `copilot_startup_requeue_documents_total` | `copilot.startup_requeue_documents_total` | `collection` | Used by startup requeue paths |
| `startup_requeue_errors_total` | Counter | `copilot_startup_requeue_errors_total` | `copilot.startup_requeue_errors_total` | `collection`, `error_type` | Used by startup requeue paths |
| `chunking_messages_processed_total` | Counter | `copilot_chunking_messages_processed_total` | `copilot.chunking_messages_processed_total` | `status` | Current status emitted is `success` |
| `chunking_chunks_created_total` | Counter | `copilot_chunking_chunks_created_total` | `copilot.chunking_chunks_created_total` | (none) | Total chunks created |
| `chunking_duration_seconds` | Histogram | `copilot_chunking_duration_seconds` | `copilot.chunking_duration_seconds` | (none) | Batch chunking duration |
| `chunking_chunk_size_tokens` | Histogram | `copilot_chunking_chunk_size_tokens` | `copilot.chunking_chunk_size_tokens` | (none) | Average tokens per chunk (observed once per batch) |
| `chunking_failures_total` | Counter | `copilot_chunking_failures_total` | `copilot.chunking_failures_total` | `error_type` | Error classification |
| `chunking_chunk_status_transitions_total` | Counter | `copilot_chunking_chunk_status_transitions_total` | `copilot.chunking_chunk_status_transitions_total` | `embedding_generated`, `collection` | Used for chunk embedding status transitions (`collection=chunks`) |

### Embedding service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `embedding_chunks_processed_total` | Counter | `copilot_embedding_chunks_processed_total` | `copilot.embedding_chunks_processed_total` | (none) | Number of embeddings generated |
| `embedding_generation_duration_seconds` | Histogram | `copilot_embedding_generation_duration_seconds` | `copilot.embedding_generation_duration_seconds` | (none) | Total processing duration |
| `embedding_failures_total` | Counter | `copilot_embedding_failures_total` | `copilot.embedding_failures_total` | `error_type` | Error classification |
| `vector_store_documents_total` | Counter | `copilot_vector_store_documents_total` | `copilot.vector_store_documents_total` | (none) | Number of embeddings stored in vector store |
| `embedding_chunk_status_transitions_total` | Counter | `copilot_embedding_chunk_status_transitions_total` | `copilot.embedding_chunk_status_transitions_total` | `embedding_generated`, `collection` | Used for chunk embedding status transitions (`collection=chunks`) |

### Orchestrator service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `startup_requeue_errors_total` | Counter | `copilot_startup_requeue_errors_total` | `copilot.startup_requeue_errors_total` | `collection`, `error_type` | Startup requeue errors for `threads` |
| `orchestrator_summary_skipped_total` | Counter | `copilot_orchestrator_summary_skipped_total` | `copilot.orchestrator_summary_skipped_total` | `reason` | e.g. `summary_already_exists` |
| `orchestrator_summary_triggered_total` | Counter | `copilot_orchestrator_summary_triggered_total` | `copilot.orchestrator_summary_triggered_total` | `reason` | e.g. `chunks_changed` |
| `orchestration_events_total` | Counter | `copilot_orchestration_events_total` | `copilot.orchestration_events_total` | `event_type`, `outcome` | Tracks orchestration publish outcomes |
| `orchestration_failures_total` | Counter | `copilot_orchestration_failures_total` | `copilot.orchestration_failures_total` | `error_type` | Error classification |

### Summarization service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `summarization_events_total` | Counter | `copilot_summarization_events_total` | `copilot.summarization_events_total` | `event_type`, `outcome` | Typically `event_type=requested` |
| `summarization_latency_seconds` | Histogram | `copilot_summarization_latency_seconds` | `copilot.summarization_latency_seconds` | (none) | End-to-end summarization duration |
| `summarization_llm_calls_total` | Counter | `copilot_summarization_llm_calls_total` | `copilot.summarization_llm_calls_total` | `backend`, `model` | LLM request count |
| `summarization_tokens_total` | Counter | `copilot_summarization_tokens_total` | `copilot.summarization_tokens_total` | `type` | `type` is `prompt` or `completion` |
| `summarization_failures_total` | Counter | `copilot_summarization_failures_total` | `copilot.summarization_failures_total` | `error_type` | Error classification |

### Reporting service

| Base name | Type | Prometheus | Azure/OTel | Dimensions (tags) | Notes |
|---|---|---|---|---|---|
| `reporting_events_total` | Counter | `copilot_reporting_events_total` | `copilot.reporting_events_total` | `event_type`, `outcome` | Tracks event handling |
| `reporting_latency_seconds` | Histogram | `copilot_reporting_latency_seconds` | `copilot.reporting_latency_seconds` | (none) | End-to-end processing duration |
| `reporting_failures_total` | Counter | `copilot_reporting_failures_total` | `copilot.reporting_failures_total` | `error_type` | Error classification |
| `reporting_delivery_total` | Counter | `copilot_reporting_delivery_total` | `copilot.reporting_delivery_total` | `channel`, `status` | e.g. `channel=webhook`, `status=success|failed` |

## Prometheus exporter metrics (scripts)

### Qdrant exporter

Exposed by `scripts/qdrant_exporter.py`.

| Prometheus name | Type | Labels | Notes |
|---|---|---|---|
| `qdrant_collection_vectors_count` | Gauge | `collection` | Vectors per collection |
| `qdrant_collection_size_bytes` | Gauge | `collection` | Collection disk size |
| `qdrant_collection_indexed_vectors_count` | Gauge | `collection` | Indexed vectors |
| `qdrant_collection_segments_count` | Gauge | `collection` | Segment count |
| `qdrant_memory_usage_bytes` | Gauge | (none) | Best-effort from `/telemetry` |
| `qdrant_scrape_success` | Gauge | (none) | 1 if last scrape succeeded |
| `qdrant_scrape_errors_total` | Counter | (none) | Scrape error count |
| `qdrant_scrape_duration_seconds` | Histogram | (none) | Scrape duration |

### MongoDB document count exporter

Exposed by `scripts/mongo_doc_count_exporter.py`.

| Prometheus name | Type | Labels | Notes |
|---|---|---|---|
| `copilot_collection_document_count` | Gauge | `database`, `collection` | Count per collection |

### MongoDB collStats exporter

Exposed by `scripts/mongo_collstats_exporter.py`.

| Prometheus name | Type | Labels | Notes |
|---|---|---|---|
| `mongodb_collstats_storageSize` | Gauge | `db`, `collection` | Storage size in bytes |
| `mongodb_collstats_count` | Gauge | `db`, `collection` | Document count |
| `mongodb_collstats_avgObjSize` | Gauge | `db`, `collection` | Average object size |
| `mongodb_collstats_totalIndexSize` | Gauge | `db`, `collection` | Total index size |
| `mongodb_collstats_indexSize` | Gauge | `db`, `collection`, `index` | Per-index size |

### Document processing exporter

Exposed by `scripts/document_processing_exporter.py`.

| Prometheus name | Type | Labels | Notes |
|---|---|---|---|
| `copilot_document_status_count` | Gauge | `database`, `collection`, `status` | Documents by status |
| `copilot_document_processing_duration_seconds` | Gauge | `database`, `collection` | Average processing duration |
| `copilot_document_age_seconds` | Gauge | `database`, `collection`, `status` | Average age by status |
| `copilot_document_attempt_count` | Gauge | `database`, `collection` | Average attempt count |
| `copilot_chunks_embedding_status_count` | Gauge | `database`, `embedding_generated` | Chunks by embedding status |
| `copilot_document_exporter_scrape_errors_total` | Gauge | (none) | Scrape errors (note: gauge, not counter) |

### Retry stuck documents job

Emitted by `scripts/retry_stuck_documents.py` to Prometheus Pushgateway.

| Prometheus name | Type | Labels | Notes |
|---|---|---|---|
| `retry_job_documents_requeued_total` | Counter | `collection` | Documents requeued |
| `retry_job_documents_skipped_backoff_total` | Counter | `collection` | Skipped due to backoff |
| `retry_job_documents_max_retries_exceeded_total` | Counter | `collection` | Hit max retries |
| `retry_job_runs_total` | Counter | `status` | Job runs by status |
| `retry_job_errors_total` | Counter | `error_type` | Errors by type |
| `retry_job_stuck_documents` | Gauge | `collection` | Current stuck docs |
| `retry_job_failed_documents` | Gauge | `collection` | Current failed docs |
| `retry_job_duration_seconds` | Histogram | (none) | Duration per run |
