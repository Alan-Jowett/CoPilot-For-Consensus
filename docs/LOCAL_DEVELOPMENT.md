<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Local Development Guide

Complete setup for a local development environment including all services, infrastructure, and debugging tools.

## Prerequisites

### Required Software

- **Docker Desktop** (v20.10+): [Windows](https://docs.docker.com/desktop/install/windows-install/) | [macOS](https://docs.docker.com/desktop/install/mac-install/) | [Linux](https://docs.docker.com/engine/install/) + [Compose](https://docs.docker.com/compose/install/)
- **Git** (v2.30+)
- **Python 3.10+** (for local testing and scripts)
- **8GB+ RAM** (16GB recommended for full stack)
- **20GB+ free disk space** (for images, volumes, and models)

### Optional Tools

- **MongoDB Compass**: https://www.mongodb.com/products/compass
- **RabbitMQ Management** (included in Docker, accessible at http://localhost:15672)
- **Postman** or **curl** (for API testing)
- **VS Code** with Docker extension (recommended)

## Quick Start

```bash
# 1. Clone and enter directory
git clone https://github.com/Alan-Jowett/CoPilot-For-Consensus.git
cd CoPilot-For-Consensus

# 2. Start infrastructure (wait 30–60s for healthy status)
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail

# 3. Initialize database
docker compose run --rm db-init
docker compose run --rm db-validate

# 4. Validate vector store and LLM runtime
docker compose run --rm vectorstore-validate
docker compose run --rm ollama-validate

# 5. Start processing services
docker compose up -d parsing chunking embedding orchestrator summarization reporting ui

# 6. Download LLM model (Mistral, ~1.5GB, first-time only)
docker compose exec ollama ollama pull mistral

# 7. Test ingestion
# Follow "Ingest Test Data" in copilot-instructions.md
```

## Common Development Tasks

### Running Tests Locally

**Unit tests** (fast, no external dependencies):
```bash
cd {service}
pytest tests/ -v -m "not integration"
```

**Integration tests** (requires infrastructure running):
```bash
# Start MongoDB, RabbitMQ, Qdrant first
docker compose up -d documentdb messagebus vectorstore

cd adapters/copilot_storage
pytest tests/ -v -m integration
```

**All service tests**:
```bash
cd {service}
python -m pip install -r requirements.txt pytest pytest-cov
pytest tests/ -v --tb=short --cov=app --cov-report=html
```

### Accessing Services

- **API Gateway**: http://localhost:8080
- **Reporting API**: http://localhost:8080/reporting
- **Grafana**: http://localhost:8080/grafana/ (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Ollama API**: http://localhost:11434

## Azure Emulator Testing

Test Azure-specific code locally without Azure credentials using official emulators.

### Available Emulators

| Service | Emulator | Endpoint |
|---------|----------|----------|
| Cosmos DB | `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview` | https://localhost:8081 |
| Blob Storage | Azurite | http://localhost:10000 |
| Queue Storage | Azurite | http://localhost:10001 |
| Table Storage | Azurite | http://localhost:10002 |

### Quick Start

```bash
# Start Azure emulators
docker compose -f docker-compose.azure-emulators.yml up -d

# Wait for emulators to be ready (check with docker compose ps)
docker compose -f docker-compose.azure-emulators.yml ps

# Set environment variables for tests
# Note: vnext-preview emulator uses HTTP, not HTTPS
export USE_AZURE_EMULATORS=true
export COSMOS_ENDPOINT="http://localhost:8081"
export COSMOS_KEY="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
export COSMOS_DATABASE="test_copilot"
# Azurite connection string - matches docker-compose.azure-emulators.yml defaults
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;"

# Run integration tests
cd adapters/copilot_storage
pytest tests/test_integration_azurecosmos.py -v

# For Azure Blob tests (in archive_store adapter)
cd ../copilot_archive_store
pytest tests/test_integration_azure_blob.py -v

# Cleanup
docker compose -f docker-compose.azure-emulators.yml down -v
```

### Cosmos DB Emulator Notes

- The vnext-preview emulator uses HTTP (not HTTPS) on port 8081
- Well-known emulator key: `C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==`
- Data Explorer UI available at http://localhost:1234 (when emulator is running)

### CI Integration

The `azure-integration-ci.yml` workflow automatically:
1. Builds all Azure Dockerfiles (validates they compile)
2. Runs integration tests against emulators
3. Reports any SDK compatibility issues

This prevents Azure deployment regressions from reaching production.

### Debugging

**View service logs**:
```bash
docker compose logs -f {service_name}
```

**Inspect running container**:
```bash
docker compose exec {service_name} /bin/bash
```

**Check container health**:
```bash
docker compose ps
```

**Stop and clean up everything**:
```bash
docker compose down -v
```

### Log clustering / anomaly sampling

If you have a large `docker compose logs` capture (or Azure log exports) and want a compact, anomaly-focused summary, see [docs/operations/log-mining.md](docs/operations/log-mining.md).

## Detailed Setup Guides

For in-depth setup (GPU support, vendor-specific LLM backends, advanced configuration), see:
- GPU & AMD setup: [documents/LLAMA_CPP_AMD_SETUP.md](../../documents/LLAMA_CPP_AMD_SETUP.md), [documents/OLLAMA_GPU_SETUP.md](../../documents/OLLAMA_GPU_SETUP.md)
- Configuration: [docs/configuration.md](../configuration.md), [docs/operations/configuration-migration.md](../operations/configuration-migration.md)
- Deployment: [docs/gateway/overview.md](../gateway/overview.md), [infra/azure/README.md](../../infra/azure/README.md)
