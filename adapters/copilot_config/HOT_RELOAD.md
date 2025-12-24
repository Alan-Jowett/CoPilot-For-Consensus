<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Hot-Reload Configuration (Phase 3)

This document describes the hot-reload configuration system introduced in Phase 3 of the configuration architecture.

## Overview

The hot-reload system allows services to dynamically update their configuration without restarts by:
1. Storing configurations centrally in the **Config Registry** service
2. Publishing change notifications via the message bus
3. Services subscribing to changes and reloading configuration

## Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Service   │─────>│  Config Registry │─────>│  MongoDB     │
│             │<─────│  (REST API)      │      │  (Storage)   │
└──────┬──────┘      └──────────┬───────┘      └──────────────┘
       │                        │
       │ Subscribe              │ Publish
       ▼                        ▼
┌─────────────────────────────────────────┐
│         RabbitMQ (Event Bus)            │
│   Exchange: config.changes              │
│   Routes: config.created, config.updated│
└─────────────────────────────────────────┘
```

## Components

### 1. Config Registry Service

Central configuration storage and management service.

**Features:**
- RESTful API for CRUD operations
- Version control with history tracking
- Environment-specific configurations
- Change notifications via message bus
- Configuration diffing

**API Endpoints:**
- `GET /api/configs/{service_name}` - Get configuration
- `POST /api/configs/{service_name}` - Create configuration
- `PUT /api/configs/{service_name}` - Update configuration (new version)
- `DELETE /api/configs/{service_name}` - Delete configuration
- `GET /api/configs/{service_name}/history` - Get version history
- `GET /api/configs/{service_name}/diff` - Compare versions

### 2. RegistryConfigProvider

Configuration provider that fetches from the registry service.

**Features:**
- TTL-based caching for performance
- Automatic cache refresh on expiry
- Graceful fallback to defaults on errors

**Example:**
```python
from copilot_config import RegistryConfigProvider

# Create provider
config = RegistryConfigProvider(
    registry_url="http://config-registry:8000",
    service_name="parsing",
    environment="prod",
    cache_ttl_seconds=60  # Refresh every 60 seconds
)

# Access config
db_host = config.get("db_host")
port = config.get_int("port", 5432)
debug = config.get_bool("debug", False)

# Force refresh
config.refresh()
```

### 3. ConfigWatcher

Monitors the registry for configuration changes and triggers callbacks.

**Features:**
- Polls registry for version changes
- Triggers callback on updates
- Configurable polling interval

**Example:**
```python
from copilot_config import ConfigWatcher

def on_config_change(new_config: dict):
    """Called when configuration changes."""
    print(f"Config updated: {new_config}")
    # Reload application components with new config
    reload_database_connection(new_config)
    reload_cache_settings(new_config)

# Create watcher
watcher = ConfigWatcher(
    registry_url="http://config-registry:8000",
    service_name="parsing",
    environment="prod",
    poll_interval_seconds=30,
    on_change=on_config_change
)

# Start watching (blocking)
watcher.start()
```

## Usage Patterns

### Pattern 1: Startup Configuration with TTL Refresh

Best for: Services that need updated config periodically but can tolerate some staleness.

```python
from copilot_config import RegistryConfigProvider

# Create provider with 60-second TTL
config = RegistryConfigProvider(
    registry_url="http://config-registry:8000",
    service_name="my-service",
    environment="prod",
    cache_ttl_seconds=60
)

# Config automatically refreshes every 60 seconds on next access
while True:
    db_host = config.get("db_host")
    # Use config...
    time.sleep(10)
```

### Pattern 2: Active Watching with Callback

Best for: Services that need immediate response to config changes.

```python
from copilot_config import ConfigWatcher
import threading

def reload_config(new_config: dict):
    """Reload application components."""
    global app_config
    app_config = new_config
    # Reload components...

# Start watcher in background thread
watcher = ConfigWatcher(
    registry_url="http://config-registry:8000",
    service_name="my-service",
    environment="prod",
    poll_interval_seconds=15,
    on_change=reload_config
)

watcher_thread = threading.Thread(target=watcher.start, daemon=True)
watcher_thread.start()

# Main application logic continues...
```

### Pattern 3: Environment Overlays

Best for: Different configurations per environment (dev, staging, prod).

```python
import os
from copilot_config import RegistryConfigProvider

# Determine environment
environment = os.environ.get("ENVIRONMENT", "default")

# Load config for specific environment
config = RegistryConfigProvider(
    registry_url="http://config-registry:8000",
    service_name="my-service",
    environment=environment,  # "dev", "staging", or "prod"
    cache_ttl_seconds=60
)

# Each environment can have different values
db_host = config.get("db_host")  # localhost in dev, prod-db in prod
```

## Configuration Management Workflow

### 1. Create Initial Configuration

```bash
curl -X POST http://config-registry:8000/api/configs/parsing?environment=prod \
  -H "Content-Type: application/json" \
  -d '{
    "config_data": {
      "db_host": "production-db",
      "db_port": 5432,
      "max_connections": 100
    },
    "comment": "Initial production config",
    "created_by": "admin"
  }'
