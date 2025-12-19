<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Copilot-for-Consensus

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**An open-source AI assistant that ingests mailing list discussions, summarizes threads, and surfaces consensus for technical working groups.**

📚 **[Documentation](#documentation)** | 🚀 **[Quick Start](#quick-start)** | 🏗️ **[Architecture](./documents/ARCHITECTURE.md)** | 🤝 **[Contributing](./CONTRIBUTING.md)** | 📋 **[Governance](./GOVERNANCE.md)**

***

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

***

## Overview

Copilot-for-Consensus is designed to **scale institutional memory and accelerate decision-making** in technical communities like IETF working groups. It uses **LLM-powered summarization and insight extraction** to help participants keep up with mailing list traffic, track draft evolution, and identify consensus or dissent.

This project aims to be:
- **Containerized** for easy deployment
- **Microservice-based** for modularity and scalability
- **Deployable locally** using lightweight open-source LLMs or **in Azure Cloud** for enterprise-scale workloads
- Built primarily in **Python** for accessibility and community contribution
- **Production-ready** with comprehensive observability, error handling, and testing

***

## Key Features

### Core Capabilities
- **Mailing List Ingestion**: Fetch archives via rsync, IMAP, or HTTP from multiple sources
- **Parsing & Normalization**: Extract structured data from `.mbox` files with thread detection and RFC/draft mention tracking
- **Semantic Chunking**: Token-aware splitting with semantic coherence for optimal embedding
- **Vector Search**: Fast similarity search using Qdrant with configurable backends (FAISS, in-memory)
- **LLM-Powered Summarization**: Extractive + abstractive summaries with configurable backends:
  - **Local**: Ollama (Mistral, Llama 2, etc.) for fully offline operation
  - **Cloud**: Azure OpenAI, OpenAI API for production scale
  - **Alternative**: llama.cpp with AMD GPU support
- **Consensus Detection**: Identify agreement/dissent signals in threads (in development)
- **Draft Tracking**: Monitor mentions and evolution of RFC drafts (in development)
- **Transparency**: Inline citations linking summaries to original messages

### Production Features
- **Event-Driven Architecture**: Asynchronous message bus (RabbitMQ) for loose coupling
- **Observability Stack**: Prometheus metrics, Grafana dashboards, Loki logging, and Promtail log aggregation
- **Error Handling**: Retry policies, failed queue management, and centralized error reporting
- **Idempotency**: All operations are idempotent with deduplication support
- **GPU Acceleration**: Optional NVIDIA (Ollama) or AMD (llama.cpp) GPU support for 10-100x faster inference
- **Schema Validation**: JSON schema validation for all messages and events
- **Health Checks**: Comprehensive health checks for all services

***

## Long-Term Vision

Beyond summarization, Copilot-for-Consensus will evolve into an **interactive subject matter expert** that:
- **Understands RFCs and mailing list history** for deep contextual answers
- Provides **semantic search and Q&A** across technical archives
- Supports **multi-modal knowledge** (text, diagrams, code snippets)
- Offers **real-time collaboration tools** for chairs and contributors
- Integrates with **standards governance workflows** for better decision tracking

***

## Architecture

The system follows a **microservice-based, event-driven architecture** where services communicate asynchronously through a message bus (RabbitMQ) and store data in MongoDB and Qdrant. This design ensures loose coupling, scalability, and resilience.

For detailed architecture documentation, design patterns, and service interactions, see [documents/ARCHITECTURE.md](./documents/ARCHITECTURE.md).

### Services Overview

| Service | Purpose | Port(s) | Status |
|---------|---------|---------|--------|
| **Processing Pipeline** | | | |
| Ingestion | Fetches mailing list archives from remote sources | 8000 (localhost) | Production |
| Parsing | Extracts and normalizes email messages from archives | - | Production |
| Chunking | Splits messages into semantic chunks for embedding | - | Production |
| Embedding | Generates vector embeddings for semantic search | - | Production |
| Orchestrator | Coordinates RAG workflow and summarization | - | Production |
| Summarization | Creates summaries using configurable LLM backends | - | Production |
| **User-Facing** | | | |
| Reporting API | HTTP API for accessing summaries and insights | 8080 (public) | Production |
| Web UI | React SPA for viewing reports | 8084 (localhost) | Production |
| **Infrastructure** | | | |
| MongoDB | Document storage for messages and summaries | 27017 (localhost) | Production |
| Qdrant | Vector database for semantic search | 6333 (localhost) | Production |
| RabbitMQ | Message broker for event-driven communication | 5672, 15672 (localhost) | Production |
| Ollama | Local LLM runtime (offline capable) | 11434 (localhost) | Production |
| llama.cpp | Alternative LLM runtime with AMD GPU support | 8081 (localhost) | Optional |
| **Observability** | | | |
| Prometheus | Metrics collection and aggregation | 9090 (localhost) | Production |
| Grafana | Monitoring dashboards and visualization | 3000 (public) | Production |
| Loki | Log aggregation | 3100 (localhost) | Production |
| Promtail | Log scraping from Docker containers | - | Production |
| Pushgateway | Metrics push gateway for batch jobs | - | Production |

**Note**: Services marked as "public" (0.0.0.0) are accessible from outside the host. All other services are bound to localhost (127.0.0.1) for security. See [documents/EXPOSED_PORTS.md](./documents/EXPOSED_PORTS.md) for security details.

### Microservices

#### Processing Pipeline
- **Ingestion Service**: Fetches mailing list archives from various sources (rsync, IMAP, HTTP)
- **Parsing Service**: Extracts and normalizes email messages from `.mbox` files, identifies threads, detects RFC/draft mentions
- **Chunking Service**: Splits messages into token-aware, semantically coherent chunks suitable for embedding
- **Embedding Service**: Generates vector embeddings using local (SentenceTransformers, Ollama) or cloud (Azure OpenAI) models
- **Orchestrator Service**: Coordinates workflow across services, manages retrieval-augmented generation (RAG)
- **Summarization Service**: Creates summaries using LLMs with configurable backends (OpenAI, Azure OpenAI, Ollama, llama.cpp)

#### User-Facing Services
- **Reporting Service**: Provides HTTP API for accessing summaries and insights (port 8080)
- **Web UI**: React SPA for browsing reports and insights (port 8084)

### Infrastructure Components

#### Storage Layer
- **MongoDB** (`documentdb`): Document storage for messages, chunks, threads, and summaries
- **Qdrant** (`vectorstore`): Vector database for semantic search and similarity queries

#### Integration Layer
- **RabbitMQ** (`messagebus`): Message broker enabling asynchronous, event-driven communication between services
- **Ollama**: Local LLM runtime for embeddings and text generation (fully offline capable)
  - Supports optional GPU acceleration (10-100x speedup) - see [documents/OLLAMA_GPU_SETUP.md](./documents/OLLAMA_GPU_SETUP.md)
  - NVIDIA GPU support (recommended for performance)
- **llama.cpp** (optional): Alternative local LLM runtime with AMD GPU support (Vulkan/ROCm) - see [AMD GPU Setup Guide](./documents/LLAMA_CPP_AMD_SETUP.md)

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

- **copilot_archive_fetcher**: Fetches archives from remote sources
- **copilot_archive_store**: Archive storage abstraction
- **copilot_auth**: Authentication and authorization
- **copilot_chunking**: Text chunking algorithms
- **copilot_config**: Unified configuration management with schema validation
- **copilot_consensus**: Consensus detection logic
- **copilot_draft_diff**: RFC draft difference tracking
- **copilot_embedding**: Embedding generation abstraction
- **copilot_events**: Event publishing, subscription, and schema validation
- **copilot_logging**: Structured logging
- **copilot_metrics**: Metrics collection (Prometheus)
- **copilot_reporting**: Error reporting
- **copilot_schema_validation**: JSON schema validation for messages and events
- **copilot_startup**: Service startup coordination
- **copilot_storage**: Document store abstraction (MongoDB, in-memory)
- **copilot_summarization**: Summarization logic abstraction
- **copilot_vectorstore**: Vector store abstraction (Qdrant, FAISS)

See [adapters/README.md](./adapters/README.md) for detailed adapter documentation.

***

## Quick Start

**For detailed local development setup, see [documents/LOCAL_DEVELOPMENT.md](./documents/LOCAL_DEVELOPMENT.md).**

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
- **Reporting API**: http://localhost:8080
- **Web UI**: http://localhost:8084
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)

