<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Scripts

This folder contains developer/ops helper scripts.

## Quick start

Install dependencies for the Python scripts in this directory:

```powershell
python -m pip install -r scripts/requirements.txt
```

## Notable scripts

- `peek_servicebus_dlq.py` — peeks (non-destructively) at Azure Service Bus topic subscription dead-letter messages. See the script docstring for usage.
- `aca_blob_log_errors.ps1` / `aca_blob_log_errors.py` — scans archived Azure Container Apps logs in Blob Storage for “error-ish” records.
- `aca_scale_status.ps1` — summarizes active revision replica counts for Container Apps (useful for verifying scale-to-zero).
- `get_data_counts.py` — lightweight snapshot of counts for archives/emails/chunks/embeddings/reports (prefers Azure Monitor metrics for Cosmos doc counts; falls back to Mongo `collStats` + Qdrant `points_count`). Also emits `documents_total` (Cosmos database total) by default and supports `--strict` for non-zero exit on partial results. Note: embeddings counts require network access to Qdrant (often internal-only in ACA).
