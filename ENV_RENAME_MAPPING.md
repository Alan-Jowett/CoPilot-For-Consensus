# Comprehensive Environment Variable Rename Mapping

**Total Variables: 124**  
**Organization: By Discriminant Type (Driver Variables)**

---

## Overview

This document provides a complete rename mapping for all 124 environment variables in the Copilot-for-Consensus project. Each variable is mapped from its current name to a new adapter-prefixed name, with detailed information about:

- **Exact old name** (as it appears in current schemas)
- **Exact new name** (adapter-prefixed)
- **Services** that use it (auth, chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization)
- **Files to update** (schema JSON, docker-compose.yml, bicep templates)
- **Notes** on special handling or conditions

---

## 1. MESSAGE_BUS_TYPE - Discriminant Driver

**Driver Variable:** `MESSAGE_BUS_TYPE`  
**Allowed Values:** `rabbitmq`, `servicebus` (Azure)  
**Used By:** chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization (7 services)

### 1.1 Discriminant Variable (No Rename)

```
MESSAGE_BUS_TYPE → MESSAGE_BUS_TYPE | Services: all message-bus-using services | Files: schema, compose
```

**Note:** Keep as-is; it determines which adapter set to use below.

### 1.2 Generic Message Bus Variables (Will be renamed based on discriminant)

```
MESSAGE_BUS_HOST → {RABBITMQ_HOST | SERVICEBUS_HOST} | Services: all | Files: schema, compose
MESSAGE_BUS_PORT → {RABBITMQ_PORT | SERVICEBUS_PORT} | Services: all | Files: schema, compose
```

**Note:** These are generic in schemas but should be renamed conditionally in code. Recommend keeping schema generic but renaming in compose files.

### 1.3 RabbitMQ-Specific Variables (Direct rename)

```
MESSAGE_BUS_HOST → RABBITMQ_HOST (when MESSAGE_BUS_TYPE=rabbitmq) | Services: all | Files: compose, code
MESSAGE_BUS_PORT → RABBITMQ_PORT (when MESSAGE_BUS_TYPE=rabbitmq) | Services: all | Files: compose, code
message_bus_user (secret) → rabbitmq_user (secret) | Services: all | Files: compose secrets
message_bus_password (secret) → rabbitmq_password (secret) | Services: all | Files: compose secrets
```

**Files:**
- `docker-compose.yml`: Rename env vars and secret names in all service definitions
- Schema files: Consider adding adapter-specific variants or document conditional behavior

### 1.4 Azure Service Bus-Specific Variables

```
MESSAGE_BUS_HOST → SERVICEBUS_HOST (when MESSAGE_BUS_TYPE=servicebus) | Services: all | Files: compose
MESSAGE_BUS_PORT → SERVICEBUS_PORT (when MESSAGE_BUS_TYPE=servicebus) | Services: all | Files: compose
MESSAGE_BUS_USE_MANAGED_IDENTITY → SERVICEBUS_USE_MANAGED_IDENTITY | Services: all | Files: compose, bicep
MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE → SERVICEBUS_FULLY_QUALIFIED_NAMESPACE | Services: all | Files: compose, bicep, code
```

**Note:** These variables don't exist yet in schemas but are needed for Azure Service Bus support.

**Bicep File:** `infra/azure/modules/servicebus.bicep` - Already uses `SERVICEBUS_*` pattern; ensure consistency.

### Summary Table: MESSAGE_BUS_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| MESSAGE_BUS_TYPE | MESSAGE_BUS_TYPE | Driver (no change) | all | schema, compose |
| MESSAGE_BUS_HOST | RABBITMQ_HOST | if type=rabbitmq | all | compose |
| MESSAGE_BUS_HOST | SERVICEBUS_HOST | if type=servicebus | all | compose, bicep |
| MESSAGE_BUS_PORT | RABBITMQ_PORT | if type=rabbitmq | all | compose |
| MESSAGE_BUS_PORT | SERVICEBUS_PORT | if type=servicebus | all | compose |
| message_bus_user | rabbitmq_user | rabbitmq only | all | compose (secrets) |
| message_bus_password | rabbitmq_password | rabbitmq only | all | compose (secrets) |
| (new) | SERVICEBUS_USE_MANAGED_IDENTITY | servicebus only | all | compose, bicep |
| (new) | SERVICEBUS_FULLY_QUALIFIED_NAMESPACE | servicebus only | all | compose, bicep |

---

## 2. DOCUMENT_STORE_TYPE - Discriminant Driver

**Driver Variable:** `DOCUMENT_STORE_TYPE`  
**Allowed Values:** `mongodb`, `cosmosdb` (Azure)  
**Used By:** chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization (7 services)

### 2.1 Discriminant Variable (No Rename)

```
DOCUMENT_STORE_TYPE → DOCUMENT_STORE_TYPE | Services: all | Files: schema, compose
```

**Note:** Keep as-is; determines adapter.

### 2.2 MongoDB-Specific Variables

```
DOCUMENT_DATABASE_HOST → MONGODB_HOST (when DOCUMENT_STORE_TYPE=mongodb) | Services: all | Files: compose, code
DOCUMENT_DATABASE_PORT → MONGODB_PORT (when DOCUMENT_STORE_TYPE=mongodb) | Services: all | Files: compose, code
DOCUMENT_DATABASE_NAME → MONGODB_DATABASE | Services: all | Files: compose, code
document_database_user (secret) → mongodb_user (secret) | Services: all | Files: compose (secrets)
document_database_password (secret) → mongodb_password (secret) | Services: all | Files: compose (secrets)
```

### 2.3 Azure Cosmos DB-Specific Variables (Standardize to COSMOS_ prefix)

```
DOCUMENT_DATABASE_HOST → COSMOS_HOST (when DOCUMENT_STORE_TYPE=cosmosdb) | Services: all | Files: compose, code, bicep
DOCUMENT_DATABASE_PORT → COSMOS_PORT (when DOCUMENT_STORE_TYPE=cosmosdb) | Services: all | Files: compose, code, bicep
DOCUMENT_DATABASE_NAME → COSMOS_DATABASE | Services: all | Files: compose, code, bicep
document_database_user (secret) → cosmos_user (secret) | Services: all | Files: compose, bicep (secrets)
document_database_password (secret) → cosmos_password (secret) | Services: all | Files: compose, bicep (secrets)
```