For the full list of exposed ports and security considerations, see [documents/EXPOSED_PORTS.md](documents/EXPOSED_PORTS.md).

**Note:** The Mistral LLM model is automatically downloaded on first startup via the `ollama-model-loader` service when using the default Ollama backend. This may take several minutes depending on your internet connection. Models are stored in the `ollama_models` Docker volume for persistence.

5. **(Optional) Enable GPU acceleration** for 10-100x faster inference:
   - **NVIDIA GPU** (recommended): See [documents/OLLAMA_GPU_SETUP.md](./documents/OLLAMA_GPU_SETUP.md)
     - Requires NVIDIA GPU with drivers and nvidia-container-toolkit
     - Verify GPU support:
       - Linux/macOS/WSL2: `./scripts/check_ollama_gpu.sh`
       - Windows PowerShell: `.\scripts\check_ollama_gpu.ps1`
       - Or directly: `docker exec ollama nvidia-smi`
   - **AMD GPU** (experimental): See [AMD GPU Setup Guide](./documents/LLAMA_CPP_AMD_SETUP.md) to enable llama.cpp with Vulkan/ROCm

6. Run ingestion to process test data:

   **Option A: Using test fixtures (recommended for first-time users):**
   ```bash
   # Start the continuously running ingestion service (exposes REST API on 8001)
   docker compose up -d ingestion

   # Copy the sample mailbox into the running container
   INGESTION_CONTAINER=$(docker compose ps -q ingestion)
   docker exec "$INGESTION_CONTAINER" mkdir -p /tmp/test-mailbox
   docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$INGESTION_CONTAINER":/tmp/test-mailbox/test-archive.mbox

   # Create the source via REST API
   curl -f -X POST http://localhost:8001/api/sources \
     -H "Content-Type: application/json" \
     -d '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'

   # Trigger ingestion via REST API
   curl -f -X POST http://localhost:8001/api/sources/test-mailbox/trigger
   ```

   **Option B: Using PowerShell helper (Windows):**
   ```powershell
   .\run_ingestion_test.ps1
   ```

   After ingestion completes, summaries will be available via the Reporting API at http://localhost:8080/api/reports

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

