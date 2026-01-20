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

### Azure Container Apps console export

If you exported `ContainerAppConsoleLogs_CL` to JSON (array of objects) with a `Log_s` column:

```powershell
python -m scripts.log_mining --input logs-azure-console-sample.json --format azure-console --group-by service --output azure_mined.json
```

### Azure Log Analytics query output (`az monitor log-analytics query -o json`)

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
