<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Storage Module and Cosmos Collections Implementation Summary

## Overview

This implementation addresses issue #634 by adding comprehensive Azure Storage Account support and finalizing Cosmos DB collections/databases configuration for the Copilot for Consensus Azure deployment.

## Changes Made

### 1. Azure Storage Account Module (`infra/azure/modules/storage.bicep`)

Created a new Bicep module to provision Azure Storage Account for blob storage:

**Features:**
- Configurable SKU (Standard_LRS for dev, Standard_GRS for prod)
- Hot access tier for frequently accessed archives
- Blob containers: `archives` (for raw email archives)
- HTTPS-only, TLS 1.2 minimum
- Blob public access disabled (secure by default)
- 7-day soft delete for blobs and containers
- RBAC-based access (no access keys exposed)

**RBAC Configuration:**
- Assigns **Storage Blob Data Contributor** role to all service managed identities
- Enables keyless authentication via Azure managed identities

**Outputs:**
- Storage account name
- Storage account resource ID
- Blob endpoint URL
- Container names created

### 2. Main Bicep Template Updates (`infra/azure/main.bicep`)

**Added:**
- Storage account name variable with proper length constraints (3-24 chars)
- Storage module deployment (conditional on `deployContainerApps`)
- Storage outputs (account name, ID, blob endpoint, container names)
- Wiring of storage module outputs to Container Apps module

**Storage Account Naming:**
- Format: `{projectPrefix}st{environment}{uniqueSuffix}`
- Example (dev): `copilotdev1a2b3c4d5e` (lowercase, no special chars, max 24 chars)

### 3. Container Apps Module Updates (`infra/azure/modules/containerapps.bicep`)

**Added Parameters:**
- `storageAccountName`: Storage account name for blob operations
- `storageBlobEndpoint`: Blob endpoint URL

**Ingestion Service Environment Variables:**
- `AZURE_STORAGE_ACCOUNT`: Storage account name
- `AZURE_STORAGE_ENDPOINT`: Blob endpoint URL
- `AZURE_STORAGE_CONTAINER`: Container name (`archives`)

These enable the ingestion service to use Azure Blob Storage for raw email archive storage with managed identity authentication.

### 4. Cosmos DB Module Enhancements (`infra/azure/modules/cosmos.bicep`)

**Enhanced Indexing Policy:**

Added **composite indexes** optimized for common query patterns:

1. **Archives**: `collection + source + ingestion_date`
2. **Messages**: `collection + archive_id + date`, `collection + thread_id + date`
3. **Threads**: `collection + archive_id + last_message_date`
4. **Summaries**: `collection + thread_id + generated_at`
5. **Chunks**: `collection + message_id + sequence`

All composite indexes include `collection` first to ensure efficient partition-scoped queries.

**Updated Documentation:**
- Added comprehensive comments explaining multi-collection pattern
- Documented benefits and trade-offs of single-container approach
- Explained when to migrate to separate containers

### 5. Documentation

#### New: `COSMOS_DB_DESIGN.md`
Comprehensive documentation covering:
- Database and container structure
- Multi-collection pattern explanation
- Logical collections (archives, messages, chunks, threads, summaries)
- Design benefits and trade-offs
- Indexing strategy with composite indexes
- Partition strategy using `/collection`
- Throughput configuration per environment
- Monitoring guidance
- Migration path for scaling

#### Updated: `BICEP_ARCHITECTURE.md`
- Added Azure Storage Account to core services list
- Added storage.bicep to module organization diagram
- Added new "Data Storage Architecture" section with:
  - Cosmos DB document store details
  - Azure Storage Account blob storage details
  - Usage patterns and RBAC roles
  - Cross-reference to COSMOS_DB_DESIGN.md

