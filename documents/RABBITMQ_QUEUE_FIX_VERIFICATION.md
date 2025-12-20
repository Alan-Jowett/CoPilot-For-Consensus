# Verifying the RabbitMQ Queue Definitions Fix

This document explains how to verify that the fix for unroutable message errors is working correctly.

## Background

The issue was caused by missing queue declarations in `infra/rabbitmq/definitions.json`. When services tried to publish events to routing keys without corresponding queues, RabbitMQ returned "unroutable message" errors because the publishers use `mandatory=True` for guaranteed delivery.

## What Was Fixed

Added 10 missing queue declarations and bindings to `infra/rabbitmq/definitions.json`:

**Reporting Service Events:**
- `report.published` - Published when a report is successfully generated
- `report.delivery.failed` - Published when report delivery fails

**Pipeline Failure Events:**
- `archive.ingestion.failed` - Ingestion failures
- `parsing.failed` - Parsing failures
- `chunking.failed` - Chunking failures
- `embedding.generation.failed` - Embedding generation failures
- `orchestration.failed` - Orchestration failures
- `summarization.failed` - Summarization failures

**Pipeline Success Events:**
- `chunks.prepared` - Chunking completed successfully
- `embeddings.generated` - Embeddings generated successfully

## Verification Steps

### 1. Verify Queue Definitions Test Passes

```bash
python3 tests/test_rabbitmq_definitions.py
```

Expected output:
```
✓ RabbitMQ definitions structure is valid
✓ Found 14 queues, 14 bindings
✓ All 14 routing keys have queue declarations and bindings
✓ Routing keys validated: [...]
✅ All RabbitMQ definitions tests passed!
```

### 2. Start the System and Check RabbitMQ Management UI

```bash
# Start all services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Open RabbitMQ Management UI
open http://localhost:15672
# Login: guest / guest (from secrets/rabbitmq_user and secrets/rabbitmq_pass)
```

In the RabbitMQ Management UI:

1. Navigate to **Queues and Streams**
2. Verify all 14 queues are present:
   - archive.ingested
   - archive.ingestion.failed
   - json.parsed
   - parsing.failed
   - chunks.prepared
   - chunking.failed
   - embeddings.generated
   - embedding.generation.failed
   - summarization.requested
   - orchestration.failed
   - summary.complete
   - summarization.failed
   - report.published
   - report.delivery.failed

3. Navigate to **Exchanges** → **copilot.events** → **Bindings**
4. Verify all 14 queues are bound with matching routing keys

### 3. Run End-to-End Test with Sample Data

```bash
# Ingest test data
./scripts/ingest_test_data.sh

# Monitor reporting service logs for errors
docker compose logs -f reporting

# Expected: No "unroutable message" errors
# Expected: "Published ReportPublished event for report <id>" messages
```

### 4. Check for Unroutable Messages in Logs

```bash
# Search all service logs for "unroutable"
docker compose logs 2>&1 | grep -i unroutable

# Expected: No results (empty output)
```

### 5. Verify Report Generation Works

```bash
# Query the reporting API
curl -s http://localhost:8080/reporting/api/reports | jq

# Expected: JSON response with reports array
# Expected: status 200, reports with summaries
```

## Troubleshooting

### If queues are missing:

1. Check that RabbitMQ loaded the definitions file:
   ```bash
   docker compose logs messagebus | grep "load_definitions"
   ```

2. Restart the messagebus service to reload definitions:
   ```bash
   docker compose restart messagebus
   ```

3. Verify the definitions.json file is mounted correctly:
   ```bash
   docker compose exec messagebus cat /etc/rabbitmq/definitions.json | jq '.queues | length'
   # Expected: 14
   ```

### If "unroutable message" errors persist:

1. Check which routing key is causing the issue in the error message
2. Verify the queue exists and is bound:
   ```bash
   # Via RabbitMQ API
   curl -u guest:guest http://localhost:15672/api/queues/%2F/<queue-name>
   curl -u guest:guest http://localhost:15672/api/exchanges/%2F/copilot.events/bindings/source
   ```

3. Check if the service is using the correct routing key:
   ```bash
   grep -r "routing_key=\"<key>\"" */app/service.py
   ```

4. Add the missing queue to `infra/rabbitmq/definitions.json` and restart

## Prevention

The validation test (`tests/test_rabbitmq_definitions.py`) prevents this issue from recurring by:

1. Scanning all service code for `routing_key=` patterns
2. Verifying each routing key has a corresponding queue declaration
3. Verifying each routing key has a binding to the `copilot.events` exchange
4. Validating the RabbitMQ definitions file structure

Run this test as part of CI/CD to catch missing queue definitions before deployment:

```bash
pytest tests/test_rabbitmq_definitions.py -v
```

## Related Documentation

- RabbitMQ Queue Configuration: `adapters/copilot_events/README.md` (lines 481-499)
- Event-Driven Architecture: `adapters/copilot_events/README.md`
- Message Bus Setup: `docker-compose.infra.yml` (messagebus service)