**Note:** Bicep files already use `COSMOS_DB_*` pattern. Standardize to `COSMOS_*` in all files for consistency.

**Bicep Files:** `infra/azure/modules/cosmos.bicep` - Adjust to output `COSMOS_HOST`, `COSMOS_PORT`, `COSMOS_DATABASE`, `COSMOS_USER`, `COSMOS_PASSWORD`.

### Summary Table: DOCUMENT_STORE_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| DOCUMENT_STORE_TYPE | DOCUMENT_STORE_TYPE | Driver (no change) | all | schema, compose |
| DOCUMENT_DATABASE_HOST | MONGODB_HOST | if type=mongodb | all | compose, code |
| DOCUMENT_DATABASE_HOST | COSMOS_HOST | if type=cosmosdb | all | compose, code, bicep |
| DOCUMENT_DATABASE_PORT | MONGODB_PORT | if type=mongodb | all | compose, code |
| DOCUMENT_DATABASE_PORT | COSMOS_PORT | if type=cosmosdb | all | compose, code, bicep |
| DOCUMENT_DATABASE_NAME | MONGODB_DATABASE | if type=mongodb | all | compose, code |
| DOCUMENT_DATABASE_NAME | COSMOS_DATABASE | if type=cosmosdb | all | compose, code, bicep |
| document_database_user | mongodb_user | mongodb only | all | compose (secrets) |
| document_database_user | cosmos_user | cosmosdb only | all | compose, bicep (secrets) |
| document_database_password | mongodb_password | mongodb only | all | compose (secrets) |
| document_database_password | cosmos_password | cosmosdb only | all | compose, bicep (secrets) |

---

## 3. VECTOR_STORE_TYPE - Discriminant Driver

**Driver Variable:** `VECTOR_STORE_TYPE`  
**Allowed Values:** `qdrant`, `aisearch`, `pinecone`  
**Used By:** embedding, reporting, summarization (3 services)

### 3.1 Discriminant Variable (No Rename)

```
VECTOR_STORE_TYPE → VECTOR_STORE_TYPE | Services: embedding, reporting, summarization | Files: schema, compose
```

### 3.2 Qdrant-Specific Variables

```
VECTOR_DATABASE_HOST → QDRANT_HOST (when VECTOR_STORE_TYPE=qdrant) | Services: embedding, reporting, summarization | Files: compose, code
VECTOR_DATABASE_PORT → QDRANT_PORT (when VECTOR_STORE_TYPE=qdrant) | Services: embedding, reporting, summarization | Files: compose, code
VECTOR_DATABASE_COLLECTION → QDRANT_COLLECTION (when VECTOR_STORE_TYPE=qdrant) | Services: embedding, reporting, summarization | Files: compose, code
VECTOR_STORE_DISTANCE → QDRANT_DISTANCE (when VECTOR_STORE_TYPE=qdrant) | Services: embedding, summarization | Files: compose, code
VECTOR_STORE_BATCH_SIZE → QDRANT_BATCH_SIZE (when VECTOR_STORE_TYPE=qdrant) | Services: embedding, summarization | Files: compose, code
```

**Note:** Currently in schemas as generic variables. Rename in code to be adapter-aware.

### 3.3 Azure AI Search-Specific Variables (Already prefixed; keep as-is)

```
AISEARCH_ENDPOINT → AISEARCH_ENDPOINT | Services: embedding, summarization | Files: schema, compose, bicep
AISEARCH_INDEX_NAME → AISEARCH_INDEX_NAME | Services: embedding, summarization | Files: schema, compose, bicep
AISEARCH_API_KEY → AISEARCH_API_KEY | Services: embedding, summarization | Files: schema, compose, bicep
AISEARCH_USE_MANAGED_IDENTITY → AISEARCH_USE_MANAGED_IDENTITY | Services: embedding, summarization | Files: schema, compose, bicep
```

**Note:** Already adapter-prefixed; no rename needed. These are distinct from generic vector vars.

### 3.4 Pinecone-Specific Variables (New; to be added)

```
(new) → PINECONE_API_KEY | Services: embedding, summarization | Files: schema, compose, code
(new) → PINECONE_ENVIRONMENT | Services: embedding, summarization | Files: schema, compose, code
(new) → PINECONE_INDEX | Services: embedding, summarization | Files: schema, compose, code
(new) → PINECONE_NAMESPACE | Services: embedding, summarization | Files: schema, compose, code
```

### Summary Table: VECTOR_STORE_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| VECTOR_STORE_TYPE | VECTOR_STORE_TYPE | Driver (no change) | embedding, reporting, summarization | schema, compose |
| VECTOR_DATABASE_HOST | QDRANT_HOST | if type=qdrant | embedding, reporting, summarization | compose, code |
| VECTOR_DATABASE_PORT | QDRANT_PORT | if type=qdrant | embedding, reporting, summarization | compose, code |
| VECTOR_DATABASE_COLLECTION | QDRANT_COLLECTION | if type=qdrant | embedding, summarization | compose, code |
| VECTOR_STORE_DISTANCE | QDRANT_DISTANCE | if type=qdrant | embedding, summarization | compose, code |
| VECTOR_STORE_BATCH_SIZE | QDRANT_BATCH_SIZE | if type=qdrant | embedding, summarization | compose, code |
| AISEARCH_ENDPOINT | AISEARCH_ENDPOINT | if type=aisearch | embedding, summarization | schema, compose, bicep |
| AISEARCH_INDEX_NAME | AISEARCH_INDEX_NAME | if type=aisearch | embedding, summarization | schema, compose, bicep |
| AISEARCH_API_KEY | AISEARCH_API_KEY | if type=aisearch | embedding, summarization | schema, compose, bicep |
| AISEARCH_USE_MANAGED_IDENTITY | AISEARCH_USE_MANAGED_IDENTITY | if type=aisearch | embedding, summarization | schema, compose, bicep |
| (new) | PINECONE_API_KEY | if type=pinecone | embedding, summarization | schema, compose, code |
| (new) | PINECONE_ENVIRONMENT | if type=pinecone | embedding, summarization | schema, compose, code |
| (new) | PINECONE_INDEX | if type=pinecone | embedding, summarization | schema, compose, code |
| (new) | PINECONE_NAMESPACE | if type=pinecone | embedding, summarization | schema, compose, code |