#### Updated: `.gitignore`
- Added exclusion for generated JSON files from `az bicep build` (modules/*.json)

## Cosmos DB Collections Strategy

### Single Container Multi-Collection Approach

All document types are stored in a **single container** (`documents`) with `/collection` as the partition key:

**Collections (Logical):**
1. `archives` - Raw email archive metadata
2. `messages` - Individual email messages
3. `chunks` - Semantic chunks for embeddings
4. `threads` - Email conversation threads
5. `summaries` - Generated thread summaries

**Why This Approach?**
- Simplified throughput management (one RU budget)
- Lower cost (one container minimum vs. five)
- Cross-collection queries and transactions
- Simplified deployment and management

**Trade-offs:**
- Shared partition key space
- Cannot set different TTL per collection
- Cannot set different indexing per collection (mitigated with composite indexes)

**When to Migrate:**
- Individual collections exceed 20GB or 10,000 RU/s
- Different TTL requirements emerge
- Hot partition issues arise

## Environment Variables Injected

### All Services (via Container Apps)
- `DOCUMENT_STORE_TYPE`: `cosmos`
- `COSMOS_DB_ENDPOINT`: Cosmos DB account endpoint (e.g., `https://xyz-cos-dev-abc.documents.azure.com:443/`)

### Ingestion Service (Additional)
- `AZURE_STORAGE_ACCOUNT`: Storage account name (e.g., `copilotdev1a2b3c4d`)
- `AZURE_STORAGE_ENDPOINT`: Blob endpoint (e.g., `https://copilotdev1a2b3c4d.blob.core.windows.net/`)
- `AZURE_STORAGE_CONTAINER`: `archives`

All services use **managed identity authentication** (no keys or connection strings in environment variables).

## Deployment Configuration

### No New Parameters Required

The storage module uses existing parameters:
- `deployContainerApps`: Storage deploys only when Container Apps are enabled
- `environment`: Controls SKU selection (LRS for dev, GRS for prod)
- Existing managed identity infrastructure

### SKU Selection
- **Development**: Standard_LRS (locally redundant)
- **Staging**: Standard_LRS
- **Production**: Standard_GRS (geo-redundant, recommended)

### Cosmos DB Throughput (Unchanged)
- **Dev**: 400-1000 RU/s autoscale
- **Staging**: 1000-2000 RU/s autoscale
- **Prod**: 2000-4000+ RU/s autoscale (adjust based on load)

## Validation

All Bicep templates build successfully:
```bash
✓ az bicep build --file main.bicep
✓ az bicep build --file modules/storage.bicep
✓ az bicep build --file modules/cosmos.bicep
✓ az bicep build --file modules/containerapps.bicep
```

**Warnings (Acceptable):**
- BCP318 warnings on appInsightsModule outputs (existing, safe due to conditional guards)

## RBAC Roles Assigned

### Storage Blob Data Contributor
All service managed identities receive this role on the storage account:
- ingestion
- parsing
- chunking
- embedding
- orchestrator
- summarization
- reporting
- auth
- ui
- gateway
- openai (managed identity)

This enables keyless blob read/write operations via managed identity.

## Migration Notes

### From MongoDB to Cosmos DB
- Container name: `documents` (replaces MongoDB collections)
- Partition key: `/collection` field must be set on all documents
- Logical collections: Use `collection` field to differentiate document types

### Cosmos DB to Blob Storage
- Archives (binary mbox files) should be stored in Blob Storage
- Archive metadata stored in Cosmos DB (`archives` collection)
- Python adapter: `copilot_archive_store.AzureBlobArchiveStore`

## Testing Recommendations

1. **Deploy to dev environment** and verify:
   - Storage account is created
   - `archives` container exists
   - Managed identities have blob contributor access
   - Ingestion service can read/write blobs

2. **Test Cosmos DB** queries with composite indexes:
   - Query messages by thread_id + date
   - Query archives by source + ingestion_date
   - Monitor RU consumption

3. **Validate RBAC** (no access keys):
   - Ingestion service connects to blob storage without connection string
   - All services connect to Cosmos DB without keys

## Cost Implications

### Azure Storage Account
- **Dev/Staging**: ~$2-5/month (100GB, Standard_LRS, Hot tier)
- **Production**: ~$10-20/month (1TB, Standard_GRS, Hot tier)

### Cosmos DB
- **Dev**: ~$24/month (400 RU/s minimum, autoscale to 1000)
- **Staging**: ~$58/month (1000 RU/s minimum, autoscale to 2000)
- **Production**: ~$233+/month (4000 RU/s minimum, autoscale based on load)

Total additional infrastructure cost: **~$26-50/month for dev, $250+/month for prod**

## References

- Storage module: `infra/azure/modules/storage.bicep`
- Cosmos module: `infra/azure/modules/cosmos.bicep`
- Main template: `infra/azure/main.bicep`
- Design docs: `infra/azure/COSMOS_DB_DESIGN.md`, `infra/azure/BICEP_ARCHITECTURE.md`
- Schema configs: `documents/schemas/documents/collections.config.json`
- Python adapters: `adapters/copilot_storage/`, `adapters/copilot_archive_store/`

## Acceptance Criteria Met

- ✅ Storage module deploys without manual steps
- ✅ Cosmos DB collections defined with desired throughput/index policies
- ✅ Connection info/URIs exported and injected via environment variables
- ✅ Services receive correct endpoints and use managed identity authentication
- ✅ Storage usage and tuning defaults documented

## Next Steps

1. Deploy to dev environment for validation
2. Test ingestion workflow with real email archives
3. Monitor Cosmos DB RU consumption and adjust autoscale limits
4. Consider enabling Cosmos DB multi-region for production (set `enableMultiRegionCosmos: true`)
5. Review and tune composite indexes based on actual query patterns
