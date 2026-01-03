<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Testing Strategy

Multi-layered testing approach covering unit, integration, and end-to-end validation.

## Test Organization

### Unit Tests
- **Location**: `{service}/tests/test_*.py`, `{adapter}/tests/test_*.py`
- **Scope**: Individual functions and classes in isolation
- **Dependencies**: Mocks, stubs, in-memory implementations
- **Speed**: Milliseconds per test
- **Run**: `pytest tests/ -v -m "not integration"`

### Integration Tests
- **Location**: `{adapter}/tests/test_integration_*.py`
- **Scope**: Real external services (MongoDB, RabbitMQ, Qdrant)
- **Mark**: `@pytest.mark.integration`
- **Speed**: Seconds per test
- **Requires**: Infrastructure running (`docker compose up -d documentdb messagebus vectorstore`)
- **Run**: `pytest tests/ -v -m integration`

### End-to-End Tests
- **Scope**: Complete pipeline from ingestion to reporting
- **Driver**: [.github/workflows/docker-compose-ci.yml](.github/workflows/docker-compose-ci.yml)
- **Includes**: Service startup, test ingestion, endpoint validation, health checks
- **Speed**: 10–15 minutes
- **Triggered**: Every PR and push to main

## Coverage Strategy

- **Main branch**: All tests run on every push (comprehensive coverage)
- **Pull requests**: Path-based filtering runs only tests for changed components (fast feedback)
- **Aggregation**: Parallel Coveralls uploads with `parallel: true` during PR/push; finalization with `parallel-finished: true` on main
- **Carryforward**: Coverage flags include all component results for full picture

## Running Tests Locally

**Single service**:
```bash
cd {service}
pip install -r requirements.txt pytest pytest-cov
pytest tests/ -v --tb=short --cov=app --cov-report=html --cov-report=term
```

**Single adapter** (unit only):
```bash
cd adapters/{adapter}
pip install -r requirements.txt pytest pytest-cov
pytest tests/ -v -m "not integration" --cov={adapter} --cov-report=html
```

**Adapter with integration tests**:
```bash
cd adapters/{adapter}
# Ensure infrastructure running: docker compose up -d documentdb messagebus vectorstore [qdrant if vectorstore adapter]
pytest tests/ -v -m integration --cov={adapter} --cov-report=html
```

**Full system (Docker Compose)**:
```bash
# Covered by .github/workflows/docker-compose-ci.yml
# Locally: startup the project, ingest test data, verify endpoints
# See copilot-instructions.md for "run the docker compose workflow" commands
```

## CI/CD Workflow

- **unified-ci.yml**: Main CI orchestrator for all services and adapters
- **service-reusable-unit-test-ci.yml**: Shared template for service unit tests
- **adapter-reusable-unit-test-ci.yml**: Shared template for adapter unit tests
- **adapter-reusable-integration-ci.yml**: Shared template for adapter integration tests
- **adapter-reusable-vectorstore-integration-ci.yml**: Qdrant-specific integration tests
- **docker-compose-ci.yml**: End-to-end validation

See [docs/BUILDING_WITH_COPILOT.md](../BUILDING_WITH_COPILOT.md) for implementation details.
