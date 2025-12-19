<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Integration Testing Strategy

This document describes the integration testing strategy for Copilot-for-Consensus, including test types, infrastructure requirements, and CI/CD integration.

***

## Overview

The Copilot-for-Consensus project employs a multi-layered testing strategy:

1. **Unit Tests**: Test individual functions and classes in isolation
2. **Integration Tests**: Test adapter and service interactions with real external dependencies
3. **System Integration Tests**: Test the complete pipeline end-to-end

***

## Test Organization

### Unit Tests

**Location**: `{service}/tests/test_*.py` or `{adapter}/tests/test_*.py`

**Characteristics**:
- Run in isolation without external dependencies
- Use mocks, stubs, or in-memory implementations
- Fast execution (milliseconds per test)
- No special infrastructure required

**Example**:
```python
def test_chunk_message():
    """Test chunking logic with in-memory data."""
    message = "This is a test message that needs to be chunked."
    chunks = chunk_message(message, chunk_size=10)
    assert len(chunks) == 6
```

**Running**:
```bash
cd {service}
pytest tests/ -v -m "not integration"
```

### Integration Tests

**Location**: `{adapter}/tests/test_integration_*.py`

**Characteristics**:
- Test interactions with real external services (MongoDB, RabbitMQ, Qdrant)
- Marked with `@pytest.mark.integration`
- Require infrastructure services to be running
- Slower execution (seconds per test)

**Example**:
```python
@pytest.mark.integration
def test_mongodb_storage():
    """Test storing and retrieving messages from MongoDB."""
    store = MongoDocumentStore(connection_string="mongodb://localhost:27017")
    store.insert("messages", {"message_id": "test-001", "body": "Test"})
    result = store.find_one("messages", {"message_id": "test-001"})
    assert result["body"] == "Test"
```

**Running**:
```bash
# Start infrastructure
docker compose up -d documentdb messagebus vectorstore

# Run integration tests
cd adapters/copilot_storage
pytest tests/ -v -m integration
```

### System Integration Tests

**Location**: `.github/workflows/docker-compose-ci.yml`

**Characteristics**:
- Test the complete system with all services running
- Validates end-to-end data flow
- Uses Docker Compose to orchestrate all services
- Tests against real mbox archives

**Process**:
1. Build all service images
2. Start infrastructure (MongoDB, RabbitMQ, Qdrant, Ollama, Prometheus, Loki, Grafana)
3. Initialize database and vector store
4. Start processing services (parsing, chunking, embedding, orchestrator, summarization)
5. Run ingestion with test data
6. Validate health endpoints
7. Verify data in MongoDB and Qdrant

***

## Infrastructure Requirements

### For Integration Tests

#### MongoDB

```bash
docker run -d --name test-mongodb -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=testuser \
  -e MONGO_INITDB_ROOT_PASSWORD=testpass \
  mongo:7.0
```

**Environment Variables**:
```bash
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_USERNAME=testuser
export MONGODB_PASSWORD=testpass
export MONGODB_DATABASE=test_copilot
```

#### RabbitMQ

```bash
docker run -d --name test-rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest \
  -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management
```

**Environment Variables**:
```bash
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USERNAME=guest
export RABBITMQ_PASSWORD=guest
```

#### Qdrant (Vector Store)

```bash
docker run -d --name test-qdrant -p 6333:6333 \
  qdrant/qdrant:latest
```

**Environment Variables**:
```bash
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export QDRANT_COLLECTION=test_embeddings
```

### For System Integration Tests

Use Docker Compose:

```bash
docker compose up -d
```

All infrastructure and services are orchestrated automatically.

***

## Test Execution

### Local Development

#### Run Unit Tests Only

```bash
# Service unit tests
cd parsing
pytest tests/ -v -m "not integration"

# Adapter unit tests
cd adapters/copilot_storage
pytest tests/ -v -m "not integration"
```

#### Run Integration Tests

```bash
# Start infrastructure
docker compose up -d documentdb messagebus vectorstore

# Run adapter integration tests
cd adapters/copilot_storage
pytest tests/ -v -m integration

# Run all tests (unit + integration)
pytest tests/ -v
```

#### Run System Integration Test