---

## 4. EMBEDDING_BACKEND - Discriminant Driver

**Driver Variable:** `EMBEDDING_BACKEND`  
**Allowed Values:** `sentencetransformers`, `azure`, `ollama`  
**Used By:** embedding, reporting, summarization (3 services)

### 4.1 Discriminant Variable (No Rename)

```
EMBEDDING_BACKEND → EMBEDDING_BACKEND | Services: embedding, reporting, summarization | Files: schema, compose
```

### 4.2 SentenceTransformers-Specific Variables (Rename to SENTENCETRANSFORMERS_*)

```
EMBEDDING_MODEL → SENTENCETRANSFORMERS_MODEL (when EMBEDDING_BACKEND=sentencetransformers) | Services: embedding, reporting, summarization | Files: compose, code
EMBEDDING_DIMENSION → SENTENCETRANSFORMERS_DIMENSION (when EMBEDDING_BACKEND=sentencetransformers) | Services: embedding, summarization | Files: compose, code
BATCH_SIZE → SENTENCETRANSFORMERS_BATCH_SIZE (when EMBEDDING_BACKEND=sentencetransformers) | Services: embedding | Files: compose, code
DEVICE → SENTENCETRANSFORMERS_DEVICE (when EMBEDDING_BACKEND=sentencetransformers) | Services: embedding | Files: compose, code
RETRY_BACKOFF_SECONDS → SENTENCETRANSFORMERS_RETRY_BACKOFF_SECONDS (when EMBEDDING_BACKEND=sentencetransformers) | Services: embedding | Files: compose, code
```

**Note:** These are generic in current schemas but used only by sentencetransformers backend. Rename to avoid confusion with other backends.

### 4.3 Azure OpenAI-Specific Variables (Already prefixed; keep as-is)

```
AZURE_OPENAI_ENDPOINT → AZURE_OPENAI_ENDPOINT | Services: embedding, summarization | Files: schema, compose, bicep
AZURE_OPENAI_API_KEY → AZURE_OPENAI_API_KEY | Services: embedding, summarization | Files: schema, compose, bicep
AZURE_OPENAI_DEPLOYMENT → AZURE_OPENAI_DEPLOYMENT | Services: embedding, summarization | Files: schema, compose, bicep
AZURE_OPENAI_API_VERSION → AZURE_OPENAI_API_VERSION | Services: embedding, summarization | Files: schema, compose, bicep
```

**Note:** Already adapter-prefixed; no rename needed.

### 4.4 Ollama-Specific Variables (Keep as-is)

```
(no embedding-specific ollama vars; uses shared OLLAMA_HOST)
```

### Summary Table: EMBEDDING_BACKEND

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| EMBEDDING_BACKEND | EMBEDDING_BACKEND | Driver (no change) | embedding, reporting, summarization | schema, compose |
| EMBEDDING_MODEL | SENTENCETRANSFORMERS_MODEL | if backend=sentencetransformers | embedding, reporting, summarization | compose, code |
| EMBEDDING_DIMENSION | SENTENCETRANSFORMERS_DIMENSION | if backend=sentencetransformers | embedding, summarization | compose, code |
| BATCH_SIZE | SENTENCETRANSFORMERS_BATCH_SIZE | if backend=sentencetransformers | embedding | compose, code |
| DEVICE | SENTENCETRANSFORMERS_DEVICE | if backend=sentencetransformers | embedding | compose, code |
| RETRY_BACKOFF_SECONDS | SENTENCETRANSFORMERS_RETRY_BACKOFF_SECONDS | if backend=sentencetransformers | embedding | compose, code |
| AZURE_OPENAI_ENDPOINT | AZURE_OPENAI_ENDPOINT | if backend=azure | embedding, summarization | schema, compose, bicep |
| AZURE_OPENAI_API_KEY | AZURE_OPENAI_API_KEY | if backend=azure | embedding, summarization | schema, compose, bicep |
| AZURE_OPENAI_DEPLOYMENT | AZURE_OPENAI_DEPLOYMENT | if backend=azure | embedding, summarization | schema, compose, bicep |
| AZURE_OPENAI_API_VERSION | AZURE_OPENAI_API_VERSION | if backend=azure | embedding, summarization | schema, compose, bicep |

---

## 5. LLM_BACKEND - Discriminant Driver

**Driver Variable:** `LLM_BACKEND`  
**Allowed Values:** `ollama`, `llamacpp`, `azure`  
**Used By:** orchestrator, summarization (2 services)

### 5.1 Discriminant Variable (No Rename)

```
LLM_BACKEND → LLM_BACKEND | Services: orchestrator, summarization | Files: schema, compose
```

### 5.2 Generic LLM Parameters (Recommendation: Keep generic or duplicate per adapter)

**Current Approach (Generic - used by all backends):**

```
LLM_MODEL → LLM_MODEL | Services: orchestrator, summarization | Files: schema, compose
LLM_TEMPERATURE → LLM_TEMPERATURE | Services: orchestrator, summarization | Files: schema, compose
LLM_MAX_TOKENS → LLM_MAX_TOKENS | Services: orchestrator, summarization | Files: schema, compose
LLM_TIMEOUT_SECONDS → LLM_TIMEOUT_SECONDS | Services: orchestrator, summarization | Files: schema, compose
```

**Recommended Approach (Adapter-Specific - avoid generic names):**

