<!-- SPDX-License-Identifier: MIT -->
<!-- Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Data Migration Guide

Export and import all pipeline data between CoPilot-for-Consensus deployments — Azure Cosmos DB, Docker Compose (MongoDB), or any mix of the two.

## Overview

The project stores all pipeline state in a document database (`copilot` database) with these collections:

| Collection | Purpose | Typical Size |
|------------|---------|-------------|
| `sources` | Ingestion source definitions | Small (< 100 docs) |
| `archives` | Mailing list archive metadata | Hundreds |
| `messages` | Parsed email messages | Thousands–tens of thousands |
| `threads` | Threaded conversation groups | Thousands |
| `chunks` | Text chunks for embedding | Tens of thousands |
| `summaries` | LLM-generated thread summaries | Thousands |
| `reports` | Generated reports and reporting metadata | Hundreds–thousands |

The `auth` database contains a `user_roles` collection for admin role mappings.

### Which scripts to use

| Backend | API Type | Scripts |
|---------|----------|---------|
| **Azure Cosmos DB (SQL API)** — default for this project | NoSQL / SQL API | `data-migration-export.py` / `data-migration-import.py` |
| **Azure Cosmos DB (MongoDB API)** | MongoDB wire protocol | `data-migration-export.ps1` / `data-migration-import.ps1` |
| **Docker Compose MongoDB** | MongoDB wire protocol | Either set works; Python scripts recommended |

> **Important**: The default Azure deployment (`infra/azure/modules/cosmos.bicep`) creates a
> **SQL API** Cosmos DB account (`kind: GlobalDocumentDB`), not a MongoDB API account.
> The `mongoexport`/`mongoimport` tools and the PowerShell scripts **do not work** with SQL API.
> Use the Python scripts for SQL API accounts.

### Partition keys

The Bicep template creates containers with these partition keys:

| Container | Partition Key | Notes |
|-----------|--------------|-------|
| `documents` | `/collection` | Shared container (exists in both `copilot` and `auth` DBs; typically unused by the app) |
| `sources`, `archives`, `messages`, `threads`, `chunks`, `summaries`, `reports` | `/id` | Per-collection containers (used by the application) |
| `user_roles` | `/id` | Auth database |

The import script uses these partition keys when creating containers. If your deployment uses
a different schema, update the `COSMOS_PARTITION_KEYS` dict in `scripts/data-migration-import.py`.

## Prerequisites

### Tools

| Tool | Install | Purpose |
|------|---------|---------|
| Python 3.11+ | Pre-installed in project venv | Running migration scripts |
| [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) | `winget install Microsoft.AzureCLI` | Storage upload, RBAC role setup |
| `azure-cosmos` | `pip install azure-cosmos` | Cosmos DB SQL API export/import |
| `azure-identity` | `pip install azure-identity` | RBAC authentication (optional) |
| `pymongo` | `pip install pymongo` | MongoDB export/import (optional) |

### Authentication

The scripts support two authentication methods for Azure Cosmos DB:

| Method | Flag | Use When |
|--------|------|----------|
| **Connection string** (default) | `--cosmos-key` | You have access to account keys |
| **Azure AD / RBAC** | `--use-rbac` | Keys are disabled, or you prefer identity-based auth |

**RBAC requirements**: The signed-in Azure AD principal (`az login`) must have one of these Cosmos DB built-in roles:

- **Export**: `Cosmos DB Built-in Data Reader` (or higher)
- **Import**: `Cosmos DB Built-in Data Contributor`

Assign a role via:

```powershell
az cosmosdb sql role assignment create `
    --account-name <cosmos-account> `
    --resource-group <rg> `
    --role-definition-name "Cosmos DB Built-in Data Contributor" `
    --principal-id <your-object-id> `
    --scope "/"
```

## Quick Start

### Export all data

```powershell
# From Azure Cosmos DB (connection string)
python scripts/data-migration-export.py --source-type cosmos `
    --cosmos-endpoint "https://<account>.documents.azure.com:443/" `
    --cosmos-key "<key>"

# From Azure Cosmos DB (RBAC — uses az login identity)
python scripts/data-migration-export.py --source-type cosmos `
    --cosmos-endpoint "https://<account>.documents.azure.com:443/" `
    --use-rbac

