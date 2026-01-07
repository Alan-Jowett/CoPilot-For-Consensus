<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schemas Index

JSON schemas live under `docs/schemas/` and are the source of truth for configuration, data contracts, and events. This page is a lightweight index until versioned docs are written.

## Layout
- [configs](configs/): Service configuration schemas consumed by `copilot_config` (used in [configuration migration](../operations/configuration-migration.md)).
- [documents](documents/): Document payload and metadata schemas used by storage and reporting pipelines.
- [events](events/): Message bus event schemas (publish/subscribe contracts).
- [role_store](role_store/): Role and permission schemas for RBAC.
- Narrative summary: [data storage schema](data-storage.md) for the MongoDB/Cosmos + vector store model.

## Usage notes
- Bump `metadata.version` when changing a schema and describe the change in `metadata.description`.
- Keep field descriptions accurate; they double as developer documentation.
- Prefer additive changes; coordinate breaking changes with service owners and update tests.
- Validate locally with your JSON tooling before committing (e.g., `python -m json.tool <schema>` or your editor's schema validator).

## Related docs
- Migration guidance: [Schema-driven configuration](../operations/configuration-migration.md)
- Versioning strategy: [Schema versioning guide](schema-versioning.md)
