<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Log Mining (Drain3)

This repo includes a reusable utility to **cluster/minimize** large logs by mining templates (Drain3) and emitting **anomaly-focused samples**.

Use it when you have:
- large `docker compose logs` captures
- Azure Container Apps console exports (`ContainerAppConsoleLogs_CL` with `Log_s`) (legacy)
- Azure Diagnostic Settings NDJSON from Blob Storage (`TimeGenerated`/`Category`/`Level`/`ContainerAppName`/`Message`)
- Azure Log Analytics query output (`az monitor log-analytics query -o json` with `tables/rows`) (legacy)

## Install

From repo root:

```powershell
python -m pip install -r scripts/requirements.txt
```

## Procedure (Azure Container Apps, Blob-archived logs)

This is the recommended workflow for production incidents because it does not require Log Analytics.

### 1) Prereqs

- Container Apps logs are archived to Blob Storage via Diagnostic Settings.
  - See: `docs/operations/blob-logging.md`
- Azure CLI authenticated: `az login`
- Blob read RBAC on the storage account (e.g., **Storage Blob Data Reader**)

### 2) Identify the storage account

If you don't already know which storage account is receiving archived logs:

```powershell
$rg = "<resource-group>"
az storage account list -g $rg -o table
```

Pick the storage account used for log archiving.

### 3) Export + mine the last 6 hours (console logs)

This downloads the matching NDJSON blobs and runs the miner, producing:
- a JSON report (templates + samples)
- a Markdown report focused on `ERROR`/`WARNING`

```powershell
$storage = "<storage-account-name>"
./scripts/export_blob_logs_rca.ps1 -StorageAccountName $storage -Timespan PT6H
```

Output defaults to `logs/azure/<storage-account-name>/rca/`.

### 4) Optional: include system logs

System logs can include platform/runtime issues (startup, probes, etc):

```powershell
$storage = "<storage-account-name>"
./scripts/export_blob_logs_rca.ps1 -StorageAccountName $storage -Timespan PT6H -ContainerName insights-logs-containerappsystemlogs
```

### 5) Optional: scope to one app (Prefix)

If you want to mine just one Container App, pass a `-Prefix` matching the Azure Monitor blob layout.

```powershell
$sub = az account show --query id -o tsv
$rg = "<resource-group>"
$app = "<container-app-name>"

$prefix = "resourceId=/SUBSCRIPTIONS/$sub/RESOURCEGROUPS/$rg/PROVIDERS/MICROSOFT.APP/CONTAINERAPPS/$app/"
./scripts/export_blob_logs_rca.ps1 -StorageAccountName "<storage-account-name>" -Timespan PT6H -Prefix $prefix
```

Note: blob paths commonly use uppercased segments in `resourceId=...`. If you get zero results, list a few blobs and copy the prefix casing from the returned `name`.

## Common Workflows

### 1) Mine templates + generate Markdown (recommended)

```powershell
python -m scripts.log_mining --input logs.txt --format docker --group-by service --output logs_mined.json --output-markdown logs_mined_errors_warnings.md --focus-levels ERROR,WARNING
```

### 1a) Stream from Docker Compose (last 24h)

This reads from stdin (omit `--input`). Use `--no-color` to avoid ANSI escape codes.

```powershell
docker compose logs --since 24h --no-color |
  python -m scripts.log_mining --format docker --group-by service --output mined_24h.json --output-markdown mined_24h_errors_warnings.md
```

### 1b) Stream + follow (live tail)

This will keep running until you stop it (Ctrl+C).

```powershell
docker compose logs -f --since 24h --no-color |
  python -m scripts.log_mining --format docker --group-by service --output mined_stream.json --output-markdown mined_stream_errors_warnings.md
```

### 2) Re-render Markdown from an existing JSON report (no re-mining)

```powershell
python -m scripts.log_mining --input logs_mined.json --input-is-report --output-markdown logs_mined_errors_warnings.md --focus-levels ERROR,WARNING
```

### 3) Azure Log Analytics query JSON output

```powershell
python -m scripts.log_mining --input path/to/az-query.json --format azure-law --group-by service --output law_mined.json --output-markdown law_mined_errors_warnings.md
```

### 4) Azure Diagnostic Settings (Blob Storage NDJSON)

If your Container Apps environment is configured to archive logs to Blob Storage via Diagnostic Settings, logs are stored as NDJSON. Point the tool at an NDJSON file (or a concatenated set) and use `azure-diagnostics`:

```powershell
python -m scripts.log_mining --input aca-console.ndjson --format azure-diagnostics --group-by service --output diag_mined.json --output-markdown diag_mined_errors_warnings.md
```

## Troubleshooting

- **No blobs selected / empty export**: verify the storage account and container names, and try a larger `-Timespan` (e.g., `PT24H`).
- **Access denied**: ensure your identity has **Storage Blob Data Reader** on the storage account.
- **Too much data**: use `-Prefix` to target a specific app, or reduce `-Timespan`.

## What to Look At

Start with:
- Markdown report: top `ERROR`/`WARNING` templates + samples
- JSON report: `anomalies.rare_templates` for low-frequency log types