```
LLM_MODEL → {OLLAMA_MODEL | LLAMACPP_MODEL | AZURE_OPENAI_DEPLOYMENT} | Services: orchestrator, summarization | Files: schema, compose, code
LLM_TEMPERATURE → {OLLAMA_TEMPERATURE | LLAMACPP_TEMPERATURE | AZURE_OPENAI_TEMPERATURE} | Services: orchestrator, summarization | Files: schema, compose, code
LLM_MAX_TOKENS → {OLLAMA_MAX_TOKENS | LLAMACPP_MAX_TOKENS | AZURE_OPENAI_MAX_TOKENS} | Services: orchestrator, summarization | Files: schema, compose, code
LLM_TIMEOUT_SECONDS → {OLLAMA_TIMEOUT_SECONDS | LLAMACPP_TIMEOUT_SECONDS | AZURE_OPENAI_TIMEOUT_SECONDS} | Services: orchestrator, summarization | Files: schema, compose, code
```

**Decision:** Use **Generic Approach** for backwards compatibility; refactor in Phase 2. Code should handle adapter awareness.

### 5.3 Ollama-Specific Variables (Keep as-is)

```
OLLAMA_HOST → OLLAMA_HOST | Services: orchestrator, summarization, embedding | Files: schema, compose
```

**Note:** Already adapter-prefixed in schemas. Used as fallback for embedding backend too.

### 5.4 llama.cpp-Specific Variables (Keep as-is)

```
LLAMACPP_HOST → LLAMACPP_HOST | Services: orchestrator, summarization | Files: schema, compose
```

**Note:** Already adapter-prefixed in schemas.

### 5.5 Azure OpenAI-Specific Variables (Keep as-is)

```
AZURE_OPENAI_ENDPOINT → AZURE_OPENAI_ENDPOINT | Services: orchestrator, summarization | Files: schema, compose, bicep
AZURE_OPENAI_API_KEY → AZURE_OPENAI_API_KEY | Services: orchestrator, summarization | Files: schema, compose, bicep
AZURE_OPENAI_DEPLOYMENT → AZURE_OPENAI_DEPLOYMENT | Services: orchestrator, summarization | Files: schema, compose, bicep
AZURE_OPENAI_API_VERSION → AZURE_OPENAI_API_VERSION | Services: orchestrator, summarization | Files: schema, compose, bicep
```

**Note:** Already adapter-prefixed; no rename needed. Different from embedding deployment.

### Summary Table: LLM_BACKEND

| Old Name | New Name | Condition | Services | Files | Note |
|----------|----------|-----------|----------|-------|------|
| LLM_BACKEND | LLM_BACKEND | Driver (no change) | orchestrator, summarization | schema, compose | |
| LLM_MODEL | LLM_MODEL | all backends | orchestrator, summarization | schema, compose | Keep generic for Phase 1 |
| LLM_TEMPERATURE | LLM_TEMPERATURE | all backends | orchestrator, summarization | schema, compose | Keep generic for Phase 1 |
| LLM_MAX_TOKENS | LLM_MAX_TOKENS | all backends | orchestrator, summarization | schema, compose | Keep generic for Phase 1 |
| LLM_TIMEOUT_SECONDS | LLM_TIMEOUT_SECONDS | all backends | orchestrator, summarization | schema, compose | Keep generic for Phase 1 |
| OLLAMA_HOST | OLLAMA_HOST | if backend=ollama | orchestrator, summarization | schema, compose | Already prefixed |
| LLAMACPP_HOST | LLAMACPP_HOST | if backend=llamacpp | orchestrator, summarization | schema, compose | Already prefixed |
| AZURE_OPENAI_ENDPOINT | AZURE_OPENAI_ENDPOINT | if backend=azure | orchestrator, summarization | schema, compose, bicep | Already prefixed |
| AZURE_OPENAI_API_KEY | AZURE_OPENAI_API_KEY | if backend=azure | orchestrator, summarization | schema, compose, bicep | Already prefixed |
| AZURE_OPENAI_DEPLOYMENT | AZURE_OPENAI_DEPLOYMENT | if backend=azure | orchestrator, summarization | schema, compose, bicep | Different from embedding |
| AZURE_OPENAI_API_VERSION | AZURE_OPENAI_API_VERSION | if backend=azure | orchestrator, summarization | schema, compose, bicep | Already prefixed |

---

## 6. ARCHIVE_STORE_TYPE - Discriminant Driver

**Driver Variable:** `ARCHIVE_STORE_TYPE`  
**Allowed Values:** `local`, `azureblob`  
**Used By:** ingestion, parsing (2 services)

### 6.1 Discriminant Variable (No Rename)

```
ARCHIVE_STORE_TYPE → ARCHIVE_STORE_TYPE | Services: ingestion, parsing | Files: schema, compose
```

### 6.2 Local Storage-Specific Variables

```
ARCHIVE_STORE_PATH → LOCAL_ARCHIVE_STORE_PATH (when ARCHIVE_STORE_TYPE=local) | Services: ingestion, parsing | Files: compose, code
```

### 6.3 Azure Blob Storage-Specific Variables (Standardize to AZUREBLOB_* prefix)

```
ARCHIVE_STORE_CONNECTION_STRING → AZUREBLOB_CONNECTION_STRING (when ARCHIVE_STORE_TYPE=azureblob) | Services: ingestion, parsing | Files: compose, code, bicep
ARCHIVE_STORE_ACCOUNT_NAME → AZUREBLOB_ACCOUNT_NAME (when ARCHIVE_STORE_TYPE=azureblob) | Services: ingestion, parsing | Files: compose, code, bicep
ARCHIVE_STORE_CONTAINER → AZUREBLOB_CONTAINER (when ARCHIVE_STORE_TYPE=azureblob) | Services: ingestion, parsing | Files: compose, code, bicep
AZURE_STORAGE_ACCOUNT → AZUREBLOB_STORAGE_ACCOUNT (legacy; consolidate) | Services: ingestion, parsing | Files: compose, bicep
AZURE_STORAGE_ENDPOINT → AZUREBLOB_ENDPOINT (legacy; consolidate) | Services: ingestion, parsing | Files: compose, bicep
AZURE_STORAGE_CONTAINER → AZUREBLOB_CONTAINER (legacy; consolidate) | Services: ingestion, parsing | Files: compose, bicep
```

**Note:** Multiple naming schemes exist (ARCHIVE_STORE_*, AZURE_STORAGE_*). Consolidate to AZUREBLOB_* prefix for clarity.