# From Docker Compose MongoDB (see "Exporting from Docker Compose" for auth details)
python scripts/data-migration-export.py --source-type mongodb `
    --mongo-uri "mongodb://<user>:<pass>@localhost:27017/?authSource=admin"
```

### Import all data

```powershell
# Into Azure Cosmos DB (connection string)
python scripts/data-migration-import.py --dest-type cosmos `
    --cosmos-endpoint "https://<account>.documents.azure.com:443/" `
    --cosmos-key "<key>" `
    --export-dir data-export-<timestamp>

# Into Azure Cosmos DB (RBAC)
python scripts/data-migration-import.py --dest-type cosmos `
    --cosmos-endpoint "https://<account>.documents.azure.com:443/" `
    --use-rbac `
    --export-dir data-export-<timestamp>

# Into Docker Compose MongoDB
python scripts/data-migration-import.py --dest-type mongodb `
    --mongo-uri "mongodb://<user>:<pass>@localhost:27017/?authSource=admin" `
    --export-dir data-export-<timestamp>
```

### One-step migrate (export + import)

```powershell
# Cosmos → Docker Compose
python scripts/data-migration-export.py --source-type cosmos --cosmos-endpoint ... --cosmos-key ...
python scripts/data-migration-import.py --dest-type mongodb --mongo-uri "mongodb://user:pass@localhost:27017/?authSource=admin" --export-dir data-export-<timestamp>

# Docker Compose → Cosmos
python scripts/data-migration-export.py --source-type mongodb --mongo-uri "mongodb://user:pass@localhost:27017/?authSource=admin"
python scripts/data-migration-import.py --dest-type cosmos --cosmos-endpoint ... --cosmos-key ... --export-dir data-export-<timestamp>

# Cosmos → Cosmos (different subscription/region)
python scripts/data-migration-export.py --source-type cosmos --cosmos-endpoint <src> --cosmos-key <src-key>
python scripts/data-migration-import.py --dest-type cosmos --cosmos-endpoint <dst> --cosmos-key <dst-key> --export-dir data-export-<timestamp>
```

### Upload to Azure Storage (archival)

After exporting, upload the data to an Azure Storage account for safe-keeping:

```powershell
az storage container create --name data-export --account-name <storage-account> --auth-mode key
az storage blob upload-batch --source data-export-<timestamp> --destination data-export --account-name <storage-account> --auth-mode key --overwrite
```

## Export Format

Data is exported to a timestamped directory:

```
data-export-<timestamp>/
├── copilot/
│   ├── sources.json
│   ├── archives.json
│   ├── messages.json
│   ├── threads.json
│   ├── chunks.json
│   ├── summaries.json
│   └── reports.json
├── auth/
│   └── user_roles.json
└── manifest.json
```

Each `.json` file contains one JSON document per line (NDJSON / JSON Lines format), compatible with both `mongoimport` and the Azure Cosmos DB bulk import APIs.

The `manifest.json` records metadata about the export:

```json
{
  "exported_at": "2026-02-12T17:00:00Z",
  "source_type": "cosmos",
  "source_endpoint": "https://example.documents.azure.com:443/",
  "databases": {
    "copilot": ["sources", "archives", "messages", "threads", "chunks", "summaries", "reports"],
    "auth": ["user_roles"]
  },
  "document_counts": {
    "copilot.sources": 5,
    "copilot.archives": 395,
    "copilot.messages": 12000,
    "copilot.threads": 25000,
    "copilot.chunks": 80000,
    "copilot.summaries": 31000,
    "copilot.reports": 500
  }
}
```

## Detailed Procedures

### Exporting from Azure Cosmos DB

The export script uses the `azure-cosmos` Python SDK (SQL API):

```powershell
# Connection string auth (account key)
python scripts/data-migration-export.py --source-type cosmos `
    --cosmos-endpoint "https://copilot-cos-dev-y6f2c.documents.azure.com:443/" `
    --cosmos-key "<primary-key>"

# RBAC auth (uses DefaultAzureCredential — az login, managed identity, etc.)
python scripts/data-migration-export.py --source-type cosmos `
    --cosmos-endpoint "https://copilot-cos-dev-y6f2c.documents.azure.com:443/" `
    --use-rbac
```

### Exporting from Docker Compose (MongoDB)

Docker Compose MongoDB credentials are stored in `secrets/mongodb_user` and `secrets/mongodb_password`.
The default CI credentials are `root`/`example`. Build the connection URI accordingly:

