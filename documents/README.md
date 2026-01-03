<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# documents/ (Reference Area)

This directory contains JSON schemas and historical implementation notes. **All user-facing documentation now lives in [docs/](../docs/).**

## Current Contents

### schemas/
JSON schema definitions for runtime validation:
- **configs.schema.json** - Configuration validation schema
- **documents.schema.json** - Document structure schema
- **events.schema.json** - Message bus event schemas
- **role_store.schema.json** - RBAC role definitions

See [docs/schemas/data-storage.md](../docs/schemas/data-storage.md) for schema documentation.

## Finding Documentation

**Start here:** [docs/README.md](../docs/README.md)

All operational guides, architecture docs, feature integration guides, and development references are now consolidated in the docs/ directory with a coherent structure:

- **Development & Testing**: [docs/LOCAL_DEVELOPMENT.md](../docs/LOCAL_DEVELOPMENT.md), [docs/TESTING_STRATEGY.md](../docs/TESTING_STRATEGY.md), [docs/CI_COVERAGE_STRATEGY.md](../docs/CI_COVERAGE_STRATEGY.md)
- **Operations**: [docs/operations/](../docs/operations/) (deployment, Docker Compose, exposed ports, retry policy, CI timeouts, GPU setup, runbooks)
- **Architecture**: [docs/architecture/](../docs/architecture/) (system overview, queues & events, data storage, chunking, validation)
- **Features**: [docs/features/](../docs/features/) (authentication, vectorstore, microservices auth, gateway TLS)
- **Observability**: [docs/observability/](../docs/observability/) (metrics, monitoring, dashboards)
- **Conventions**: [docs/CONVENTIONS.md](../docs/CONVENTIONS.md), [docs/BUILDING_WITH_COPILOT.md](../docs/BUILDING_WITH_COPILOT.md)

## Contributing

When adding new documentation:
1. Add content to [docs/](../docs/) with appropriate subdirectory structure
2. Update [docs/README.md](../docs/README.md) index
3. Use JSON schemas from documents/schemas/ for validation
4. Do not add new docs to documents/ (this is reference-only)
