<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Data Validation Architecture

Application-layer validation ensuring centralized, consistent, evolving logic without database-level constraints.

## Validation Layers

### 1. Event Validation

Message bus events validated using `ValidatingEventPublisher` and `ValidatingEventSubscriber`:

```python
from copilot_events import create_publisher, ValidatingEventPublisher
from copilot_schema_validation import FileSchemaProvider

# Wrap publisher with validation
schema_provider = FileSchemaProvider()  # Loads schemas from docs/schemas/events
publisher = ValidatingEventPublisher(
    publisher=base_publisher,
    schema_provider=schema_provider,
    strict=True,  # Raise ValidationError on invalid events
)

publisher.publish(event)  # Validated against JSON schema
```

**Adapter**: `copilot_events/`

### 2. Document Validation

MongoDB documents validated using `ValidatingDocumentStore`:

```python
from copilot_storage import create_document_store, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider

schema_provider = FileSchemaProvider()  # Loads documents/ schemas
store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=schema_provider,
    strict=True,
)

store.insert("messages", document)  # Validated before insert
```

**Adapter**: `copilot_storage/`

### 3. Configuration Validation

Service configuration validated against schema on startup:

```python
from copilot_config import load_typed_config, ConfigValidationError

try:
    config = load_typed_config("service-name")
except ConfigValidationError as e:
    logger.error(f"Config error: {e}")
    raise Exception("Service startup failed")
```

**Adapter**: `copilot_config/`

## Schema Locations

| Type | Location | File Pattern |
|------|----------|--------------|
| **Events** | `docs/schemas/events/` | `{EventName}.schema.json` |
| **Documents** | `docs/schemas/documents/` | `{CollectionName}.schema.json` |
| **Configs** | `docs/schemas/configs/` | `{ServiceName}.schema.json` |
| **Roles/Permissions** | `docs/schemas/role_store/` | `{Entity}.schema.json` |

## Validation Strategy

- **No database constraints**: Validation stays in application layer for flexibility
- **Fail-fast startup**: Invalid config detected at service initialization
- **Strict event validation**: Message bus enforces schema contracts
- **Document validation on insert**: Prevents invalid data in storage
- **Explicit nullability**: Optional fields marked in schema; consumers must handle absence
- **Version tracking**: Schema versioning in `metadata.version`

## Best Practices

1. **Schema-first approach**: Define schema before service code
2. **Version on breaking changes**: Update `metadata.version` and coordinate with deployments
3. **Additive changes only**: Prefer adding optional fields to avoid migration burden
4. **Test validation**: Unit tests should verify both valid and invalid payloads
5. **Error messages**: ValidationError includes path and issue description for debugging

See [copilot_schema_validation/README.md](../../adapters/copilot_schema_validation/README.md) and [docs/schemas/README.md](../schemas/README.md).