**Bicep File:** `infra/azure/modules/storage.bicep` - Ensure outputs use `AZUREBLOB_*` pattern.

### Summary Table: ARCHIVE_STORE_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| ARCHIVE_STORE_TYPE | ARCHIVE_STORE_TYPE | Driver (no change) | ingestion, parsing | schema, compose |
| ARCHIVE_STORE_PATH | LOCAL_ARCHIVE_STORE_PATH | if type=local | ingestion, parsing | compose, code |
| ARCHIVE_STORE_CONNECTION_STRING | AZUREBLOB_CONNECTION_STRING | if type=azureblob | ingestion, parsing | compose, code, bicep |
| ARCHIVE_STORE_ACCOUNT_NAME | AZUREBLOB_ACCOUNT_NAME | if type=azureblob | ingestion, parsing | compose, code, bicep |
| ARCHIVE_STORE_CONTAINER | AZUREBLOB_CONTAINER | if type=azureblob | ingestion, parsing | compose, code, bicep |
| AZURE_STORAGE_ACCOUNT | AZUREBLOB_STORAGE_ACCOUNT | (legacy) | ingestion, parsing | compose, bicep |
| AZURE_STORAGE_ENDPOINT | AZUREBLOB_ENDPOINT | (legacy) | ingestion, parsing | compose, bicep |
| AZURE_STORAGE_CONTAINER | AZUREBLOB_CONTAINER | (legacy) | ingestion, parsing | compose, bicep |

---

## 7. ERROR_REPORTER_TYPE - Discriminant Driver

**Driver Variable:** `ERROR_REPORTER_TYPE`  
**Allowed Values:** `sentry`, `noop`  
**Used By:** auth, chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization (8 services)

### 7.1 Discriminant Variable (No Rename)

```
ERROR_REPORTER_TYPE → ERROR_REPORTER_TYPE | Services: all | Files: schema, compose
```

### 7.2 Sentry-Specific Variables (Already prefixed; keep as-is)

```
SENTRY_DSN → SENTRY_DSN | Services: all | Files: schema, compose
SENTRY_ENVIRONMENT → SENTRY_ENVIRONMENT | Services: all | Files: schema, compose
```

**Note:** Already adapter-prefixed; no rename needed.

### Summary Table: ERROR_REPORTER_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| ERROR_REPORTER_TYPE | ERROR_REPORTER_TYPE | Driver (no change) | all | schema, compose |
| SENTRY_DSN | SENTRY_DSN | if type=sentry | all | schema, compose |
| SENTRY_ENVIRONMENT | SENTRY_ENVIRONMENT | if type=sentry | all | schema, compose |

---

## 8. SECRET_PROVIDER_TYPE - Discriminant Driver

**Driver Variable:** `SECRET_PROVIDER_TYPE`  
**Allowed Values:** `env`, `vault` (Azure Key Vault)  
**Used By:** auth (primary; others reference auth service) (1 service)

### 8.1 Discriminant Variable (No Rename)

```
SECRET_PROVIDER_TYPE → SECRET_PROVIDER_TYPE | Services: auth | Files: schema, compose
```

### 8.2 Environment Variables Secret Provider (Keep as-is)

```
SECRETS_BASE_PATH → SECRETS_BASE_PATH | Services: auth | Files: schema, compose
```

### 8.3 Azure Key Vault-Specific Variables (Rename to VAULT_* prefix)

```
AZURE_KEY_VAULT_NAME → VAULT_NAME (when SECRET_PROVIDER_TYPE=vault) | Services: auth | Files: compose, code, bicep
(new) → VAULT_SUBSCRIPTION_ID | Services: auth | Files: compose, code, bicep
(new) → VAULT_RESOURCE_GROUP | Services: auth | Files: compose, code, bicep
(new) → VAULT_TENANT_ID | Services: auth | Files: compose, code, bicep
```

**Note:** `AZURE_KEY_VAULT_NAME` exists but is not in schemas. Standardize to `VAULT_*` prefix.

**Bicep File:** `infra/azure/modules/keyvault.bicep` - Output `VAULT_NAME`, `VAULT_SUBSCRIPTION_ID`, `VAULT_RESOURCE_GROUP`, `VAULT_TENANT_ID`.

### Summary Table: SECRET_PROVIDER_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| SECRET_PROVIDER_TYPE | SECRET_PROVIDER_TYPE | Driver (no change) | auth | schema, compose |
| SECRETS_BASE_PATH | SECRETS_BASE_PATH | if type=env | auth | schema, compose |
| AZURE_KEY_VAULT_NAME | VAULT_NAME | if type=vault | auth | compose, code, bicep |
| (new) | VAULT_SUBSCRIPTION_ID | if type=vault | auth | compose, code, bicep |
| (new) | VAULT_RESOURCE_GROUP | if type=vault | auth | compose, code, bicep |
| (new) | VAULT_TENANT_ID | if type=vault | auth | compose, code, bicep |

---

## 9. AUTH_ROLE_STORE_TYPE - Discriminant Driver

**Driver Variable:** `AUTH_ROLE_STORE_TYPE`  
**Allowed Values:** `mongodb`, `cosmosdb`, `memory`  
**Used By:** auth (1 service)

### 9.1 Discriminant Variable (No Rename)

```
AUTH_ROLE_STORE_TYPE → AUTH_ROLE_STORE_TYPE | Services: auth | Files: schema, compose
```

**Note:** Already has `AUTH_` prefix; indicates service context.

### 9.2 MongoDB-Specific Variables (Add adapter prefix)

