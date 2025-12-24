<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Tests Directory

This directory contains end-to-end integration tests for the Copilot-for-Consensus system.

## Test Files

### test_integration_message_flow.py
Event schema validation tests. These tests validate that all event types have proper JSON schemas and that events can be correctly validated against them. They demonstrate the schema validation infrastructure without requiring actual service instances.

**Markers:** `integration`

### validate_e2e_flow.py
End-to-end validation script that verifies the complete message flow pipeline from ingestion to embedding generation. This is **not** a pytest test - it's a standalone validation script designed to run in CI after Docker Compose services are up.

**Usage:**
```bash
python tests/validate_e2e_flow.py
```

**Environment Variables:**
- `MONGODB_HOST` - MongoDB host (default: localhost)
- `MONGODB_PORT` - MongoDB port (default: 27017)
- `MONGODB_USERNAME` - MongoDB username (default: root)
- `MONGODB_PASSWORD` - MongoDB password (default: example)
- `MONGODB_DATABASE` - MongoDB database name (default: copilot)
- `QDRANT_HOST` - Qdrant host (default: localhost)
- `QDRANT_PORT` - Qdrant port (default: 6333)
- `QDRANT_COLLECTION` - Qdrant collection name (default: embeddings)

**What it validates:**
1. Archives are ingested and stored
2. Messages are parsed and persisted
3. Threads are correctly inferred
4. Chunks are created from messages
5. Embeddings are generated and stored in Qdrant
6. Data consistency across collections

**Timing considerations:**
- The script waits up to 90 seconds for message processing to complete
- In CI, a 20-second delay is added after ingestion before validation starts
- Message processing through the pipeline (parsing → chunking → embedding) can take 30-60 seconds for 10 messages
- Embeddings are treated as warnings rather than failures since they depend on Ollama availability

**Exit codes:**
- `0` - All validations passed (or only warnings)
- `1` - One or more critical validations failed

## Fixtures

### fixtures/mailbox_sample/
Test mailbox fixture for end-to-end validation. Contains:
- `test-archive.mbox` - Sample mbox file with 10 representative messages
- `ingestion-config.json` - Ingestion configuration pointing to the test mailbox
- `README.md` - Documentation for the fixture

See the [fixture README](fixtures/mailbox_sample/README.md) for details on how to use the test mailbox.

## Running Tests

### Run schema validation tests
```bash
pytest tests/test_integration_message_flow.py -v -m integration
```

### Run end-to-end validation (requires Docker Compose stack)

> **Note:** These commands use `docker compose` (with a space), which requires Docker Compose V2.
> If you are using an older Docker installation, replace `docker compose` with `docker-compose` (with a hyphen) in all commands below.

```bash
# 1. Start all services (includes the continuously running ingestion API)
docker compose up -d

# 2. Copy the sample mailbox into the running ingestion container
INGESTION_CONTAINER=$(docker compose ps -q ingestion)
docker exec "$INGESTION_CONTAINER" mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$INGESTION_CONTAINER":/tmp/test-mailbox/test-archive.mbox

# 3. Create the source via REST API
curl -f -X POST http://localhost:8080/ingestion/api/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'

# 4. Trigger ingestion via REST API
curl -f -X POST http://localhost:8080/ingestion/api/sources/test-mailbox/trigger

# 5. Validate results
docker compose run --rm \
  -v $PWD/tests:/app/tests:ro \
  -e MONGODB_HOST=documentdb \
  -e MONGODB_PORT=27017 \
  -e MONGODB_USERNAME=root \
  -e MONGODB_PASSWORD=example \
  -e MONGODB_DATABASE=copilot \
  -e QDRANT_HOST=vectorstore \
  -e QDRANT_PORT=6333 \
  -e QDRANT_COLLECTION=embeddings \
  --entrypoint "" \
  ingestion \
  bash -c "pip install -q pymongo qdrant-client && python /app/tests/validate_e2e_flow.py"
```

## CI Integration

The end-to-end validation is automatically run in the Docker Compose CI workflow (`.github/workflows/docker-compose-ci.yml`) after the ingestion service completes. This ensures that the complete pipeline works correctly on every PR and merge to main.
