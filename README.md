<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Copilot-for-Consensus
**An open-source AI assistant that ingests mailing list discussions, summarizes threads, and surfaces consensus for technical working groups.**

***

## Pre-commit Hook

Install and enable the pre-commit hook to run the header check locally before commits:

```
pip install pre-commit
pre-commit install
```

You can run it against all files at any time:

```
pre-commit run --all-files
```


## Overview
Copilot-for-Consensus is designed to **scale institutional memory and accelerate decision-making** in technical communities like IETF working groups. It uses **LLM-powered summarization and insight extraction** to help participants keep up with mailing list traffic, track draft evolution, and identify consensus or dissent.

This project aims to be:
- **Containerized** for easy deployment.
- **Microservice-based** for modularity and scalability.
- **Deployable locally** using a lightweight micro-LLM or **in Azure Cloud** for enterprise-scale workloads.
- Built primarily in **Python** for accessibility and community contribution.

***

## Key Features (MVP)
- **Mailing List Ingestion:** Fetch archives via rsync or IMAP.
- **Parsing & Normalization:** Use Python `mailbox` or equivalent for structured extraction.
- **Vector Store Abstraction:** Modular backend support (FAISS, in-memory, future: Qdrant, Azure) for semantic search.
- **Summarization Engine:** Extractive + abstractive summaries powered by LLMs.
- **Consensus Detection:** Identify agreement/dissent signals in threads.
- **Draft Tracking:** Monitor mentions and evolution of RFC drafts.
- **Transparency:** Inline citations linking summaries to original messages.

***

## Long-Term Vision
Beyond summarization, Copilot-for-Consensus will evolve into an **interactive subject matter expert** that:
- **Understands RFCs and mailing list history** for deep contextual answers.
- Provides **semantic search and Q&A** across technical archives.
- Supports **multi-modal knowledge** (text, diagrams, code snippets).
- Offers **real-time collaboration tools** for chairs and contributors.
- Integrates with **standards governance workflows** for better decision tracking.

***

## License & Code Headers

This project is distributed under the **MIT License**. All files that support comments must include an SPDX license header:

```
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors
```

**Header formats by file type:**
- **Python, Bash, YAML, Docker Compose:** Use `#` comments
  ```python
  # SPDX-License-Identifier: MIT
  # Copyright (c) 2025 Copilot-for-Consensus contributors
  ```
- **Markdown, HTML, XML:** Use `<!-- -->` comments
  ```html
  <!-- SPDX-License-Identifier: MIT
       Copyright (c) 2025 Copilot-for-Consensus contributors -->
  ```
- **JavaScript/TypeScript:** Use `//` comments
  ```typescript
  // SPDX-License-Identifier: MIT
  // Copyright (c) 2025 Copilot-for-Consensus contributors
  ```

All contributions must include appropriate SPDX headers. See [CONTRIBUTING.md](documents/CONTRIBUTING.md) for details.

***

## Architecture

### Microservices
- **Ingestion Service:** Fetches mailing list archives from various sources
- **Parsing Service:** Extracts and normalizes email messages
- **Chunking Service:** Splits messages into manageable chunks
- **Embedding Service:** Generates vector embeddings for semantic search
- **Orchestrator Service:** Coordinates workflow across services
- **Summarization Service:** Creates summaries using LLMs
- **Reporting Service:** Provides API and UI for accessing results

### Infrastructure Components
- **MongoDB** (`documentdb`): Document storage for structured data
- **Qdrant** (`vectorstore`): Vector database for semantic search
- **Ollama**: Local LLM runtime for embeddings and generation
- **RabbitMQ** (`messagebus`): Message broker for inter-service communication
- **Prometheus** (`monitoring`): Metrics collection and storage
- **Grafana**: Metrics visualization and dashboards
- **Loki**: Centralized log aggregation
- **Promtail**: Log collection agent
- **Error Reporting Service**: Centralized error tracking and debugging

### Observability Stack

The system includes a comprehensive observability stack for monitoring, logging, and error tracking:

#### Metrics (Prometheus + Grafana)
- **Prometheus** scrapes metrics from all services on port 9090
- **Grafana** provides visualization dashboards on port 3000
- Pre-configured dashboards for:
  - System health and service uptime
  - Ingestion and parsing throughput
  - Embedding latency percentiles
  - Vector store size and performance

Access Grafana at `http://localhost:3000` (default credentials: admin/admin)

#### Logging (Loki + Promtail)
- **Loki** aggregates logs from all services on port 3100
- **Promtail** scrapes Docker container logs automatically
- Logs are labeled by service, container, and level
- Query logs through Grafana's Explore interface

#### Error Tracking
- **Error Reporting Service** provides centralized error aggregation on port 8081
- Web UI at `http://localhost:8081/ui` for browsing errors
- REST API at `/api/errors` for programmatic access
- Filters by service, error level, and error type
- Statistics dashboard showing error distribution

***

## Quick Start

### Prerequisites
- Docker and Docker Compose
- 8GB+ RAM recommended
- 20GB+ disk space for models and data

### Running the Stack

1. Clone the repository:
```bash
git clone https://github.com/Alan-Jowett/CoPilot-For-Consensus.git
cd CoPilot-For-Consensus
```

2. Start all services:
```bash
docker compose up -d
```

3. Initialize the database:
```bash
# Database initialization runs automatically via db-init service
docker compose logs db-init
```

4. Access the services:
- **Reporting UI**: http://localhost:8080
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)
- **Error Tracking**: http://localhost:8081/ui
- **Prometheus**: http://localhost:9090
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)

5. Pull an LLM model (first time only):
```bash
docker compose exec ollama ollama pull mistral
```

6. Run ingestion:
```bash
docker compose run --rm ingestion
```

### Viewing Logs

View logs for all services:
```bash
docker compose logs -f
```

View logs for a specific service:
```bash
docker compose logs -f parsing
```

Query centralized logs in Grafana:
1. Open http://localhost:3000
2. Navigate to Explore
3. Select "Loki" datasource
4. Query: `{service="parsing"}` to see parsing service logs

***  

## License Header Check

This repository includes a utility to verify that files contain both an SPDX license identifier and a copyright header.

### Run

On Windows PowerShell:

```
python scripts/check_license_headers.py --root .
```
### CI enforcement

All pull requests run a GitHub Action that executes the same header check. If any file that should have headers is missing either the SPDX identifier or the copyright line, the workflow fails.


Common flags:
- `--extensions`: space-separated list of extensions to check (default covers common source and config files)
- `--filenames`: specific filenames to include (default includes `Dockerfile`)
- `--exclude`: directories or patterns to exclude (defaults include common build and cache folders)
- `--ignore-file`: path to a repository-relative ignore file (default `.headercheckignore`)

### Ignore file

You can create `.headercheckignore` at the repo root to exclude additional folders or patterns, one per line. Lines starting with `#` are comments.