```
AUTH_ROLE_STORE_HOST → AUTH_MONGODB_HOST (when AUTH_ROLE_STORE_TYPE=mongodb) | Services: auth | Files: compose, code
AUTH_ROLE_STORE_PORT → AUTH_MONGODB_PORT (when AUTH_ROLE_STORE_TYPE=mongodb) | Services: auth | Files: compose, code
AUTH_ROLE_STORE_DATABASE → AUTH_MONGODB_DATABASE (when AUTH_ROLE_STORE_TYPE=mongodb) | Services: auth | Files: compose, code
AUTH_ROLE_STORE_COLLECTION → AUTH_MONGODB_COLLECTION (when AUTH_ROLE_STORE_TYPE=mongodb) | Services: auth | Files: compose, code
AUTH_ROLE_STORE_USERNAME → AUTH_MONGODB_USERNAME | Services: auth | Files: compose, code
role_store_password (secret) → auth_mongodb_password (secret) | Services: auth | Files: compose (secrets)
AUTH_ROLE_STORE_SCHEMA_DIR → AUTH_MONGODB_SCHEMA_DIR | Services: auth | Files: compose, code
```

### 9.3 Azure Cosmos DB-Specific Variables (Standardize to COSMOS_ prefix with AUTH_ context)

```
AUTH_ROLE_STORE_HOST → AUTH_COSMOS_HOST (when AUTH_ROLE_STORE_TYPE=cosmosdb) | Services: auth | Files: compose, code, bicep
AUTH_ROLE_STORE_PORT → AUTH_COSMOS_PORT (when AUTH_ROLE_STORE_TYPE=cosmosdb) | Services: auth | Files: compose, code, bicep
AUTH_ROLE_STORE_DATABASE → AUTH_COSMOS_DATABASE (when AUTH_ROLE_STORE_TYPE=cosmosdb) | Services: auth | Files: compose, code, bicep
AUTH_ROLE_STORE_COLLECTION → AUTH_COSMOS_COLLECTION (when AUTH_ROLE_STORE_TYPE=cosmosdb) | Services: auth | Files: compose, code, bicep
AUTH_ROLE_STORE_USERNAME → AUTH_COSMOS_USERNAME | Services: auth | Files: compose, code, bicep
role_store_password (secret) → auth_cosmos_password (secret) | Services: auth | Files: compose, bicep (secrets)
AUTH_ROLE_STORE_SCHEMA_DIR → AUTH_COSMOS_SCHEMA_DIR | Services: auth | Files: compose, code, bicep
```

### 9.4 Memory (In-Memory) Store-Specific Variables (No network vars needed)

```
AUTH_ROLE_STORE_SCHEMA_DIR → AUTH_MEMORY_SCHEMA_DIR (when AUTH_ROLE_STORE_TYPE=memory) | Services: auth | Files: compose, code
```

### Summary Table: AUTH_ROLE_STORE_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| AUTH_ROLE_STORE_TYPE | AUTH_ROLE_STORE_TYPE | Driver (no change) | auth | schema, compose |
| AUTH_ROLE_STORE_HOST | AUTH_MONGODB_HOST | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_HOST | AUTH_COSMOS_HOST | if type=cosmosdb | auth | compose, code, bicep |
| AUTH_ROLE_STORE_PORT | AUTH_MONGODB_PORT | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_PORT | AUTH_COSMOS_PORT | if type=cosmosdb | auth | compose, code, bicep |
| AUTH_ROLE_STORE_DATABASE | AUTH_MONGODB_DATABASE | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_DATABASE | AUTH_COSMOS_DATABASE | if type=cosmosdb | auth | compose, code, bicep |
| AUTH_ROLE_STORE_COLLECTION | AUTH_MONGODB_COLLECTION | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_COLLECTION | AUTH_COSMOS_COLLECTION | if type=cosmosdb | auth | compose, code, bicep |
| AUTH_ROLE_STORE_USERNAME | AUTH_MONGODB_USERNAME | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_USERNAME | AUTH_COSMOS_USERNAME | if type=cosmosdb | auth | compose, code, bicep |
| role_store_password | auth_mongodb_password | if type=mongodb | auth | compose (secrets) |
| role_store_password | auth_cosmos_password | if type=cosmosdb | auth | compose, bicep (secrets) |
| AUTH_ROLE_STORE_SCHEMA_DIR | AUTH_MONGODB_SCHEMA_DIR | if type=mongodb | auth | compose, code |
| AUTH_ROLE_STORE_SCHEMA_DIR | AUTH_COSMOS_SCHEMA_DIR | if type=cosmosdb | auth | compose, code, bicep |
| AUTH_ROLE_STORE_SCHEMA_DIR | AUTH_MEMORY_SCHEMA_DIR | if type=memory | auth | compose, code |

---

## 10. METRICS_TYPE - Discriminant Driver

**Driver Variable:** `METRICS_TYPE`  
**Allowed Values:** `prometheus`, `pushgateway`, `azure_monitor`, `noop`  
**Used By:** auth, chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization (8 services)

### 10.1 Discriminant Variable (No Rename)

```
METRICS_TYPE → METRICS_TYPE | Services: all | Files: schema, compose
```

### 10.2 Prometheus Push Gateway-Specific Variables

```
PROMETHEUS_PUSHGATEWAY → PROMETHEUS_PUSHGATEWAY | Services: auth, reporting | Files: schema, compose
```

**Note:** Already adapter-prefixed. Used by `auth` and `reporting` services when metrics_type=pushgateway.

### 10.3 Azure Monitor-Specific Variables (New; to be added)

```
(new) → AZURE_MONITOR_INSTRUMENTATION_KEY | Services: all | Files: compose, code, bicep
(new) → AZURE_MONITOR_TENANT_ID | Services: all | Files: compose, code, bicep
```

### Summary Table: METRICS_TYPE

| Old Name | New Name | Condition | Services | Files |
|----------|----------|-----------|----------|-------|
| METRICS_TYPE | METRICS_TYPE | Driver (no change) | all | schema, compose |
| PROMETHEUS_PUSHGATEWAY | PROMETHEUS_PUSHGATEWAY | if type=pushgateway | auth, reporting | schema, compose |
| (new) | AZURE_MONITOR_INSTRUMENTATION_KEY | if type=azure_monitor | all | compose, code, bicep |
| (new) | AZURE_MONITOR_TENANT_ID | if type=azure_monitor | all | compose, code, bicep |

---

## 11. Non-Discriminant Service-Specific Variables (No Rename Needed)

These variables are service-specific and already properly prefixed or generic within their service scope.

### 11.1 Auth Service (AUTH_* prefixed)

