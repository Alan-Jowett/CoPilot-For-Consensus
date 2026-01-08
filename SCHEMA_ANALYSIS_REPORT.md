# Schema Configuration Analysis Report

## Executive Summary
Analysis of 8 service schema files (docs/schemas/configs/*.json) revealing discriminant fields (adapter selectors), their supported adapters, and environment variable naming patterns.

**Key Finding**: Widespread use of generic environment variable names instead of adapter-specific prefixes. This creates ambiguity when multiple adapters are available for the same discriminant.

---

## Analysis by Service

### 1. **AUTH Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `SECRET_PROVIDER_TYPE` | `local` (implicit default) | *(none - uses secret store directly)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `SECRET_PROVIDER_TYPE` | `vault` | *(none - env-based)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `METRICS_TYPE` | `prometheus` | `PROMETHEUS_PUSHGATEWAY` (conditional) | ⚠ MIXED | `PROMETHEUS_PUSHGATEWAY` | 0 |
| `METRICS_TYPE` | `pushgateway` | `PROMETHEUS_PUSHGATEWAY` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `METRICS_TYPE` | `azure_monitor` | *(none in schema)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `METRICS_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `AUTH_ROLE_STORE_TYPE` | `mongodb` | `AUTH_ROLE_STORE_HOST`, `AUTH_ROLE_STORE_PORT`, `AUTH_ROLE_STORE_USERNAME`, `AUTH_ROLE_STORE_PASSWORD`, `AUTH_ROLE_STORE_DATABASE`, `AUTH_ROLE_STORE_COLLECTION`, `AUTH_ROLE_STORE_SCHEMA_DIR` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `AUTH_ROLE_STORE_TYPE` | `cosmosdb` | `AUTH_ROLE_STORE_HOST`, `AUTH_ROLE_STORE_PORT`, `AUTH_ROLE_STORE_USERNAME`, `AUTH_ROLE_STORE_PASSWORD`, `AUTH_ROLE_STORE_DATABASE`, `AUTH_ROLE_STORE_COLLECTION`, `AUTH_ROLE_STORE_SCHEMA_DIR` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `AUTH_ROLE_STORE_TYPE` | `memory` | `AUTH_ROLE_STORE_SCHEMA_DIR` | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Auth Assessment**: ✅ **GOOD** - Already uses adapter-specific prefixes (e.g., `AUTH_ROLE_STORE_*`, `PROMETHEUS_PUSHGATEWAY`)

---

### 2. **CHUNKING Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `ERROR_REPORTER_TYPE` | `sentry` | `SENTRY_DSN`, `SENTRY_ENVIRONMENT` (not in this schema, but in ingestion) | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Chunking Assessment**: ❌ **POOR** - Uses generic `MESSAGE_BUS_*` and `DOCUMENT_DATABASE_*` names. **8 vars need renaming**

---

### 3. **EMBEDDING Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `VECTOR_STORE_TYPE` | `qdrant` | `VECTOR_DATABASE_HOST`, `VECTOR_DATABASE_PORT`, `VECTOR_DATABASE_COLLECTION`, `VECTOR_STORE_DISTANCE`, `VECTOR_STORE_BATCH_SIZE` | ❌ **GENERIC** | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION`, `QDRANT_DISTANCE`, `QDRANT_BATCH_SIZE` | 5 |
| `VECTOR_STORE_TYPE` | `aisearch` | `AISEARCH_ENDPOINT`, `AISEARCH_INDEX_NAME`, `AISEARCH_API_KEY`, `AISEARCH_USE_MANAGED_IDENTITY` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `VECTOR_STORE_TYPE` | `pinecone` | *(not found in schema)* | ? UNKNOWN | ? | ? |
| `EMBEDDING_BACKEND` | `sentencetransformers` | `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `BATCH_SIZE`, `DEVICE` | ❌ **GENERIC** | `SENTENCETRANSFORMERS_MODEL`, `EMBEDDING_DIMENSION`, `SENTENCETRANSFORMERS_BATCH_SIZE`, `SENTENCETRANSFORMERS_DEVICE` | 3 |
| `EMBEDDING_BACKEND` | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `EMBEDDING_BACKEND` | `ollama` | `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `BATCH_SIZE`, `DEVICE` | ❌ **GENERIC** | `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_BATCH_SIZE`, `OLLAMA_DEVICE` | 4 |
| `ERROR_REPORTER_TYPE` | `sentry` | `SENTRY_DSN`, `SENTRY_ENVIRONMENT` (not in schema) | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Embedding Assessment**: ❌ **VERY POOR** - Multiple discriminants with generic names. **17 vars need renaming**

---

### 4. **INGESTION Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `ARCHIVE_STORE_TYPE` | `local` | `ARCHIVE_STORE_PATH` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ARCHIVE_STORE_TYPE` | `azureblob` | `ARCHIVE_STORE_CONNECTION_STRING`, `ARCHIVE_STORE_ACCOUNT_NAME`, `ARCHIVE_STORE_CONTAINER` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `inmemory` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `sentry` | `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `console`/`silent` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Ingestion Assessment**: ❌ **FAIR** - Archive store naming is good, but message bus and document store use generics. **9 vars need renaming**

---

### 5. **ORCHESTRATOR Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `LLM_BACKEND` | `ollama` | `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | ❌ **GENERIC** | `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TEMPERATURE`, `OLLAMA_MAX_TOKENS` | 4 |
| `LLM_BACKEND` | `llamacpp` | `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | ❌ **GENERIC** | `LLAMACPP_HOST`, `LLAMACPP_MODEL`, `LLAMACPP_TEMPERATURE`, `LLAMACPP_MAX_TOKENS` | 4 |
| `LLM_BACKEND` | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `sentry` | *(not in schema)* | ? UNKNOWN | ? | ? |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Orchestrator Assessment**: ❌ **VERY POOR** - LLM backend especially problematic (shares generic names across 2 adapters). **18 vars need renaming**

---

### 6. **PARSING Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `ARCHIVE_STORE_TYPE` | `local` | `ARCHIVE_STORE_PATH` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ARCHIVE_STORE_TYPE` | `azureblob` | `ARCHIVE_STORE_CONNECTION_STRING`, `ARCHIVE_STORE_ACCOUNT_NAME`, `ARCHIVE_STORE_CONTAINER` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `sentry` | *(not in schema)* | ? UNKNOWN | ? | ? |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Parsing Assessment**: ❌ **FAIR** - Archive store good, but message bus and document store generic. **18 vars need renaming**

---

### 7. **REPORTING Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `VECTOR_STORE_TYPE` | `qdrant` | `VECTOR_DATABASE_HOST`, `VECTOR_DATABASE_PORT`, `VECTOR_DATABASE_COLLECTION` | ❌ **GENERIC** | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION` | 3 |
| `VECTOR_STORE_TYPE` | `aisearch` | `AISEARCH_ENDPOINT`, `AISEARCH_INDEX_NAME`, `AISEARCH_API_KEY`, `AISEARCH_USE_MANAGED_IDENTITY` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `EMBEDDING_BACKEND` | `sentencetransformers` | `EMBEDDING_MODEL`, `DEVICE` | ❌ **GENERIC** | `SENTENCETRANSFORMERS_MODEL`, `SENTENCETRANSFORMERS_DEVICE` | 2 |
| `EMBEDDING_BACKEND` | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `sentry` | *(not in schema)* | ? UNKNOWN | ? | ? |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Reporting Assessment**: ❌ **VERY POOR** - Multiple discriminants with generic names across all major adapters. **23 vars need renaming**

---

### 8. **SUMMARIZATION Service**

| Discriminant | Adapter | Env Vars Used | Status | Should Be | Rename Count |
|---|---|---|---|---|---|
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | 4 |
| `MESSAGE_BUS_TYPE` | `servicebus` | `MESSAGE_BUS_HOST`, `MESSAGE_BUS_PORT`, `MESSAGE_BUS_USER`, `MESSAGE_BUS_PASSWORD` | ❌ **GENERIC** | `SERVICEBUS_HOST`, `SERVICEBUS_PORT`, `SERVICEBUS_USER`, `SERVICEBUS_PASSWORD` | 4 |
| `DOCUMENT_STORE_TYPE` | `mongodb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_NAME`, `MONGODB_USER`, `MONGODB_PASSWORD` | 5 |
| `DOCUMENT_STORE_TYPE` | `cosmosdb` | `DOCUMENT_DATABASE_HOST`, `DOCUMENT_DATABASE_PORT`, `DOCUMENT_DATABASE_NAME`, `DOCUMENT_DATABASE_USER`, `DOCUMENT_DATABASE_PASSWORD` | ❌ **GENERIC** | `COSMOSDB_HOST`, `COSMOSDB_PORT`, `COSMOSDB_NAME`, `COSMOSDB_USER`, `COSMOSDB_PASSWORD` | 5 |
| `VECTOR_STORE_TYPE` | `qdrant` | `VECTOR_DATABASE_HOST`, `VECTOR_DATABASE_PORT`, `VECTOR_DATABASE_COLLECTION`, `VECTOR_STORE_DISTANCE`, `VECTOR_STORE_BATCH_SIZE` | ❌ **GENERIC** | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION`, `QDRANT_DISTANCE`, `QDRANT_BATCH_SIZE` | 5 |
| `VECTOR_STORE_TYPE` | `aisearch` | `AISEARCH_ENDPOINT`, `AISEARCH_INDEX_NAME`, `AISEARCH_API_KEY`, `AISEARCH_USE_MANAGED_IDENTITY` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `LLM_BACKEND` | `ollama` (labeled `local`) | `OLLAMA_HOST`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | ❌ **MIXED** | `OLLAMA_HOST` ✓, but `OLLAMA_MODEL`, `OLLAMA_TEMPERATURE`, `OLLAMA_MAX_TOKENS` | 3 |
| `LLM_BACKEND` | `llamacpp` | `LLAMACPP_HOST`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | ❌ **MIXED** | `LLAMACPP_HOST` ✓, but `LLAMACPP_MODEL`, `LLAMACPP_TEMPERATURE`, `LLAMACPP_MAX_TOKENS` | 3 |
| `LLM_BACKEND` | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `LLM_BACKEND` | `mock` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `EMBEDDING_BACKEND` | `sentencetransformers` | `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` | ❌ **GENERIC** | `SENTENCETRANSFORMERS_MODEL`, `SENTENCETRANSFORMERS_DIMENSION` | 2 |
| `EMBEDDING_BACKEND` | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | ✓ ADAPTER-SPECIFIC | N/A | 0 |
| `ERROR_REPORTER_TYPE` | `sentry` | *(not in schema)* | ? UNKNOWN | ? | ? |
| `ERROR_REPORTER_TYPE` | `noop` | *(none)* | ✓ ADAPTER-SPECIFIC | N/A | 0 |

**Summarization Assessment**: ❌ **VERY POOR** - Even worse: `OLLAMA_HOST` and `LLAMACPP_HOST` are adapter-specific but `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` are generic across multiple adapters. **31 vars need renaming/refactoring**

---

## Summary Statistics

| Service | Discriminants | Total Adapters | Generic Env Vars | Rename Count | Severity |
|---|---|---|---|---|---|
| **auth** | 3 | 8 | 0 | **0** | ✅ GOOD |
| **chunking** | 2 | 4 | 8 | **8** | ❌ POOR |
| **embedding** | 3 | 6 | 13 | **17** | ❌ VERY POOR |
| **ingestion** | 3 | 5 | 9 | **9** | ❌ FAIR |
| **orchestrator** | 3 | 5 | 18 | **18** | ❌ VERY POOR |
| **parsing** | 3 | 5 | 14 | **18** | ❌ FAIR |
| **reporting** | 4 | 7 | 19 | **23** | ❌ VERY POOR |
| **summarization** | 4 | 8 | 24 | **31** | ❌ VERY POOR |
| **TOTALS** | **25** | **48** | **105** | **124** | ⚠️ CRITICAL |

---

## Root Cause Analysis

### Problem 1: Shared Generic Names Across Multiple Adapters
The most egregious pattern is using the same environment variable names for different adapters:

```
MESSAGE_BUS_TYPE = rabbitmq → MESSAGE_BUS_HOST, MESSAGE_BUS_PORT, ...
MESSAGE_BUS_TYPE = servicebus → MESSAGE_BUS_HOST, MESSAGE_BUS_PORT, ... (SAME VARS!)
```

**Issue**: Can't reliably pass different configs for different adapters without adapter detection logic.

### Problem 2: Inconsistent Adapter-Specific Naming
Some adapters get proper prefixes, others don't:

```
✓ GOOD:    AISEARCH_ENDPOINT, AISEARCH_API_KEY (for aisearch adapter)
✓ GOOD:    AZURE_OPENAI_* (for azure adapter)
✗ BAD:     VECTOR_DATABASE_HOST (generic, used by both qdrant and aisearch)
✗ BAD:     EMBEDDING_MODEL (generic, used by sentencetransformers, ollama, and azure)
```

### Problem 3: Partial Application of Adapter Prefixes
Summarization service shows this clearly:

```
LLM_BACKEND = ollama
  ✓ OLLAMA_HOST (adapter-specific)
  ✗ LLM_MODEL (generic, shared with llamacpp)
  ✗ LLM_TEMPERATURE (generic, shared with llamacpp)
  ✗ LLM_MAX_TOKENS (generic, shared with llamacpp)
```

---

## Discriminant Field Summary

### All Discriminants Identified (Unique)

1. **SECRET_PROVIDER_TYPE** (auth)
   - Adapters: `local`, `vault`
   - ✓ Well-designed (no env vars needed; secrets stored differently)

2. **METRICS_TYPE** (auth, chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization)
   - Adapters: `prometheus`, `pushgateway`, `azure_monitor`, `noop`
   - Status: ✓ OK (mostly implicit; `PROMETHEUS_PUSHGATEWAY` is adapter-specific)

3. **AUTH_ROLE_STORE_TYPE** (auth)
   - Adapters: `mongodb`, `cosmosdb`, `memory`
   - ✓ Adapter-specific prefix: `AUTH_ROLE_STORE_*`

4. **MESSAGE_BUS_TYPE** (chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization)
   - Adapters: `rabbitmq`, `servicebus`
   - ❌ Uses generic `MESSAGE_BUS_*` across all adapters
   - **FIX**: `RABBITMQ_*` and `SERVICEBUS_*`

5. **DOCUMENT_STORE_TYPE** (chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization)
   - Adapters: `mongodb`, `cosmosdb`, `inmemory`
   - ❌ Uses generic `DOCUMENT_DATABASE_*` across all adapters
   - **FIX**: `MONGODB_*` and `COSMOSDB_*`

6. **VECTOR_STORE_TYPE** (embedding, reporting, summarization)
   - Adapters: `qdrant`, `aisearch`, `pinecone` (implied in summary, not in schema)
   - ❌ Mixes generic `VECTOR_DATABASE_*` (for qdrant) with `AISEARCH_*` (for aisearch)
   - **FIX**: Standardize to `QDRANT_*`, `AISEARCH_*`, `PINECONE_*`

7. **ARCHIVE_STORE_TYPE** (ingestion, parsing)
   - Adapters: `local`, `azureblob`
   - ✓ Adapter-specific: `ARCHIVE_STORE_*` is generic but `ARCHIVE_STORE_CONNECTION_STRING`, `ARCHIVE_STORE_ACCOUNT_NAME`, `ARCHIVE_STORE_CONTAINER` are distinct enough

8. **EMBEDDING_BACKEND** (embedding, reporting, summarization)
   - Adapters: `sentencetransformers`, `azure`, `ollama`, (implied others)
   - ❌ Uses generic `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `DEVICE` across all adapters
   - **FIX**: `SENTENCETRANSFORMERS_MODEL`, `AZURE_OPENAI_MODEL`, `OLLAMA_MODEL`, etc.

9. **LLM_BACKEND** (orchestrator, summarization)
   - Adapters: `ollama` (local), `llamacpp`, `azure`, `mock`, (implied `openai`)
   - ❌ Uses generic `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` across adapters
   - ⚠️ Partially better in summarization: `OLLAMA_HOST`, `LLAMACPP_HOST` but still shares other vars
   - **FIX**: `OLLAMA_*`, `LLAMACPP_*`, `AZURE_OPENAI_*`, etc.

10. **ERROR_REPORTER_TYPE** (chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization)
    - Adapters: `sentry`, `noop`, `console`, `silent`
    - ✓ Adapter-specific: Uses `SENTRY_*` for sentry, none for others (implicit no-op)

---

## Recommendations

### Immediate Actions (High Priority)

1. **Rename MESSAGE_BUS_TYPE environment variables**
   - Replace `MESSAGE_BUS_HOST` → `RABBITMQ_HOST` or `SERVICEBUS_HOST` (adapter-dependent)
   - Replace `MESSAGE_BUS_PORT` → `RABBITMQ_PORT` or `SERVICEBUS_PORT`
   - Replace `MESSAGE_BUS_USER` → `RABBITMQ_USER` or `SERVICEBUS_USER`
   - Replace `MESSAGE_BUS_PASSWORD` → `RABBITMQ_PASSWORD` or `SERVICEBUS_PASSWORD`
   - **Impact**: 7 services × 4 vars = 28 env var changes across schemas and code

2. **Rename DOCUMENT_STORE_TYPE environment variables**
   - Replace `DOCUMENT_DATABASE_HOST` → `MONGODB_HOST` or `COSMOSDB_HOST`
   - Replace `DOCUMENT_DATABASE_PORT` → `MONGODB_PORT` or `COSMOSDB_PORT`
   - Replace `DOCUMENT_DATABASE_NAME` → `MONGODB_DATABASE_NAME` or `COSMOSDB_DATABASE_NAME`
   - Replace `DOCUMENT_DATABASE_USER` → `MONGODB_USER` or `COSMOSDB_USER`
   - Replace `DOCUMENT_DATABASE_PASSWORD` → `MONGODB_PASSWORD` or `COSMOSDB_PASSWORD`
   - **Impact**: 7 services × 5 vars = 35 env var changes

3. **Rename VECTOR_STORE_TYPE environment variables**
   - Standardize across: `qdrant` (QDRANT_*), `aisearch` (AISEARCH_*), `pinecone` (PINECONE_*)
   - Replace `VECTOR_DATABASE_*` → adapter-specific
   - **Impact**: 3 services × 3+ vars = ~15 env var changes

4. **Refactor EMBEDDING_BACKEND environment variables**
   - Adapter-specific: `SENTENCETRANSFORMERS_*`, `OLLAMA_*`, `AZURE_OPENAI_*`
   - **Impact**: 3 services × 4+ vars = ~12 env var changes

5. **Refactor LLM_BACKEND environment variables**
   - Adapter-specific: `OLLAMA_*`, `LLAMACPP_*`, `AZURE_OPENAI_*`, `OPENAI_*`
   - Partial fix needed in summarization.json (already has `OLLAMA_HOST`, `LLAMACPP_HOST`)
   - **Impact**: 2 services × 4 vars = 8 env var changes

### Phase-in Strategy

**Phase 1** (Quick wins):
- Fix `MESSAGE_BUS_TYPE` and `DOCUMENT_STORE_TYPE` first (most services, clearest pattern)

**Phase 2** (Medium effort):
- Fix `VECTOR_STORE_TYPE` and `EMBEDDING_BACKEND`

**Phase 3** (Complex):
- Fix `LLM_BACKEND` (involves orchestrator and summarization, more complex logic)

### Documentation Impact

- Update all service README.md files with new env var names
- Update docker-compose.yml (if using generic names)
- Update any adapter documentation (adapters/*/README.md)
- Update CONFIG_GUIDE.md (if it exists)
- Update example .env files

---

## Conclusion

**Critical Issue**: The system has **124 environment variables that should be renamed** to follow adapter-specific naming conventions. The current generic naming makes it difficult to:

1. **Run multiple adapters simultaneously** (e.g., debugging one implementation)
2. **Configure different adapters per environment** (dev → local, prod → Azure)
3. **Auto-validate configurations** (can't distinguish which vars apply to which adapter)
4. **Maintain code clarity** (developers can't tell which env var belongs to which adapter)

Recommendation: **Prioritize Phase 1** (MESSAGE_BUS and DOCUMENT_STORE) as these affect all 7+ services and represent the highest impact fix.