### Troubleshooting

**Services won't start:**
- Ensure Docker has at least 8GB RAM allocated
- Check for port conflicts:
  - Linux/macOS: `netstat -tuln | grep -E '(3000|8080|27017|5672|6333)'`
  - Windows PowerShell: `Get-NetTCPConnection -LocalPort 3000,8080,27017,5672,6333 -ErrorAction SilentlyContinue`
  - Or check service status: `docker compose ps`
- View service logs: `docker compose logs <service-name>`

**Ollama model pull fails:**
- Wait for ollama service to be healthy: `docker compose ps ollama`
- Check connectivity: `docker compose exec ollama ollama list`
- Retry: The ollama-model-loader service retries up to 5 times

**Database connection errors:**
- Verify MongoDB is healthy: `docker compose ps documentdb`
- Check credentials match `.env` file
- Run smoke test (see Database Smoke Testing section below)

**RabbitMQ connection errors:**
- Verify RabbitMQ is healthy: `docker compose ps messagebus`
- Check management UI: http://localhost:15672 (guest/guest)

For more troubleshooting, see [documents/LOCAL_DEVELOPMENT.md](./documents/LOCAL_DEVELOPMENT.md).

### Demo vs Production Setup

**Current setup is optimized for local development and integration testing:**
- Uses local Ollama for LLM inference (no API keys needed)
- All services run in Docker Compose on a single host
- In-memory queues (RabbitMQ) and local storage
- No authentication or TLS on most services

**For production deployments, consider:**
- **LLM Backend**: Use Azure OpenAI or OpenAI API for better performance and reliability
  - Set `LLM_BACKEND=azure` and configure `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT`
- **Message Queue**: Use managed RabbitMQ (e.g., CloudAMQP) or Azure Service Bus for durability
- **Storage**: Use Azure Cosmos DB or managed MongoDB for high availability
- **Vector Store**: Use managed Qdrant Cloud or Azure Cognitive Search
- **Observability**: Use Azure Monitor, Datadog, or New Relic for production monitoring
- **Security**: Enable TLS, authentication, and network policies (see [SECURITY.md](./SECURITY.md))
- **Scaling**: Deploy services independently with Kubernetes or Azure Container Apps

See [documents/ARCHITECTURE.md](./documents/ARCHITECTURE.md) for detailed production architecture guidance.

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
- **[documents/LOCAL_DEVELOPMENT.md](./documents/LOCAL_DEVELOPMENT.md)**: Complete local development setup, debugging, and testing guide
- **[documents/TESTING_STRATEGY.md](./documents/TESTING_STRATEGY.md)**: Integration testing strategy, test organization, and CI/CD integration
- **[documents/CONVENTIONS.md](./documents/CONVENTIONS.md)**: Documentation conventions, style guide, and contribution standards
- **[documents/EXPOSED_PORTS.md](./documents/EXPOSED_PORTS.md)**: Network ports reference, security considerations, and access control