```powershell
# Default (unauthenticated localhost — works if MongoDB has no auth)
python scripts/data-migration-export.py --source-type mongodb

# With credentials from secrets files (typical local dev setup)
$user = Get-Content secrets/mongodb_user
$pass = Get-Content secrets/mongodb_password
python scripts/data-migration-export.py --source-type mongodb `
    --mongo-uri "mongodb://${user}:${pass}@localhost:27017/?authSource=admin"
```

### Importing into Azure Cosmos DB

```powershell
# Connection string auth
python scripts/data-migration-import.py --dest-type cosmos `
    --cosmos-endpoint "https://copilot-cos-dev-y6f2c.documents.azure.com:443/" `
    --cosmos-key "<primary-key>" `
    --export-dir "data-export-20260212T170000"

# RBAC auth
python scripts/data-migration-import.py --dest-type cosmos `
    --cosmos-endpoint "https://copilot-cos-dev-y6f2c.documents.azure.com:443/" `
    --use-rbac `
    --export-dir "data-export-20260212T170000"
```

> **Note**: The import script creates databases and containers if they don't exist.
> Cosmos DB containers are created with partition keys matching `infra/azure/modules/cosmos.bicep`
> (see the [Partition keys](#partition-keys) table above). Verify the mapping in
> `COSMOS_PARTITION_KEYS` in `scripts/data-migration-import.py` before importing into a new environment.

### Importing into Docker Compose (MongoDB)

```powershell
# Ensure Docker Compose services are running
docker compose up -d documentdb

# With credentials from secrets files
$user = Get-Content secrets/mongodb_user
$pass = Get-Content secrets/mongodb_password
python scripts/data-migration-import.py --dest-type mongodb `
    --mongo-uri "mongodb://${user}:${pass}@localhost:27017/?authSource=admin" `
    --export-dir "data-export-20260212T170000"
```

## Collection-Level Operations

Export or import individual collections:

```powershell
# Export only sources and archives
python scripts/data-migration-export.py --source-type cosmos `
    --cosmos-endpoint ... --cosmos-key ... `
    --collections sources,archives

# Import only summaries (e.g., after re-generating)
python scripts/data-migration-import.py --dest-type mongodb `
    --export-dir "data-export-20260212T170000" `
    --collections summaries
```

## Handling ID Formats

| Backend | `_id` / `id` Format | Partition Key | Notes |
|---------|---------------------|---------------|-------|
| Azure Cosmos DB (per-collection) | 16-char hex string | `/id` | Most containers |
| Azure Cosmos DB (`documents` shared) | String | `/collection` | Shared container; rarely used by app |
| MongoDB | ObjectId or string | N/A | Depends on insert method |

The export scripts normalize `_id` to string format. The import scripts preserve the string `_id`, which is compatible with both backends. The `InMemoryDocumentStore` (used in tests) also uses string IDs.

## Troubleshooting

### Cosmos DB rate limiting (HTTP 429)

Large imports may hit RU/s limits. The Python import script automatically retries on 429 errors.
To increase throughput, temporarily scale up RU/s:

```powershell
az cosmosdb sql database throughput update `
    --account-name copilot-cos-dev-y6f2c `
    --resource-group copilot-app-rg `
    --name copilot `
    --max-throughput 10000
```

### Import conflicts (duplicate `_id`)

By default, the import script uses upsert mode so existing documents are overwritten. To skip duplicates instead:

```powershell
python scripts/data-migration-import.py --dest-type mongodb `
    --export-dir "data-export-20260212T170000" `
    --mode merge
```

### Large collections timeout

For very large Cosmos DB databases, the export may be slow due to cross-partition queries.
The Python export script reads all items per container and writes NDJSON. No batch size parameter is needed — the SDK handles pagination automatically.

## Security Considerations

- Export directories may contain PII (email addresses, message content). Store securely and delete after migration.
- Connection strings and keys are passed via CLI arguments — never committed to source control.
- **Prefer RBAC auth** (`--use-rbac`) over connection string keys when possible. RBAC uses short-lived Azure AD tokens, avoids key rotation concerns, and integrates with Azure audit logging.
- RBAC tokens expire after ~1 hour. For large exports/imports that may exceed this, use connection string auth instead.
- When using connection string auth, rotate Cosmos DB keys after migration if the key was shared with temporary environments.