```

### 2. Update Configuration

```bash
curl -X PUT http://config-registry:8000/api/configs/parsing?environment=prod \
  -H "Content-Type: application/json" \
  -d '{
    "config_data": {
      "db_host": "production-db",
      "db_port": 5432,
      "max_connections": 200
    },
    "comment": "Increased max connections",
    "created_by": "admin"
  }'
```

This creates version 2. Services using `RegistryConfigProvider` will pick up the change on next cache refresh. Services using `ConfigWatcher` will be notified immediately.

### 3. View History

```bash
curl http://config-registry:8000/api/configs/parsing/history?environment=prod&limit=5
```

### 4. Compare Versions

```bash
curl http://config-registry:8000/api/configs/parsing/diff?environment=prod&old_version=1&new_version=2
```

Returns:
```json
{
  "service_name": "parsing",
  "environment": "prod",
  "old_version": 1,
  "new_version": 2,
  "added": {},
  "removed": {},
  "changed": {
    "max_connections": {
      "old": 100,
      "new": 200
    }
  }
}
```

## Best Practices

### 1. Use Environment Overlays

Organize configurations by environment:
- `default`: Base configuration with sensible defaults
- `dev`: Development-specific overrides
- `staging`: Staging-specific overrides
- `prod`: Production configuration

### 2. Set Appropriate Cache TTLs

- **High-frequency changes**: 10-30 seconds
- **Normal operations**: 60-120 seconds
- **Stable configs**: 300-600 seconds

Shorter TTLs mean more registry calls but faster updates. Longer TTLs reduce load but delay updates.

### 3. Use ConfigWatcher for Critical Settings

For settings that need immediate updates (security configs, feature flags), use `ConfigWatcher` instead of TTL-based refresh.

### 4. Version Control All Changes

Always include meaningful comments when updating configurations:
```python
update = ConfigUpdate(
    config_data=new_config,
    comment="Increased timeout for external API calls",
    created_by="admin"
)
```

### 5. Test Configuration Changes

Before updating production:
1. Update `dev` environment
2. Test with services
3. Update `staging` environment
4. Validate in staging
5. Update `prod` environment

### 6. Monitor Configuration Changes

Subscribe to config change events to track updates:
```python
from copilot_events import create_subscriber

subscriber = create_subscriber(
    bus_type="rabbitmq",
    host="messagebus",
    port=5672
)

def on_config_change(event):
    print(f"Config changed: {event}")
    # Log to audit system

subscriber.subscribe("config.changes", on_config_change)
```

## Security Considerations

### 1. Access Control

Implement authentication and authorization for config registry:
- Read: All services
- Write: Admin users only
- Delete: Super admin only

### 2. Sensitive Data

Do NOT store secrets in config registry. Use:
- Docker secrets for sensitive values
- Environment variables for runtime secrets
- Dedicated secret management (Azure Key Vault, HashiCorp Vault)

### 3. Audit Logging

All configuration changes are logged with:
- Timestamp
- User who made the change
- Change comment
- Old and new values (for audit trail)

### 4. Validation

Validate configuration data against schemas before accepting:
```python
from copilot_config import load_typed_config

# Validate new config matches schema
try:
    validated = load_typed_config("parsing", config_data=new_config)
except ConfigValidationError as e:
    print(f"Invalid config: {e}")
```

## Troubleshooting

### Configuration Not Updating

1. **Check cache TTL**: Is it too long?
2. **Verify registry is running**: `curl http://config-registry:8000/health`
3. **Check service can reach registry**: Network connectivity
4. **Verify environment**: Are you querying the right environment?

### High Registry Load

1. **Increase cache TTL**: Reduce refresh frequency
2. **Use ConfigWatcher selectively**: Only for critical services
3. **Implement request batching**: Fetch multiple configs at once

### Version Conflicts

1. **Use diff endpoint**: Compare versions to understand changes
2. **Review history**: Check who made changes and when
3. **Rollback if needed**: Update to previous version

## Migration from Phase 2

Services using Phase 1/2 configuration (env vars + schema) can migrate gradually:

```python
# Old way (Phase 1/2)
from copilot_config import load_typed_config
config = load_typed_config("my-service")

# New way (Phase 3 - with fallback)
from copilot_config import RegistryConfigProvider, load_typed_config

try:
    # Try registry first
    config = RegistryConfigProvider(
        registry_url="http://config-registry:8000",
        service_name="my-service",
        environment="prod"
    )
except Exception:
    # Fall back to env vars
    config = load_typed_config("my-service")
```

## Related Documentation

- [Config Registry Service](../config-registry/README.md)
- [Phase 1: Schema-Driven Configuration](README.md)
- [Phase 2: Schema Versioning](../../documents/SCHEMA_VERSIONING.md)
- [Configuration Migration Guide](../../documents/CONFIGURATION_MIGRATION.md)

## License

MIT License - See [LICENSE](../../LICENSE) for details.
