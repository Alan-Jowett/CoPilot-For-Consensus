<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# CI Coverage Strategy

CI/CD and code coverage strategy ensuring stable, reliable metrics on the main branch.

## Strategy

### Main Branch
**All tests run** regardless of changed files, ensuring:
- Consistent, comparable coverage numbers
- No regressions masked by partial test execution
- Coverage reflects entire codebase state

### Pull Requests
**Path-based filtering** runs tests only for changed components:
- Faster CI feedback during development
- Reduced resource consumption
- Early detection in changed areas

### Coverage Aggregation
Each service/adapter uploads coverage independently:
- Flag: `parallel: true` to indicate partial upload
- Unique `flag-name` per component (e.g., `chunking`, `copilot_events`)
- Format: LCOV for compatibility

Finalization step combines all reports:
- Uses `parallel-finished: true` to signal completion
- Carryforward includes all component flags
- Single aggregated metric per branch

## Workflows

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| **unified-ci.yml** | Main orchestrator for all services/adapters | PR, push, schedule |
| **service-reusable-unit-test-ci.yml** | Shared template for service unit tests | Called by unified-ci |
| **adapter-reusable-unit-test-ci.yml** | Shared template for adapter unit tests | Called by unified-ci |
| **adapter-reusable-integration-ci.yml** | Integration tests with MongoDB/RabbitMQ | Called by unified-ci |
| **adapter-reusable-vectorstore-integration-ci.yml** | Qdrant-specific integration tests | Called by unified-ci |
| **docker-compose-ci.yml** | Full end-to-end validation | PR, push |

## Key Checks

- **Lint**: `flake8`, `pylint`, `bandit` per service
- **Unit Tests**: Full suite on all services/adapters
- **Integration Tests**: External dependency validation
- **Docker Build**: All service images build successfully
- **End-to-End**: Compose stack validation with test ingestion
- **Policy**: License headers, mutable defaults, dependabot config

See [docs/BUILDING_WITH_COPILOT.md](../BUILDING_WITH_COPILOT.md) for implementation details.