### Service Documentation
Each microservice has a comprehensive README:
- [Ingestion Service](./ingestion/README.md)
- [Parsing Service](./parsing/README.md)
- [Chunking Service](./chunking/README.md)
- [Embedding Service](./embedding/README.md)
- [Orchestrator Service](./orchestrator/README.md)
- [Summarization Service](./summarization/README.md)
- [Reporting Service](./reporting/README.md)
- [Web UI](./ui/README.md)

### Adapter Documentation
- **[adapters/README.md](./adapters/README.md)**: Overview of the adapter layer and available adapters

***

## Development

### Local Development Setup

For detailed local development instructions, see [documents/LOCAL_DEVELOPMENT.md](./documents/LOCAL_DEVELOPMENT.md).

**Quick setup:**
1. Clone the repository
2. Install pre-commit hooks: `pip install pre-commit && pre-commit install`
3. Start services: `docker compose up -d`
4. Run tests: See [documents/TESTING_STRATEGY.md](./documents/TESTING_STRATEGY.md)

### Pre-commit Hooks

This project uses pre-commit hooks to enforce code quality and license headers:

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### Running Tests

**Integration tests:**
```bash
# Run all integration tests
docker compose -f docker-compose.yml up -d
python -m pytest tests/integration/

# Run specific service tests
python -m pytest tests/integration/test_parsing.py
```

**Unit tests:**
```bash
# Run unit tests for a specific service
cd parsing
python -m pytest tests/
```

**Port exposure validation:**
```bash
python tests/test_port_exposure.py
python tests/validate_port_changes.py
```

For comprehensive testing documentation, see [documents/TESTING_STRATEGY.md](./documents/TESTING_STRATEGY.md).

### Code Quality

**Static Analysis and Validation:**
This project uses comprehensive static analysis to catch attribute errors, type issues, and other problems before deployment:

```bash
# Install validation tools
pip install -r requirements-dev.txt

# Run all validation checks
python scripts/validate_python.py

# Run specific checks
python scripts/validate_python.py --tool ruff      # Fast linting
python scripts/validate_python.py --tool mypy      # Type checking
python scripts/validate_python.py --tool pyright   # Advanced type checking
python scripts/validate_python.py --tool pylint    # Attribute checking
python scripts/validate_python.py --tool import-tests  # Import smoke tests

# Auto-fix issues (where possible)
python scripts/validate_python.py --tool ruff --fix
```

The CI pipeline enforces:
- **Ruff**: Fast Python linter for syntax and style
- **MyPy**: Static type checker with strict mode
- **Pyright**: Advanced type checker for catching attribute errors
- **Pylint**: Attribute and member access validation
- **Import Tests**: Ensures all modules load without errors

**License headers:**
All source files must include SPDX license headers. Verify compliance:
```bash
python scripts/check_license_headers.py --root .
```

**Linting and formatting:**
The project uses ruff for Python formatting and pre-commit hooks for enforcement.

***

## Contributing

We welcome contributions from the community! This project follows open-source governance principles.

### How to Contribute

1. **Read the guidelines**: See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed instructions
2. **Follow the Code of Conduct**: Read [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
3. **Understand governance**: Review [GOVERNANCE.md](./GOVERNANCE.md) for project structure
4. **Report security issues**: Follow [SECURITY.md](./SECURITY.md) for vulnerability reporting

### Contribution Areas

- **Core features**: Implement new microservices or enhance existing ones
- **Adapters**: Add support for new storage, messaging, or LLM backends
- **Documentation**: Improve guides, add examples, fix errors
- **Testing**: Add test coverage, improve CI/CD
- **Performance**: Optimize processing pipelines, reduce latency
- **Observability**: Enhance metrics, dashboards, and logging

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes with appropriate tests
4. Ensure all tests pass and pre-commit hooks succeed
5. Submit a pull request with a clear description

All pull requests are reviewed according to the governance process documented in [GOVERNANCE.md](./GOVERNANCE.md).

***

## License

This project is distributed under the **MIT License**. See [LICENSE](./LICENSE) for details.

### License Headers

All files that support comments must include an SPDX license identifier and copyright header:

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

All contributions must include appropriate SPDX headers. The pre-commit hook and CI enforce this requirement.
