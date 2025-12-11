<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Adapters

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
- **copilot_storage**: Document store abstraction (MongoDB, in-memory)

### Events & Messaging
- **copilot_events**: Event publishing, subscription, and schema validation

### Observability
- **copilot_logging**: Structured logging abstraction
- **copilot_metrics**: Metrics collection (Prometheus, no-op)
- **copilot_reporting**: Error reporting (Console, Sentry)

### Infrastructure
- **copilot_auth**: Authentication and authorization
- **copilot_config**: Configuration management

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
- **copilot_reporting**: `SilentErrorReporter`

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
