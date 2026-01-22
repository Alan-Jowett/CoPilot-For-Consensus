<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Log Mining (Drain3)

This utility clusters/minimizes logs by:

1. Normalizing obvious variables (timestamps, GUIDs, IPs, URLs, numbers)
2. Mining templates via **Drain3**
3. Sampling **rare** templates and representative examples for anomaly hunting

## Install

From repo root:

```powershell
python -m pip install -r scripts/requirements.txt
```

## Usage

### Docker Compose logs (combined)

```powershell
python -m scripts.log_mining --input logs.txt --format docker --group-by service --output logs_mined.json --output-markdown logs_mined.md
```

### Pipe from docker compose

```powershell
docker compose logs --no-color | python -m scripts.log_mining --format docker --output logs_mined.json
```

### Pipe from docker compose (last 24h)

```powershell
docker compose logs --since 24h --no-color | python -m scripts.log_mining --format docker --group-by service --output logs_mined_24h.json --output-markdown logs_mined_24h_errors_warnings.md
```

### Pipe from docker compose (follow / live)

```powershell
docker compose logs -f --since 24h --no-color | python -m scripts.log_mining --format docker --group-by service --output logs_mined_stream.json --output-markdown logs_mined_stream_errors_warnings.md
```

### Azure Container Apps console export

If you exported `ContainerAppConsoleLogs_CL` to JSON (array of objects) with a `Log_s` column:

```powershell
python -m scripts.log_mining --input logs-azure-console-sample.json --format azure-console --group-by service --output azure_mined.json

### Azure Diagnostic Settings (Blob Storage NDJSON)

If you enabled Container Apps log archiving to Blob Storage via Diagnostic Settings, the logs are typically stored as **NDJSON** (one JSON object per line) and contain fields like `TimeGenerated`, `Category`, `Level`, `ContainerAppName`, and `Message`.

Download a blob (or concatenate multiple blobs) and run:

```powershell
python -m scripts.log_mining --input aca-console.ndjson --format azure-diagnostics --group-by service --output diag_mined.json --output-markdown diag_mined_errors_warnings.md
```
```

### Azure Log Analytics query output (`az monitor log-analytics query -o json`) (legacy)

If you saved the raw `az` query result JSON (with `tables/columns/rows`):

```powershell
python -m scripts.log_mining --input logs/azure/copilot-law-dev-y6f2c/rca/validation_sample.json --format azure-law --group-by service --output law_mined.json
```

## Report output

The output JSON includes:
- `meta`: run metadata and totals
- `templates`: mined templates with counts and per-template samples
- `anomalies.rare_templates`: templates with count <= `--rare-template-threshold` (default: 5)

For anomaly hunting, start with `anomalies.rare_templates` and the `samples`/`first_seen_line` fields.

## Human-readable Markdown

The Markdown output is designed for triage and defaults to focusing on `ERROR` and `WARNING` templates.

To generate Markdown from an existing JSON report (no re-mining):

```powershell
python -m scripts.log_mining --input logs_mined.json --input-is-report --output-markdown logs_mined.md
```
