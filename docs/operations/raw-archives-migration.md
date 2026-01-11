<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Raw Archives Container Migration

The Azure Storage container for raw email archives changed from `archives` to `raw-archives`.
This is a breaking change for existing Azure deployments. Use one of the options below.

## Option 1: Migrate data to the new container (recommended)

Using AzCopy:

```bash
# Copy from old container to new container (same account)
azcopy copy "https://<account>.blob.core.windows.net/archives" \
             "https://<account>.blob.core.windows.net/raw-archives" \
             --recursive=true
```

Using Azure CLI:

```bash
# Create destination container if missing
az storage container create \
  --name raw-archives \
  --account-name <account>

# Server-side copy (example for a single blob); script/loop for all blobs
az storage blob copy start \
  --destination-container raw-archives \
  --destination-blob <blob-name> \
  --source-container archives \
  --account-name <account>
```

## Option 2: Keep backward compatibility temporarily

Override the container name to `archives` in your deployment until migration is complete.

- Docker Compose: set `ARCHIVE_STORE_CONTAINER=archives` for services using Azure Blob
- Azure Bicep/Container Apps: set the environment variable `ARCHIVE_STORE_CONTAINER` to `archives`

## Verification

- After migration, run ingestion and ensure new archives land in `raw-archives`
- Parsing should retrieve existing and new archives from `raw-archives`

## Notes

- Managed identity scenarios are unaffected—only the container name changed.
- For large datasets, prefer AzCopy for faster, resilient transfer.
