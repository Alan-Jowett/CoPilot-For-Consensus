<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Local Development Guide

This guide walks through setting up a complete local development environment for Copilot-for-Consensus, including all services, infrastructure, and debugging tools.

***

## Prerequisites

### Required Software

- **Docker Desktop** (v20.10 or later)
  - Includes Docker Compose v2
  - Windows: [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
  - macOS: [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
  - Linux: [Docker Engine](https://docs.docker.com/engine/install/) + [Docker Compose](https://docs.docker.com/compose/install/)
- **Git** (v2.30 or later)
- **Python 3.10+** (for local testing and scripts)
- **8GB+ RAM** (16GB recommended for full stack)
- **20GB+ free disk space** (for images, volumes, and models)

### Optional Tools

- **MongoDB Compass** (database GUI): https://www.mongodb.com/products/compass
- **RabbitMQ Management Plugin** (included in Docker image, accessible at http://localhost:15672)
- **Postman** or **curl** (for API testing)
- **VS Code** with Docker extension (recommended IDE)

***

## Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/Alan-Jowett/CoPilot-For-Consensus.git
cd CoPilot-For-Consensus
```

### 2. Start Infrastructure Services

```bash
# Start core infrastructure (MongoDB, RabbitMQ, Qdrant, monitoring)
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail
```

Wait 30-60 seconds for services to become healthy.

### 3. Initialize Database

```bash
# Initialize MongoDB collections and indexes
docker compose run --rm db-init

# Validate schema setup
docker compose run --rm db-validate
```

### 4. Validate Infrastructure

```bash
# Validate vector store (Qdrant)
docker compose run --rm vectorstore-validate

# Validate Ollama LLM runtime
docker compose run --rm ollama-validate
```

### 5. Start Processing Services

```bash
# Start all microservices
docker compose up -d parsing chunking embedding orchestrator summarization reporting error-reporting
```

### 6. Download LLM Model (First Time Only)

```bash
# Pull Mistral model for summarization (1.5GB download)
docker compose exec ollama ollama pull mistral

# Verify model is available
docker compose exec ollama ollama list
```

### 7. Run Ingestion

```bash
# Ingest sample data
docker compose run --rm ingestion
```

### 8. Access Dashboards

- **Reporting UI**: http://localhost:8080
- **Error Tracking**: http://localhost:8081/ui
- **Grafana**: http://localhost:3000 (admin/admin)
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Prometheus**: http://localhost:9090

***

## Detailed Setup

### Environment Configuration

The system uses environment variables for configuration. The repository includes a `.env` file that you can modify for your local setup. Key variables to configure:

```bash
# Database
DOC_DB_ADMIN_USERNAME=root
DOC_DB_ADMIN_PASSWORD=example
MONGO_APP_DB=copilot

# Message Bus
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# LLM Backend
LLM_BACKEND=ollama  # or 'azure' or 'openai'
LLM_MODEL=mistral
OLLAMA_HOST=http://ollama:11434

# Embedding Backend
EMBEDDING_BACKEND=sentencetransformers  # or 'ollama' or 'azure'
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Service-by-Service Startup

For debugging individual services, start them one at a time:

#### 1. Infrastructure Layer

```bash
# MongoDB (document storage)
docker compose up -d documentdb
docker compose logs -f documentdb

# RabbitMQ (message bus)
docker compose up -d messagebus
docker compose logs -f messagebus

# Qdrant (vector store)
docker compose up -d vectorstore
docker compose logs -f vectorstore

# Ollama (local LLM)
docker compose up -d ollama
docker compose logs -f ollama
```

#### 2. Observability Stack

```bash
# Prometheus + Pushgateway (metrics)
docker compose up -d monitoring pushgateway

# Loki + Promtail (logs)
docker compose up -d loki promtail

# Grafana (visualization)
docker compose up -d grafana
```

#### 3. Processing Services

```bash
# Start services in dependency order
docker compose up -d parsing       # Parses mbox files
docker compose up -d chunking      # Splits messages into chunks
docker compose up -d embedding     # Generates embeddings
docker compose up -d orchestrator  # Coordinates workflow
docker compose up -d summarization # Creates summaries
docker compose up -d reporting     # Serves results
docker compose up -d error-reporting  # Error tracking
```

#### 4. Ingestion (On-Demand)

```bash
# Run ingestion once
docker compose run --rm ingestion

# Or start as a service for continuous ingestion
docker compose up -d ingestion
```

***

## Development Workflows

### Running Individual Services Locally (Outside Docker)

For faster iteration when developing a specific service:

#### Example: Parsing Service

```bash
cd parsing

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export MESSAGE_BUS_HOST=localhost
export MESSAGE_BUS_PORT=5672
export DOCUMENT_DATABASE_HOST=localhost
export DOCUMENT_DATABASE_PORT=27017
export LOG_LEVEL=DEBUG

# Run the service
python main.py
```

**Note:** Ensure infrastructure services (MongoDB, RabbitMQ) are running in Docker:

```bash
docker compose up -d documentdb messagebus vectorstore
```

### Testing

#### Unit Tests

```bash
# Run tests for a specific service
cd parsing
pip install -r requirements.txt pytest pytest-cov
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

#### Integration Tests

```bash
# Ensure infrastructure is running
docker compose up -d documentdb messagebus vectorstore

# Run integration tests (marked with @pytest.mark.integration)
cd adapters/copilot_storage
pytest tests/ -v -m integration

# Run all tests including integration
pytest tests/ -v
```

#### System Integration Tests

To run a full end-to-end system integration test with Docker Compose, follow the steps below. This will build all images, start infrastructure and services, run ingestion, and validate health endpoints.

```bash
# From repository root
docker compose build --parallel
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail
docker compose run --rm db-init
docker compose run --rm db-validate
docker compose run --rm vectorstore-validate
docker compose run --rm ollama-validate
docker compose up -d parsing chunking embedding orchestrator summarization reporting error-reporting
docker compose run --rm ingestion

# Validate health endpoints
curl -f http://localhost:8080/      # reporting
curl -f http://localhost:8081/      # error-reporting
curl -f http://localhost:3000/api/health  # grafana
curl -f http://localhost:9090/-/healthy   # prometheus

# On Windows (PowerShell), use:
# Invoke-WebRequest -UseBasicParsing http://localhost:8080/ | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:8081/ | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:3000/api/health | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:9090/-/healthy | Out-Null

# Cleanup
docker compose down
```

### Viewing Logs

#### Real-Time Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f parsing

# Multiple services
docker compose logs -f parsing chunking embedding

# Tail last 100 lines
docker compose logs -f --tail=100 parsing
```

#### Centralized Logs (Loki + Grafana)

1. Open Grafana: http://localhost:3000
2. Navigate to **Explore**
3. Select **Loki** datasource
4. Query examples:
   - All parsing logs: `{service="parsing"}`
   - Error logs: `{level="error"}`
   - Specific service errors: `{service="embedding", level="error"}`

### Monitoring

#### Metrics (Prometheus + Grafana)

1. Open Grafana: http://localhost:3000
2. Pre-configured dashboards:
   - **System Overview**: Service health, uptime, throughput
   - **Ingestion Pipeline**: Messages parsed, chunks created, embeddings generated
   - **Failed Queues**: Queue depths, retry counts, alert thresholds

#### Failed Queues

```bash
# Inspect failed queues
python scripts/manage_failed_queues.py list

# View failed messages
python scripts/manage_failed_queues.py inspect parsing_failed

# Requeue failed messages (retry)
python scripts/manage_failed_queues.py requeue parsing_failed

# Purge permanently failed messages
python scripts/manage_failed_queues.py purge parsing_failed --confirm
```

### Debugging

#### MongoDB Access

```bash
# Connect to MongoDB shell
docker compose exec documentdb mongosh \
  -u root \
  -p example \
  --authenticationDatabase admin \
  copilot

# Query messages
db.messages.find().limit(5).pretty()

# Check collection stats
db.messages.stats()
db.chunks.stats()
```

#### RabbitMQ Management

Access the RabbitMQ web UI at http://localhost:15672 (guest/guest):

- **Queues**: View message counts, rates, consumers
- **Exchanges**: See event routing topology
- **Connections**: Active service connections

#### Vector Store (Qdrant)

```bash
# Query vector store API
curl http://localhost:6333/collections

# Check collection info
curl http://localhost:6333/collections/message_embeddings
```

#### Ollama Model Management

```bash
# List available models
docker compose exec ollama ollama list

# Pull additional models
docker compose exec ollama ollama pull llama2
docker compose exec ollama ollama pull nomic-embed-text

# Remove models
docker compose exec ollama ollama rm mistral

# Show model info
docker compose exec ollama ollama show mistral
```

***

## Common Issues & Solutions

### Services Won't Start

**Symptom:** `docker compose up` fails or services exit immediately.

**Solutions:**

1. Check Docker resources (8GB+ RAM):
   ```bash
   docker system info | grep -i memory
   ```
   
   **Windows (PowerShell):**
   ```powershell
   docker system info | Select-String -Pattern "memory" -CaseSensitive:$false
   ```

2. Clean up old containers/volumes:
   ```bash
   docker compose down -v
   docker system prune -a
   ```

3. Rebuild images:
   ```bash
   docker compose build --no-cache
   ```

### Database Connection Errors

**Symptom:** Services log `ConnectionError: Cannot connect to MongoDB`.

**Solutions:**

1. Verify MongoDB is healthy:
   ```bash
   docker compose ps documentdb
   docker compose logs documentdb
   ```

2. Wait for health check:
   ```bash
   docker compose up -d documentdb
   sleep 30
   docker compose run --rm db-validate
   ```

3. Check credentials in `.env` file

### Message Bus Errors

**Symptom:** Services log `pika.exceptions.AMQPConnectionError`.

**Solutions:**

1. Verify RabbitMQ is running:
   ```bash
   docker compose ps messagebus
   curl http://localhost:15672
   ```

2. Check queue state:
   ```bash
   python scripts/manage_failed_queues.py list
   ```

3. Restart message bus:
   ```bash
   docker compose restart messagebus
   ```

### Ollama Model Not Found

**Symptom:** `Model 'mistral' not found in Ollama`.

**Solutions:**

1. Pull the model:
   ```bash
   docker compose exec ollama ollama pull mistral
   ```

2. Verify model is loaded:
   ```bash
   docker compose exec ollama ollama list
   ```

3. Use alternative model:
   ```bash
   export LLM_MODEL=llama2
   docker compose exec ollama ollama pull llama2
   ```

### Disk Space Issues

**Symptom:** `no space left on device` or slow performance.

**Solutions:**

1. Check disk usage:
   ```bash
   docker system df
   ```

2. Clean up unused resources:
   ```bash
   docker system prune -a --volumes
   ```

3. Remove old models:
   ```bash
   docker compose exec ollama ollama rm old-model
   ```

***

## Development Best Practices

### Code Changes

1. **Make incremental changes**: Test each change before moving to the next
2. **Run linters**: Use `flake8`, `pylint`, `bandit` before committing
3. **Add tests**: Include unit and integration tests for new features
4. **Update docs**: Modify README and relevant documentation in the same PR

### Iterative Testing

```bash
# Watch mode for tests (using pytest-watch)
pip install pytest-watch
cd parsing
ptw tests/ -- -v

# Rebuild and restart a single service
docker compose build parsing
docker compose up -d --force-recreate parsing
docker compose logs -f parsing
```

### Pre-Commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### License Headers

All source files must include SPDX license headers:

```bash
# Check license headers
python scripts/check_license_headers.py --root .

# Auto-fix missing headers (if available)
pre-commit run --all-files
```

***

## Clean Shutdown

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clears all data)
docker compose down -v

# Stop and remove images
docker compose down --rmi all
```

***

## Next Steps

- **Add custom ingestion sources**: Edit `ingestion/config.json`
- **Integrate cloud LLMs**: Configure Azure OpenAI or OpenAI API
- **Deploy to production**: See deployment guides (coming soon)
- **Extend with plugins**: Add custom adapters or services

***

## Getting Help

- **Documentation**: See [documents/](../documents/) for detailed technical docs
- **Issues**: Report bugs at https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues
- **Discussions**: Ask questions at https://github.com/Alan-Jowett/CoPilot-For-Consensus/discussions
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines
