<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Log Mining (Drain3)

This repo includes a reusable utility to **cluster/minimize** large logs by mining templates (Drain3) and emitting **anomaly-focused samples**.

Use it when you have:
- large `docker compose logs` captures
- Azure Container Apps console exports (`ContainerAppConsoleLogs_CL` with `Log_s`)
- Azure Log Analytics query output (`az monitor log-analytics query -o json` with `tables/rows`)

## Install

From repo root:

```powershell
python -m pip install -r scripts/requirements.txt
```

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

## What to Look At

Start with:
- Markdown report: top `ERROR`/`WARNING` templates + samples
- JSON report: `anomalies.rare_templates` for low-frequency log types
