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
- **Python, Bash, Docker Compose:** Use `#` comments
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

All contributions must include appropriate SPDX headers. See [CONTRIBUTING.md](./CONTRIBUTING.md) for details.

***

## Architecture

The system follows a **microservice-based, event-driven architecture** where services communicate asynchronously through a message bus (RabbitMQ) and store data in MongoDB and Qdrant. This design ensures loose coupling, scalability, and resilience.

For detailed architecture documentation, design patterns, and service interactions, see [documents/ARCHITECTURE.md](./documents/ARCHITECTURE.md).

### Microservices

#### Processing Pipeline
- **Ingestion Service**: Fetches mailing list archives from various sources (rsync, IMAP, HTTP)
- **Parsing Service**: Extracts and normalizes email messages from `.mbox` files, identifies threads, detects RFC/draft mentions
- **Chunking Service**: Splits messages into token-aware, semantically coherent chunks suitable for embedding
- **Embedding Service**: Generates vector embeddings using local (SentenceTransformers, Ollama) or cloud (Azure OpenAI) models
- **Orchestrator Service**: Coordinates workflow across services, manages retrieval-augmented generation (RAG)
- **Summarization Service**: Creates summaries using LLMs with configurable backends

#### User-Facing Services
- **Reporting Service**: Provides HTTP API and web UI for accessing summaries and insights (port 8080)
- **Error Reporting Service**: Centralized error tracking and debugging interface (port 8081)

### Infrastructure Components

#### Storage Layer
- **MongoDB** (`documentdb`): Document storage for messages, chunks, threads, and summaries
- **Qdrant** (`vectorstore`): Vector database for semantic search and similarity queries

#### Integration Layer
- **RabbitMQ** (`messagebus`): Message broker enabling asynchronous, event-driven communication between services
- **Ollama**: Local LLM runtime for embeddings and text generation (fully offline capable)
  - Supports optional GPU acceleration (10-100x speedup) - see [documents/OLLAMA_GPU_SETUP.md](./documents/OLLAMA_GPU_SETUP.md)

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
  - Failed queue monitoring

Access Grafana at `http://localhost:3000` (default credentials: admin/admin)

#### Logging (Loki + Promtail)
- **Loki** aggregates logs from all services on port 3100
- **Promtail** scrapes Docker container logs automatically
- Logs are labeled by service, container, and level
- Query logs through Grafana's Explore interface

#### Failed Queue Management
- **Failed queues** capture messages that fail after retry exhaustion
- Automated alerts for queue buildup (Warning >50, Critical >200, Emergency >1000)
- CLI tool for inspection, requeue, and purge operations: `scripts/manage_failed_queues.py`
- Dedicated Grafana dashboard: **Failed Queues Overview**
- See [documents/FAILED_QUEUE_OPERATIONS.md](./documents/FAILED_QUEUE_OPERATIONS.md) for operational runbook

### Adapters

The system uses adapter modules to decouple core business logic from external dependencies:

- **copilot_storage**: Document store abstraction (MongoDB, in-memory)
- **copilot_events**: Event publishing, subscription, and schema validation
- **copilot_config**: Unified configuration management with schema validation
- **copilot_schema_validation**: JSON schema validation for messages and events
- **copilot_vectorstore**: Vector store abstraction (Qdrant, FAISS)
- **copilot_metrics**: Metrics collection (Prometheus)
- **copilot_logging**: Structured logging
- **copilot_reporting**: Error reporting

See [adapters/README.md](./adapters/README.md) for detailed adapter documentation.

***

## Quick Start

**For detailed local development setup, see [docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md).**

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
- **Prometheus**: http://localhost:9090
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)

5. Pull an LLM model (first time only):
```bash
docker compose exec ollama ollama pull mistral
```

6. **(Optional) Enable GPU acceleration** for 10-100x faster inference:
   - See [documents/OLLAMA_GPU_SETUP.md](./documents/OLLAMA_GPU_SETUP.md) for setup instructions
   - Requires NVIDIA GPU with drivers and nvidia-container-toolkit
   - Verify GPU support: `./scripts/check_ollama_gpu.sh`