```bash
# From repository root
docker compose build --parallel
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail
docker compose run --rm db-init
docker compose run --rm db-validate
docker compose run --rm vectorstore-validate
docker compose run --rm ollama-validate
docker compose up -d parsing chunking embedding orchestrator summarization reporting ui
docker compose run --rm ingestion

# Validate health endpoints (via gateway)
curl -f http://localhost:8080/health       # gateway
curl -f http://localhost:8080/API/health   # reporting
curl -f http://localhost:8080/ui/          # web ui
curl -f http://localhost:8080/grafana/     # grafana
curl -f http://localhost:9090/-/healthy    # prometheus

# On Windows (PowerShell), use:
# Invoke-WebRequest -UseBasicParsing http://localhost:8080/health | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:8080/API/health | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:8080/ui/ | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:8080/grafana/ | Out-Null
# Invoke-WebRequest -UseBasicParsing http://localhost:9090/-/healthy | Out-Null

# Cleanup
docker compose down
```

### CI/CD Execution

#### GitHub Actions Workflows

**Adapter Integration Tests**: `.github/workflows/adapter-reusable-integration-ci.yml`

```yaml
- name: Start Infrastructure Services
  run: |
    docker run -d --name mongodb -p 27017:27017 \
      -e MONGO_INITDB_ROOT_USERNAME=testuser \
      -e MONGO_INITDB_ROOT_PASSWORD=testpass \
      mongo:7.0
    docker run -d --name rabbitmq -p 5672:5672 \
      rabbitmq:3-management
    sleep 10

- name: Run Integration Tests
  run: |
    pytest tests/ -v -m integration \
      --junit-xml=integration-test-results.xml \
      --cov=. --cov-report=lcov:integration-coverage.lcov
```

**System Integration Test**: `.github/workflows/docker-compose-ci.yml`

```yaml
- name: Build all images
  run: docker compose build --parallel

- name: Start infrastructure
  run: docker compose up -d documentdb messagebus vectorstore ollama monitoring

- name: Initialize database
  run: |
    docker compose run --rm db-init
    docker compose run --rm db-validate

- name: Start services
  run: docker compose up -d parsing chunking embedding orchestrator summarization

- name: Run ingestion
  run: docker compose run --rm ingestion

- name: Validate health
  run: |
    curl -f http://localhost:8080/ || exit 1
    curl -f http://localhost:8081/ || exit 1
    # On Windows runners, use: Invoke-WebRequest -UseBasicParsing http://localhost:8080/ | Out-Null
```

***

## Test Data

### Sample Archives

Test data is located in `tests/fixtures/mailbox_sample/`:

- **sample.mbox**: Small mbox file with 5-10 test messages
- **large.mbox**: Larger mbox file for performance testing
- **malformed.mbox**: Intentionally corrupted for error handling tests

### Test Message Structure

```python
# tests/fixtures/test_messages.py
TEST_MESSAGE = {
    "message_id": "<test-001@example.com>",
    "thread_id": "<test-thread-001@example.com>",
    "subject": "Test Message Subject",
    "from": {"name": "Test User", "email": "test@example.com"},
    "to": [{"name": "Recipient", "email": "recipient@example.com"}],
    "date": "2023-10-15T12:00:00Z",
    "body_normalized": "This is a test message body for integration testing.",
    "draft_mentions": ["draft-ietf-quic-transport-34"]
}
```

***

## Coverage Requirements

### Unit Tests

- **Target**: 80% code coverage minimum
- **Measured**: Per service/adapter
- **Tool**: pytest-cov
- **Report**: Uploaded to Coveralls

```bash
pytest tests/ -v --cov=app --cov-report=html --cov-report=lcov
```

### Integration Tests

- **Target**: Critical paths covered (database operations, message bus, vector store)
- **Measured**: Per adapter
- **Tool**: pytest-cov with `-m integration`

```bash
pytest tests/ -v -m integration --cov=. --cov-report=lcov
```

### System Integration

- **Target**: All services healthy and responding
- **Validated**: Health endpoints, database collections, vector store collections

***

## Test Isolation

### Database Isolation

Each integration test should use a unique database or collection:

```python
import pytest
import uuid

@pytest.fixture
def test_db():
    """Provide isolated test database."""
    db_name = f"test_copilot_{uuid.uuid4().hex[:8]}"
    store = MongoDocumentStore(database=db_name)
    yield store
    # Cleanup after test
    store.client.drop_database(db_name)
```

### Message Bus Isolation

Use unique queue names per test:

```python
@pytest.fixture
def test_queue():
    """Provide isolated test queue."""
    queue_name = f"test_queue_{uuid.uuid4().hex[:8]}"
    publisher = MessageBusPublisher(queue=queue_name)
    yield publisher
    # Cleanup after test
    publisher.delete_queue(queue_name)
```