```
AUTH_ISSUER → AUTH_ISSUER | Services: auth | Files: schema, compose
AUTH_AUDIENCES → AUTH_AUDIENCES | Services: auth | Files: schema, compose
JWT_ALGORITHM → JWT_ALGORITHM | Services: auth | Files: schema, compose
JWT_KEY_ID → JWT_KEY_ID | Services: auth | Files: schema, compose
JWT_DEFAULT_EXPIRY → JWT_DEFAULT_EXPIRY | Services: auth | Files: schema, compose
jwt_private_key (secret) → jwt_private_key (secret) | Services: auth | Files: schema, compose (secrets)
jwt_public_key (secret) → jwt_public_key (secret) | Services: auth | Files: schema, compose (secrets)
jwt_secret_key (secret) → jwt_secret_key (secret) | Services: auth | Files: schema, compose (secrets)
AUTH_GITHUB_REDIRECT_URI → AUTH_GITHUB_REDIRECT_URI | Services: auth | Files: schema, compose
AUTH_GITHUB_API_BASE_URL → AUTH_GITHUB_API_BASE_URL | Services: auth | Files: schema, compose
AUTH_GOOGLE_REDIRECT_URI → AUTH_GOOGLE_REDIRECT_URI | Services: auth | Files: schema, compose
AUTH_MS_REDIRECT_URI → AUTH_MS_REDIRECT_URI | Services: auth | Files: schema, compose
AUTH_MS_TENANT → AUTH_MS_TENANT | Services: auth | Files: schema, compose
AUTH_REQUIRE_PKCE → AUTH_REQUIRE_PKCE | Services: auth | Files: schema, compose
AUTH_REQUIRE_NONCE → AUTH_REQUIRE_NONCE | Services: auth | Files: schema, compose
AUTH_MAX_SKEW_SECONDS → AUTH_MAX_SKEW_SECONDS | Services: auth | Files: schema, compose
AUTH_AUTO_APPROVE_ENABLED → AUTH_AUTO_APPROVE_ENABLED | Services: auth | Files: schema, compose
AUTH_AUTO_APPROVE_ROLES → AUTH_AUTO_APPROVE_ROLES | Services: auth | Files: schema, compose
AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED → AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED | Services: auth | Files: schema, compose
AUTH_ENABLE_DPOP → AUTH_ENABLE_DPOP | Services: auth | Files: schema, compose
```

**Note:** No rename needed; already well-prefixed.

### 11.2 Chunking Service

```
CHUNK_SIZE_TOKENS → CHUNK_SIZE_TOKENS | Services: chunking | Files: schema, compose
CHUNK_OVERLAP_TOKENS → CHUNK_OVERLAP_TOKENS | Services: chunking | Files: schema, compose
MIN_CHUNK_SIZE_TOKENS → MIN_CHUNK_SIZE_TOKENS | Services: chunking | Files: schema, compose
MAX_CHUNK_SIZE_TOKENS → MAX_CHUNK_SIZE_TOKENS | Services: chunking | Files: schema, compose
CHUNKING_STRATEGY → CHUNKING_STRATEGY | Services: chunking | Files: schema, compose
```

### 11.3 Orchestrator Service

```
TOP_K → TOP_K | Services: orchestrator, summarization | Files: schema, compose
CONTEXT_WINDOW_TOKENS → CONTEXT_WINDOW_TOKENS | Services: orchestrator | Files: schema, compose
SYSTEM_PROMPT_PATH → SYSTEM_PROMPT_PATH | Services: orchestrator | Files: schema, compose
USER_PROMPT_PATH → USER_PROMPT_PATH | Services: orchestrator | Files: schema, compose
```

### 11.4 Summarization Service

```
CITATION_COUNT → CITATION_COUNT | Services: summarization | Files: schema, compose
```

### 11.5 Reporting Service

```
NOTIFY_ENABLED → NOTIFY_ENABLED | Services: reporting | Files: schema, compose
NOTIFY_WEBHOOK_URL → NOTIFY_WEBHOOK_URL | Services: reporting | Files: schema, compose
WEBHOOK_SUMMARY_MAX_LENGTH → WEBHOOK_SUMMARY_MAX_LENGTH | Services: reporting | Files: schema, compose
```

### 11.6 Ingestion Service

```
STORAGE_PATH → STORAGE_PATH | Services: ingestion | Files: schema, compose
INGESTION_SCHEDULE_CRON → INGESTION_SCHEDULE_CRON | Services: ingestion | Files: schema, compose
```

### 11.7 Parsing Service

```
LOG_LEVEL → LOG_LEVEL | Services: parsing | Files: schema, compose
```

### 11.8 Common Service Variables (HTTP_PORT, JWT_AUTH_ENABLED, RETRY_MAX_ATTEMPTS, RETRY_DELAY_SECONDS)

```
HTTP_PORT → HTTP_PORT | Services: all except auth, ingestion | Files: schema, compose
JWT_AUTH_ENABLED → JWT_AUTH_ENABLED | Services: all except auth | Files: schema, compose
RETRY_MAX_ATTEMPTS → RETRY_MAX_ATTEMPTS | Services: all | Files: schema, compose
RETRY_DELAY_SECONDS → RETRY_DELAY_SECONDS | Services: parsing, summarization | Files: schema, compose
```

**Note:** No rename needed; generic service variables.

---

## 12. OAuth Provider Secrets (No Rename; Already Structured)

```
github_oauth_client_id (secret) → github_oauth_client_id (secret) | Services: auth | Files: compose (secrets)
github_oauth_client_secret (secret) → github_oauth_client_secret (secret) | Services: auth | Files: compose (secrets)
google_oauth_client_id (secret) → google_oauth_client_id (secret) | Services: auth | Files: compose (secrets)
google_oauth_client_secret (secret) → google_oauth_client_secret (secret) | Services: auth | Files: compose (secrets)
microsoft_oauth_client_id (secret) → microsoft_oauth_client_id (secret) | Services: auth | Files: compose (secrets)
microsoft_oauth_client_secret (secret) → microsoft_oauth_client_secret (secret) | Services: auth | Files: compose (secrets)
```

**Note:** No rename needed; already properly named.