7. Run ingestion:
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

## Database Smoke Testing

A simple smoke test script is available to verify MongoDB connectivity and schema acceptance:

```bash
# Run from within a MongoDB container (after stack is up)
docker compose exec documentdb mongosh \
  "mongodb://${DOC_DB_ADMIN_USERNAME:-admin}:${DOC_DB_ADMIN_PASSWORD:-PLEASE_CHANGE_ME}@localhost:27017/admin" \
  /test/test_insert.js

# Or from the host (if mongosh is installed locally)
mongosh "mongodb://${DOC_DB_ADMIN_USERNAME:-admin}:${DOC_DB_ADMIN_PASSWORD:-PLEASE_CHANGE_ME}@localhost:27017/admin" \
  ./infra/test/test_insert.js
```

This script:
- Inserts a minimal `messages` document with required fields
- Verifies the insert was acknowledged by MongoDB
- Prints success confirmation with the inserted message_id
- Helps isolate connection vs. schema issues during troubleshooting

**Note:** The test inserts a document with `message_id: "smoke-test-message-001"`. You may want to clean it up after testing:
```bash
docker compose exec documentdb mongosh \
  -u ${DOC_DB_ADMIN_USERNAME:-admin} \
  -p ${DOC_DB_ADMIN_PASSWORD:-PLEASE_CHANGE_ME} \
  --authenticationDatabase admin \
  copilot \
  --eval 'db.messages.deleteOne({message_id: "smoke-test-message-001"})'
```

***  

## Documentation

Comprehensive documentation is available throughout the repository:

### Core Documentation
- **[CONTRIBUTING.md](./CONTRIBUTING.md)**: Contribution guidelines, development setup, coding standards
- **[CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)**: Community standards and behavior expectations
- **[GOVERNANCE.md](./GOVERNANCE.md)**: Project governance, decision-making, and maintainer roles
- **[SECURITY.md](./SECURITY.md)**: Security policy and vulnerability reporting

### Technical Documentation
- **[documents/ARCHITECTURE.md](./documents/ARCHITECTURE.md)**: Detailed system architecture, design patterns, and service interactions
- **[documents/SCHEMA.md](./documents/SCHEMA.md)**: Database schemas and message bus event definitions
- **[documents/FORWARD_PROGRESS.md](./documents/FORWARD_PROGRESS.md)**: Idempotency, retry logic, and error handling patterns
- **[documents/SERVICE_MONITORING.md](./documents/SERVICE_MONITORING.md)**: Observability, metrics, and logging best practices
- **[documents/FAILED_QUEUE_OPERATIONS.md](./documents/FAILED_QUEUE_OPERATIONS.md)**: Failed queue management and troubleshooting

### Development Guides
- **[docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md)**: Complete local development setup, debugging, and testing guide
- **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)**: Integration testing strategy, test organization, and CI/CD integration
- **[docs/CONVENTIONS.md](./docs/CONVENTIONS.md)**: Documentation conventions, style guide, and contribution standards

### Service Documentation
Each microservice has a comprehensive README:
- [Ingestion Service](./ingestion/README.md)
- [Parsing Service](./parsing/README.md)
- [Chunking Service](./chunking/README.md)
- [Embedding Service](./embedding/README.md)
- [Orchestrator Service](./orchestrator/README.md)
- [Summarization Service](./summarization/README.md)
- [Reporting Service](./reporting/README.md)
- [Error Reporting Service](./error-reporting/README.md)

### Adapter Documentation
- **[adapters/README.md](./adapters/README.md)**: Overview of the adapter layer and available adapters

***

## License Header Check

This repository includes a utility to verify that files contain both an SPDX license identifier and a copyright header.

### Run

Run the check manually:

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
- `--root`: root directory to search for files (default is current directory)
- `--head-lines`: number of lines at the top of each file to check for headers (default is 30)

### Ignore file

You can create `.headercheckignore` at the repo root to exclude additional folders or patterns, one per line. Lines starting with `#` are comments.

