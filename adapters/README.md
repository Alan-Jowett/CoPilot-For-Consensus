<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Adapters

## CI Status

[![Auth Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-auth-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-auth-adapter.yml)
[![Config Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-config-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-config-adapter.yml)
[![Events Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-events-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-events-adapter.yml)
[![Logging Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-logging-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-logging-adapter.yml)
[![Metrics Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-metrics-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-metrics-adapter.yml)
[![Reporting Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-reporting-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-reporting-adapter.yml)
[![Storage Adapter CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-storage-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-storage-adapter.yml)

This directory contains the **adapter layer** that sits at the architectural boundary between our core business logic and external systems. These modules abstract away specific technology choices and provide stable interfaces for the rest of the application.

## Purpose

The adapters in this directory serve as the **integration boundary layer** following clean architecture and hexagonal design principles. They:

- **Decouple** core business logic from external dependencies
- **Enable modularity** by providing consistent interfaces
- **Improve testability** through dependency injection and mock implementations
- **Future-proof** the system by isolating technology choices
- **Simplify onboarding** by clearly separating concerns

## Available Adapters

### Storage & Persistence
- **copilot_storage**: Document store abstraction (MongoDB, in-memory) · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-storage-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-storage-adapter.yml)

### Events & Messaging
- **copilot_message_bus**: Event publishing, subscription, and schema validation · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-events-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-events-adapter.yml)

### Observability
- **copilot_logging**: Structured logging abstraction · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-logging-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-logging-adapter.yml)
- **copilot_metrics**: Metrics collection (Prometheus, no-op) · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-metrics-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-metrics-adapter.yml)
 - **copilot_error_reporting**: Error reporting (Console, Sentry) · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-reporting-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-reporting-adapter.yml)

### Infrastructure
- **copilot_auth**: Authentication and authorization · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-auth-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-auth-adapter.yml)
- **copilot_config**: Configuration management · [![CI](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-config-adapter.yml/badge.svg)](https://github.com/Alan-Jowett/CoPilot-For-Consensus/actions/workflows/test-config-adapter.yml)

## Design Principles

Each adapter module should:

1. **Define clear interfaces**: Use abstract base classes or protocols
2. **Provide multiple implementations**: Support production, testing, and development scenarios
3. **Enable configuration**: Allow environment-based or explicit configuration
4. **Include comprehensive tests**: Cover both interface contracts and implementations
5. **Document usage**: Provide clear examples and API documentation

## Usage Pattern

Adapters are typically instantiated using factory functions:

```python
# Storage adapter
from copilot_storage import create_document_store
store = create_document_store(store_type="mongodb", connection_string="...")

# Logging adapter
from copilot_logging import create_logger
logger = create_logger()  # Configures from environment

# Metrics adapter
from copilot_metrics import create_metrics_collector
metrics = create_metrics_collector()  # Configures from METRICS_BACKEND env var
```

## Testing

Each adapter provides test-friendly implementations:

- **copilot_storage**: `InMemoryDocumentStore`
- **copilot_logging**: `SilentLogger`
- **copilot_metrics**: `NoOpMetricsCollector`
 - **copilot_error_reporting**: `SilentErrorReporter`

### Integration Tests

Adapters that interact with external services have dedicated integration tests:

- **copilot_storage**: MongoDB integration tests (`test_integration_mongodb.py`)
- **copilot_message_bus**: RabbitMQ integration tests (`test_integration_rabbitmq.py`)
- **copilot_archive_fetcher**: rsync and HTTP integration tests
- **copilot_schema_validation**: MongoDB-backed schema provider integration tests

Integration tests are marked with `@pytest.mark.integration` and can be run with:

```bash
# Run all integration tests
pytest -m integration

# Run integration tests for a specific adapter
cd adapters/copilot_message_bus
pytest -m integration

# Skip integration tests
pytest -m "not integration"
```

Integration tests require external services (MongoDB, RabbitMQ, etc.) to be running.
The CI pipeline automatically provisions these services using GitHub Actions service containers.

## Contributing

When adding new adapters or modifying existing ones:

1. Follow the existing interface patterns
2. Provide at least two implementations (production + test)
3. Include comprehensive unit and integration tests
4. Document configuration options and usage examples
5. Update this README with your new adapter

## Architecture Context

These adapters implement the **Ports and Adapters** (Hexagonal Architecture) pattern:

- **Ports**: The interfaces defined by each adapter (e.g., `DocumentStore`, `Logger`)
- **Adapters**: The concrete implementations (e.g., `MongoDocumentStore`, `StdoutLogger`)

This allows our microservices to depend on stable abstractions rather than volatile implementations, making the system more maintainable and testable.