---

## Summary: All 124 Variables Mapped

### By Category

1. **Discriminant Drivers (9 total; 0 renames)**
   - `MESSAGE_BUS_TYPE`
   - `DOCUMENT_STORE_TYPE`
   - `VECTOR_STORE_TYPE`
   - `EMBEDDING_BACKEND`
   - `LLM_BACKEND`
   - `ARCHIVE_STORE_TYPE`
   - `ERROR_REPORTER_TYPE`
   - `SECRET_PROVIDER_TYPE`
   - `AUTH_ROLE_STORE_TYPE`
   - `METRICS_TYPE`

2. **Adapter-Aware Variables (Will rename based on discriminant; ~55 total)**
   - MESSAGE_BUS_*: 9 variables
   - DOCUMENT_STORE_*: 11 variables
   - VECTOR_STORE_*: 14 variables
   - EMBEDDING_BACKEND_*: 10 variables
   - LLM_BACKEND_*: 11 variables (keep generic + adapter-specific)
   - ARCHIVE_STORE_*: 8 variables
   - AUTH_ROLE_STORE_*: 12 variables

3. **Already Adapter-Prefixed (Keep as-is; ~20 total)**
   - `SENTRY_*` (2): SENTRY_DSN, SENTRY_ENVIRONMENT
   - `AZURE_OPENAI_*` (4): AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
   - `AISEARCH_*` (4): AISEARCH_ENDPOINT, AISEARCH_INDEX_NAME, AISEARCH_API_KEY, AISEARCH_USE_MANAGED_IDENTITY
   - `OLLAMA_*` (1): OLLAMA_HOST
   - `LLAMACPP_*` (1): LLAMACPP_HOST
   - `PROMETHEUS_*` (1): PROMETHEUS_PUSHGATEWAY
   - `AUTH_*` service-specific (7): AUTH_ISSUER, AUTH_AUDIENCES, AUTH_GITHUB_REDIRECT_URI, etc.

4. **Service-Specific Generic Variables (No rename; ~40 total)**
   - Chunking-specific (5): CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS, MIN_CHUNK_SIZE_TOKENS, MAX_CHUNK_SIZE_TOKENS, CHUNKING_STRATEGY
   - Orchestrator-specific (4): TOP_K, CONTEXT_WINDOW_TOKENS, SYSTEM_PROMPT_PATH, USER_PROMPT_PATH
   - Summarization-specific (1): CITATION_COUNT
   - Reporting-specific (3): NOTIFY_ENABLED, NOTIFY_WEBHOOK_URL, WEBHOOK_SUMMARY_MAX_LENGTH
   - Ingestion-specific (2): STORAGE_PATH, INGESTION_SCHEDULE_CRON
   - Parsing-specific (1): LOG_LEVEL
   - Common service variables (6): HTTP_PORT, JWT_AUTH_ENABLED, RETRY_MAX_ATTEMPTS, RETRY_DELAY_SECONDS, JWT_ALGORITHM, JWT_KEY_ID, JWT_DEFAULT_EXPIRY, LOG_LEVEL, LOG_TYPE, LOG_NAME
   - OAuth secrets (6): github_*, google_*, microsoft_*

---

## Implementation Roadmap

### Phase 1: Non-Breaking Changes (Compose/Code only; Keep schemas generic)
- Rename variables in `docker-compose.yml` for adapter-specific backends
- Update application code to use renamed variables
- Keep schemas generic but add conditional documentation
- **Files to update:**
  - `docker-compose.yml`, `docker-compose.services.yml`, `docker-compose.infra.yml`
  - All Python service files (adapters and services)
  - Environment variable parsing code

### Phase 2: Schema Updates
- Create adapter-specific schema variants or conditional fields
- Document adapter selection logic in schema
- Update configuration loader to handle conditional env var names
- **Files to update:**
  - `docs/schemas/configs/*.json` (all schema files)
  - Configuration loader code

### Phase 3: Bicep Template Updates
- Standardize Bicep output variable names to use renamed prefixes
- Update all `*.bicep` files to output COSMOS_*, AZUREBLOB_*, VAULT_*, SERVICEBUS_* etc.
- **Files to update:**
  - `infra/azure/main.bicep`
  - `infra/azure/modules/*.bicep` (cosmos.bicep, storage.bicep, keyvault.bicep, servicebus.bicep, etc.)

### Phase 4: Documentation & Migration Guide
- Document migration steps for users
- Provide backwards compatibility script (env var mapping)
- Update README and deployment guides
- **Files to update:**
  - `README.md`
  - `docs/configuration.md`
  - `docs/DEPLOYMENT_GUIDE_*.md`
  - New `docs/ENVIRONMENT_VARIABLE_MIGRATION.md`

---

## Files to Update Summary

| File Type | Files | Phase |
|-----------|-------|-------|
| Docker Compose | `docker-compose.yml`, `docker-compose.services.yml`, `docker-compose.infra.yml` | 1 |
| Schemas | `docs/schemas/configs/auth.json`, `chunking.json`, `embedding.json`, `ingestion.json`, `orchestrator.json`, `parsing.json`, `reporting.json`, `summarization.json` | 2 |
| Python Services | All `*/app/*.py`, `*/main.py`, adapter files in `adapters/*/` | 1 |
| Bicep Templates | `infra/azure/main.bicep`, `infra/azure/modules/*.bicep` | 3 |
| Documentation | `docs/configuration.md`, `docs/DEPLOYMENT_GUIDE_*.md`, `README.md`, new migration guide | 4 |

---

## Notes

- **Backwards Compatibility:** Phase 1 changes can be made without breaking existing configurations by keeping schema variables generic.
- **Conditional Logic:** Application code should detect the discriminant variable value and read the appropriate adapter-specific variables.
- **Bicep Consistency:** Azure Bicep templates already partially use adapter-prefixed names (e.g., COSMOS_DB_*). This mapping standardizes and completes that pattern.
- **Secret Management:** Secret names in docker-compose should follow the same pattern as env vars but maintain secret store compatibility.
- **Migration Path:** Implement feature flags or env var aliasing to allow gradual migration without breaking existing deployments.

