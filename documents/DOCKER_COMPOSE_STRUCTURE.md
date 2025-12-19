<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Docker Compose Structure

The Docker Compose configuration is split into three files for better organization:

## Files

### docker-compose.yml (Top-level)
- **Purpose**: Main entry point that orchestrates all services
- **Contains**: 
  - `include` directives for infrastructure and services
  - Shared volumes (mongo_data, vector_data, prometheus_data, etc.)
  - Shared secrets (credentials, keys, OAuth tokens)
- **Usage**: All standard `docker compose` commands use this file automatically

### docker-compose.infra.yml (Infrastructure)
- **Purpose**: Infrastructure and monitoring services (22 services)
- **Contains**:
  - Database: documentdb, db-init, db-validate
  - Message bus: messagebus, rabbitmq-exporter
  - Vector store: vectorstore, vectorstore-validate
  - LLM: ollama, ollama-validate, ollama-model-loader, llama-cpp
  - Monitoring: monitoring (Prometheus), pushgateway, grafana, loki, promtail
  - Exporters: mongodb-exporter, mongo-doc-count-exporter, mongo-collstats-exporter, document-processing-exporter, qdrant-exporter, cadvisor

### docker-compose.services.yml (Application)
- **Purpose**: Application microservices (10 services)
- **Contains**:
  - Core services: parsing, chunking, embedding, orchestrator, summarization, reporting
  - Supporting: ingestion, auth, ui (web UI), retry-job

## Usage

### Start everything (infrastructure + services):
```bash
docker compose up -d
```

### Start only infrastructure:
```bash
docker compose -f docker-compose.infra.yml up -d
```

### Start only services (assumes infrastructure is running):
```bash
docker compose -f docker-compose.services.yml up -d
```

### Build all services:
```bash
docker compose build
```

### View combined configuration:
```bash
docker compose config
```

### Validate configuration:
```bash
docker compose config --quiet
```

## Benefits

1. **Clearer organization**: Infrastructure vs application services are separated
2. **Easier navigation**: Smaller files are easier to read and modify
3. **Selective startup**: Start infrastructure independently for development
4. **Shared resources**: Volumes and secrets defined once in the top-level file
5. **Same commands**: All standard `docker compose` commands work as before

## Notes

- The `include` directive requires Docker Compose v2.20 or later
- All secrets and volumes are shared between both files
- Service dependencies (e.g., `depends_on`) work across included files
