# Configuration Management

This document describes the configuration management system for Copilot-for-Consensus microservices, including schema versioning, discovery, and evolution.

## Table of Contents

- [Overview](#overview)
- [Schema Versioning](#schema-versioning)
- [Configuration Discovery](#configuration-discovery)
- [Schema Compatibility](#schema-compatibility)
- [Configuration Evolution](#configuration-evolution)
- [Best Practices](#best-practices)

## Overview

Copilot-for-Consensus uses a schema-driven configuration system built on the `copilot_config` adapter. All microservices define their configuration requirements in JSON schema files located in `documents/schemas/configs/`.

### Key Features

- **Type-safe configuration**: Configuration values are validated at startup
- **Schema versioning**: Schemas include version information for evolution tracking
- **Configuration discovery**: Services expose their configuration schema via REST endpoint
- **Compatibility checking**: CI validates that schema changes don't break deployments
- **Multi-source support**: Configuration can come from environment variables, secrets, or document stores

## Schema Versioning

### Version Fields

Each configuration schema includes version metadata:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "service_name": "parsing",
  "schema_version": "1.0.0",
  "min_service_version": "0.1.0",
  "metadata": {
    "description": "Parsing service configuration schema",
    "version": "1.0.0"
  },
  "fields": { ... }
}
```

### Version Fields Explained

- **`$schema`**: JSON Schema version used (Draft 2020-12)
- **`schema_version`**: Version of this configuration schema (semver format)
- **`min_service_version`**: Minimum service version required to use this schema
- **`metadata.version`**: Legacy version field (deprecated, use `schema_version`)

### Semantic Versioning

Schema versions follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes
  - Field removal
  - Type changes
  - Making optional fields required
  - Default value changes for required fields

- **MINOR** (1.0.0 → 1.1.0): Backward-compatible additions
  - Adding optional fields
  - Adding new enum values
  - Expanding validation rules

- **PATCH** (1.0.0 → 1.0.1): Non-functional updates
  - Documentation changes
  - Metadata updates
  - Fixing typos

### Runtime Validation

Services automatically validate schema compatibility at startup:

```python
from copilot_config import load_typed_config

# Load configuration with version validation
config = load_typed_config("parsing")

# Access configuration
print(config.message_bus_host)

# Check schema version
print(f"Schema version: {config.get_schema_version()}")
print(f"Min service version: {config.get_min_service_version()}")
```

If the service version is incompatible with the schema, the service fails fast at startup with a clear error message.

## Configuration Discovery

### Discovery Endpoint

Each microservice exposes a `/.well-known/configuration-schema` endpoint that returns:

- Service name and version
- Schema version
- Minimum service version required
- Full configuration schema

### Example Response

```json
{
  "service_name": "parsing",
  "service_version": "0.1.0",
  "schema_version": "1.0.0",
  "min_service_version": "0.1.0",
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "service_name": "parsing",
    "schema_version": "1.0.0",
    "fields": {
      "message_bus_host": {
        "type": "string",
        "source": "env",
        "env_var": "MESSAGE_BUS_HOST",
        "default": "messagebus",
        "description": "Message bus hostname"
      },
      ...
    }
  }
}
```

### Implementation

To add the discovery endpoint to a FastAPI service:

```python
from copilot_config import get_configuration_schema_response
from app import __version__

@app.get("/.well-known/configuration-schema")
def configuration_schema():
    """Configuration schema discovery endpoint."""
    try:
        response = get_configuration_schema_response(
            service_name="your-service",
            service_version=__version__,
        )
        return response
    except FileNotFoundError:
        # Log the full error server-side
        logger.error("Schema file not found for service")
        raise HTTPException(status_code=404, detail="Schema not found")
    except Exception as e:
        # Log the full error and stack trace server-side
        logger.error(f"Failed to load configuration schema: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load schema")
```

### Use Cases

- **Operational introspection**: Ops teams can query configuration structure remotely
- **Automated tooling**: CI/CD pipelines can validate configurations before deployment
- **Documentation generation**: Auto-generate configuration documentation from schemas
- **Service mesh integration**: Service meshes can auto-discover configuration requirements

## Schema Compatibility

### Compatibility Rules

The `copilot_config.check_compat` module enforces compatibility rules:

**Breaking Changes** (require MAJOR version bump):
- Removing required fields
- Changing field types
- Making optional fields required
- Changing default values for required fields

**Warnings** (suggest MINOR version bump):
- Removing optional fields
- Changing default values for optional fields
- Marking fields as deprecated

### CLI Tool

Check schema compatibility before merging:

```bash
# Compare old and new schema versions
python -m copilot_config check_compat \
  --old documents/schemas/configs/parsing.json.old \
  --new documents/schemas/configs/parsing.json

# Use strict mode (fail on warnings)
python -m copilot_config check_compat \
  --old old_schema.json \
  --new new_schema.json \
  --strict
```

### CI Integration

The schema validation workflow automatically runs compatibility checks on pull requests:

1. Detects modified schema files
2. Compares against base branch version
3. Runs compatibility checker
4. Fails if breaking changes without MAJOR version bump

## Configuration Evolution

### Migration Workflow

When evolving configuration schemas:

1. **Update schema file** with new fields/changes
2. **Bump version** according to semver rules
3. **Update min_service_version** if service changes required
4. **Run compatibility checker** locally
5. **Update service code** to handle new configuration
6. **Test with both old and new configs** (if backward compatible)
7. **Submit PR** - CI validates compatibility
8. **Deploy** - services auto-validate schema compatibility

### Adding a New Optional Field

```json
{
  "schema_version": "1.1.0",  // MINOR bump
  "min_service_version": "0.1.0",  // No change
  "fields": {
    "existing_field": { ... },
    "new_optional_field": {
      "type": "string",
      "source": "env",
      "env_var": "NEW_FIELD",
      "default": "default_value",
      "required": false,
      "description": "New optional configuration"
    }
  }
}
```

### Breaking Change (Field Removal)

```json
{
  "schema_version": "2.0.0",  // MAJOR bump
  "min_service_version": "0.2.0",  // Require newer service
  "fields": {
    // "removed_field": { ... },  // Removed
    "existing_field": { ... }
  }
}
```

### Deprecating a Field

Mark fields as deprecated before removal:

```json
{
  "schema_version": "1.2.0",  // MINOR bump
  "fields": {
    "old_field": {
      "type": "string",
      "deprecated": true,
      "description": "DEPRECATED: Use new_field instead"
    },
    "new_field": {
      "type": "string",
      "description": "Replacement for old_field"
    }
  }
}
```

Then in a future MAJOR version, remove the deprecated field.

## Best Practices

### Schema Design

- **Use descriptive field names**: `message_bus_host` not `host`
- **Provide defaults**: All optional fields should have sensible defaults
- **Document fields**: Include clear descriptions
- **Group related fields**: Use consistent naming prefixes
- **Avoid deeply nested structures**: Keep schemas flat when possible

### Version Management

- **Start at 1.0.0**: Initial schemas should be version 1.0.0
- **Bump deliberately**: Consider impact of version changes
- **Communicate changes**: Document breaking changes in release notes
- **Support transitions**: Maintain backward compatibility when possible

### Testing

- **Test schema loading**: Verify configuration loads successfully
- **Test version validation**: Ensure version checks work correctly
- **Test compatibility**: Run compatibility checker in CI
- **Test discovery endpoint**: Verify endpoint returns correct data

### Deployment

- **Deploy schemas first**: Update schema files before service code
- **Monitor startup**: Check for configuration validation errors
- **Rollback plan**: Keep old schemas available for rollbacks
- **Gradual rollout**: Use canary deployments for breaking changes

### Documentation

- **Keep schemas documented**: Update descriptions when changing fields
- **Document migrations**: Provide migration guides for breaking changes
- **Update examples**: Keep example configurations current
- **Link to schemas**: Reference schema files in service documentation

## Example: Complete Migration

### Scenario: Adding JWT Authentication

**Step 1: Update Schema (MINOR version bump)**

```json
{
  "schema_version": "1.1.0",
  "min_service_version": "0.1.0",
  "fields": {
    ...existing fields...,
    "jwt_auth_enabled": {
      "type": "bool",
      "source": "env",
      "env_var": "JWT_AUTH_ENABLED",
      "default": false,
      "required": false,
      "description": "Enable JWT authentication middleware"
    }
  }
}
```

**Step 2: Update Service Code**

```python
config = load_typed_config("parsing")

if config.jwt_auth_enabled:
    app.add_middleware(JWTAuthMiddleware, ...)
```

**Step 3: Deploy**

1. Deploy updated schema
2. Deploy updated service code
3. Enable feature via environment variable: `JWT_AUTH_ENABLED=true`

**Step 4: Make Required (MAJOR version bump later)**

After migration period, make field required:

```json
{
  "schema_version": "2.0.0",
  "min_service_version": "0.2.0",
  "fields": {
    "jwt_auth_enabled": {
      "type": "bool",
      "required": true,
      "default": true,
      ...
    }
  }
}
```

## Troubleshooting

### Service fails to start with version error

**Error**: `Service version X.Y.Z is not compatible with minimum required schema version A.B.C`

**Solution**: Update service to meet minimum version, or downgrade schema.

### CI fails on compatibility check

**Error**: `Breaking changes require MAJOR version bump`

**Solution**: Review changes, bump schema version appropriately, or revert breaking changes.

### Discovery endpoint returns 404

**Cause**: Endpoint not added to service

**Solution**: Add `/.well-known/configuration-schema` endpoint to FastAPI app.

### Schema not found at startup

**Cause**: Schema file missing or wrong location

**Solution**: Ensure schema exists at `documents/schemas/configs/<service>.json`

## References

- [copilot_config README](../adapters/copilot_config/README.md)
- [JSON Schema Specification](https://json-schema.org/)
- [Semantic Versioning](https://semver.org/)
- [RFC 8615: Well-Known URIs](https://www.rfc-editor.org/rfc/rfc8615.html)
