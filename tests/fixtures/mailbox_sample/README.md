<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Test Mailbox Fixture

This directory contains a test mailbox used for end-to-end validation of the message flow pipeline.

## Files

- **test-archive.mbox**: A sample mbox file containing 10 representative messages
  - 3 conversation threads
  - Messages with In-Reply-To and References headers
  - RFC and draft mentions (e.g., draft-ietf-quic-transport-34, RFC 9000)
  - Realistic email structure and content

- **ingestion-config.json**: Configuration file for the ingestion service
  - Defines a "test-mailbox" source pointing to test-archive.mbox
  - Uses "local" source type to read the file directly

## Usage in CI

The Docker Compose CI workflow uses these fixtures to validate the end-to-end message flow:

1. **Upload Configuration**: The ingestion config is uploaded to the document store
2. **Run Ingestion**: The ingestion service processes test-archive.mbox
3. **Validate Flow**: The validate_e2e_flow.py script validates:
   - Archives are ingested and stored
   - Messages are parsed and persisted
   - Threads are correctly inferred
   - Chunks are created from messages
   - Embeddings are generated and stored in Qdrant

## Expected Results

From the 10 messages in test-archive.mbox:

- **Archives**: 1 archive record
- **Messages**: 10 message records
- **Threads**: ~3 thread records (based on conversation structure)
- **Chunks**: ~10+ chunk records (depending on chunking strategy)
- **Embeddings**: ~10+ vectors in Qdrant (one per chunk)

## Running Locally

> **Note:** These commands use `docker compose` (with a space), which requires Docker Compose V2.  
> If you are using an older Docker installation, replace `docker compose` with `docker-compose` (with a hyphen) in all commands below.

To test the end-to-end flow locally:

```bash
# Start infrastructure and services (includes the ingestion API)
docker compose up -d

# Copy the sample mailbox into the running ingestion container
INGESTION_CONTAINER=$(docker compose ps -q ingestion)
docker exec "$INGESTION_CONTAINER" mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$INGESTION_CONTAINER":/tmp/test-mailbox/test-archive.mbox

# Create the source via REST API
curl -f -X POST http://localhost:8001/api/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'

# Trigger ingestion via REST API
curl -f -X POST http://localhost:8001/api/sources/test-mailbox/trigger

# Validate results
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
