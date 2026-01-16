<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Documentation Hub

This is the primary index for project documentation. Use this page first; legacy or in-progress materials under documents/ are referenced until they are migrated here.

## Quick Navigation
- Architecture: [docs/architecture/overview.md](architecture/overview.md), [docs/architecture/queues-and-events.md](architecture/queues-and-events.md), [docs/architecture/implementation-summary.md](architecture/implementation-summary.md), [docs/architecture/data-storage.md](architecture/data-storage.md), [docs/architecture/chunking.md](architecture/chunking.md), [docs/architecture/validation.md](architecture/validation.md)
- Development & CI: [docs/LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md), [docs/TESTING_STRATEGY.md](TESTING_STRATEGY.md), [docs/CI_COVERAGE_STRATEGY.md](CI_COVERAGE_STRATEGY.md), [docs/BUILDING_WITH_COPILOT.md](BUILDING_WITH_COPILOT.md)
- Project Conventions: [docs/CONVENTIONS.md](CONVENTIONS.md)
- Schema-Driven Config: [docs/SCHEMA_DRIVEN_CONFIGURATION.md](SCHEMA_DRIVEN_CONFIGURATION.md)
- Operations & Deployment: [docs/configuration.md](configuration.md), [docs/operations/docker-compose-structure.md](operations/docker-compose-structure.md), [docs/operations/exposed-ports.md](operations/exposed-ports.md), [docs/operations/deployment.md](operations/deployment.md), [docs/operations/configuration-migration.md](operations/configuration-migration.md), [docs/operations/security-migration-summary.md](operations/security-migration-summary.md), [docs/operations/retry-policy.md](operations/retry-policy.md), [docs/operations/forward-progress.md](operations/forward-progress.md), [docs/operations/ci-test-timeouts.md](operations/ci-test-timeouts.md), GPU/LLM setup ([docs/operations/llm-gpu-setup.md](operations/llm-gpu-setup.md), [docs/operations/ollama-gpu-setup.md](operations/ollama-gpu-setup.md)), runbooks ([docs/operations/runbooks](operations/runbooks)), gateway deployment guides ([docs/gateway/overview.md](gateway/overview.md))
- Project Conventions & Guidelines: [docs/CONVENTIONS.md](CONVENTIONS.md), [docs/BUILDING_WITH_COPILOT.md](BUILDING_WITH_COPILOT.md)
- Features: Authentication & token refresh ([docs/features/authentication.md](features/authentication.md)); Vectorstore ([docs/features/vectorstore.md](features/vectorstore.md)); Microservices Auth ([docs/features/microservices-auth.md](features/microservices-auth.md)); Gateway TLS ([docs/features/gateway-tls.md](features/gateway-tls.md)); Metrics ([documents/METRICS_INTEGRATION_GUIDE.md](../documents/METRICS_INTEGRATION_GUIDE.md))
- Observability: [docs/observability/implementation-summary.md](observability/implementation-summary.md), [docs/observability/service-monitoring.md](observability/service-monitoring.md), [docs/observability/metrics-integration.md](observability/metrics-integration.md), [docs/observability/retry-policy-dashboard.md](observability/retry-policy-dashboard.md), [docs/GRAFANA_JWT_IMPLEMENTATION.md](GRAFANA_JWT_IMPLEMENTATION.md), [docs/GRAFANA_JWT_TESTING.md](GRAFANA_JWT_TESTING.md)
- APIs: [docs/openapi.md](openapi.md), gateway notes ([docs/gateway](gateway))
- Schemas: [docs/schemas/README.md](schemas/README.md), [docs/schemas/data-storage.md](schemas/data-storage.md), and [docs/schemas/schema-versioning.md](schemas/schema-versioning.md) → JSON schemas under [docs/schemas/](schemas/) (configs, documents, events, role_store)
- Migrations & Policies: [docs/operations/configuration-migration.md](operations/configuration-migration.md), [docs/operations/security-migration-summary.md](operations/security-migration-summary.md), [docs/operations/retry-policy.md](operations/retry-policy.md), [docs/operations/forward-progress.md](operations/forward-progress.md)

## Directory Purposes
- docs/: Canonical, user-facing and contributor-facing docs. New or consolidated content should land here. The archive/ subdirectory contains historical implementation notes preserved for audit purposes.
- documents/: Historical implementation notes only (schemas moved to docs/schemas/).

## Naming & Link Conventions
- Prefer kebab-case for new filenames.
- Keep internal links relative and update them when files move.
- Avoid duplicate topics; pick a single canonical page and redirect/update references.

## Planned Consolidations (phase 1)
- Architecture: ✅ moved into docs/architecture/ (overview + queues/events); update any remaining links.
- Authentication: ✅ merged into [docs/features/authentication.md](features/authentication.md); legacy files now point here.
- Configuration & Ops: ✅ includes [docs/operations/docker-compose-structure.md](operations/docker-compose-structure.md), [docs/operations/exposed-ports.md](operations/exposed-ports.md), and [docs/operations/configuration-migration.md](operations/configuration-migration.md).
- Observability: ✅ consolidated at [docs/observability/service-monitoring.md](observability/service-monitoring.md) and [docs/observability/metrics-integration.md](observability/metrics-integration.md).
- Runbooks: ✅ relocated to [docs/operations/runbooks](operations/runbooks); legacy stubs remain under documents/runbooks during link updates.
- Schemas: ✅ [docs/schemas/README.md](schemas/README.md) and [docs/schemas/schema-versioning.md](schemas/schema-versioning.md) point to [docs/schemas](schemas) JSON until versioned docs are written.

## How to Contribute to the Reorg
- When touching a topic with duplicates, consolidate into docs/ and replace the older file with a short pointer or remove it after updating links.
- Keep the index above current; add new pages here when created.
- If you move a file, update references in README.md, CONTRIBUTING.md, and any doc cross-links.