### Vector Store Isolation

Use unique collection names:

```python
@pytest.fixture
def test_collection():
    """Provide isolated test collection."""
    collection = f"test_embeddings_{uuid.uuid4().hex[:8]}"
    client = QdrantClient(host="localhost", port=6333)
    client.create_collection(collection, vectors_config=...)
    yield collection
    # Cleanup after test
    client.delete_collection(collection)
```

***

## Common Patterns

### Setup and Teardown

```python
@pytest.fixture(scope="module")
def mongodb_connection():
    """Module-level MongoDB connection."""
    store = MongoDocumentStore(
        host="localhost",
        port=27017,
        database="test_copilot"
    )
    yield store
    # Cleanup all test collections
    for collection in store.list_collections():
        if collection.startswith("test_"):
            store.drop_collection(collection)
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
@pytest.mark.integration
async def test_async_message_publishing():
    """Test asynchronous message publishing."""
    publisher = AsyncMessageBusPublisher()
    await publisher.publish("test.event", {"data": "test"})
    await publisher.close()
```

### Parameterized Tests

```python
import pytest

@pytest.mark.parametrize("backend", ["sentencetransformers", "ollama"])
def test_embedding_backends(backend):
    """Test embedding generation with different backends."""
    config = {"backend": backend}
    embeddings = generate_embeddings(["test text"], config)
    assert len(embeddings) == 1
    assert len(embeddings[0]) > 0
```

***

## Debugging Failed Tests

### View Test Logs

```bash
# Increase verbosity
pytest tests/ -vv --tb=long

# Show print statements
pytest tests/ -s

# Stop on first failure
pytest tests/ -x
```

### Inspect Infrastructure

```bash
# Check MongoDB
docker compose exec documentdb mongosh -u root -p example copilot
db.messages.find().limit(5)

# Check RabbitMQ
curl -u guest:guest http://localhost:15672/api/queues

# Check Qdrant
curl http://localhost:6333/collections

# On Windows (PowerShell), use:
# Invoke-WebRequest -UseBasicParsing -Headers @{Authorization=("Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")))} http://localhost:15672/api/queues
# Invoke-WebRequest -UseBasicParsing http://localhost:6333/collections
```

### Debug Specific Test

```bash
# Run single test with debugging
pytest tests/test_integration_mongodb.py::test_insert_message -vv -s

# Use Python debugger
pytest tests/test_integration_mongodb.py::test_insert_message --pdb
```

***

## CI/CD Integration

### Required Checks

All pull requests must pass:

1. **Unit Tests**: All service and adapter unit tests
2. **Integration Tests**: All adapter integration tests
3. **Linting**: flake8, pylint, bandit
4. **License Headers**: SPDX header check
5. **System Integration**: Docker Compose end-to-end test

### Coverage Reporting

- **Coveralls**: Aggregates coverage from all jobs
- **Minimum**: 70% overall coverage (configurable)
- **Trend**: Coverage should not decrease with new PRs

### Test Matrix

Services and adapters are tested against:

- **Python**: 3.10, 3.11, 3.12
- **MongoDB**: 7.0
- **RabbitMQ**: 3.x
- **Qdrant**: latest

***

## Best Practices

1. **Keep tests fast**: Prefer unit tests over integration tests when possible
2. **Isolate tests**: Each test should be independent and idempotent
3. **Use fixtures**: Share setup code with pytest fixtures
4. **Mark tests clearly**: Use `@pytest.mark.integration` for integration tests
5. **Clean up resources**: Always clean up created databases, queues, collections
6. **Test edge cases**: Include tests for error conditions and edge cases
7. **Document complex tests**: Add docstrings explaining what the test validates
8. **Use realistic data**: Test with realistic message sizes and formats

***

## Future Improvements

- [ ] Performance testing framework (load testing)
- [ ] Chaos engineering tests (failure injection)
- [ ] Contract testing between services
- [ ] Visual regression testing for UI components
- [ ] Security scanning integration (OWASP, etc.)
- [ ] Mutation testing for test quality

***

## Resources

- **pytest documentation**: https://docs.pytest.org/
- **pytest-cov**: https://pytest-cov.readthedocs.io/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Docker Compose**: https://docs.docker.com/compose/

***

For questions or improvements to the testing strategy, please open an issue or discussion.
