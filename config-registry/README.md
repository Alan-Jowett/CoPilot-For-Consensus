<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Config Registry Service

Centralized configuration management microservice with hot-reload support and environment-specific overlays.

## Overview

The Config Registry service is part of **Phase 3** of the configuration system evolution, providing:

- **Centralized Configuration Storage**: Store and manage configurations for all services
- **Version Control**: Track configuration changes with full version history
- **Environment Overlays**: Support for environment-specific configs (local, dev, staging, prod)
- **Hot-Reload**: Real-time configuration updates via event notifications
- **Configuration Diffing**: Compare configuration versions
- **REST API**: Full CRUD operations for configuration management

## Architecture

```
┌─────────────────────┐
│   Config Registry   │
│   (FastAPI)         │
├─────────────────────┤
│ - CRUD APIs         │
│ - Versioning        │
│ - Notifications     │
│ - Diffing           │
└──────┬───────┬──────┘
       │       │
       ▼       ▼
   MongoDB   RabbitMQ
   (Store)   (Events)
```

## Features

### 1. Configuration Storage

Configurations are stored with:
- **Service name**: Identifies the service (e.g., "parsing")
- **Environment**: Deployment environment (default, dev, staging, prod)
- **Version**: Auto-incrementing version number
- **Metadata**: Creation timestamp, author, change comment
- **Config data**: Actual configuration values

### 2. Version Control

Every configuration update creates a new version, maintaining a complete audit trail:
- View configuration history
- Compare versions with built-in diff tool
- Rollback to previous versions

### 3. Environment Overlays

Support for environment-specific configurations:
```
default → dev → staging → prod
  (base)   (override)
```

### 4. Change Notifications

Publishes events to message bus on configuration changes:
- `config.created`: New configuration created
- `config.updated`: Configuration updated (new version)
- `config.deleted`: Configuration deleted

Services can subscribe to these events for hot-reload.

## REST API

### Configuration Management

#### Get Configuration
```bash
GET /api/configs/{service_name}?environment=dev&version=5
```

#### Create Configuration
```bash
POST /api/configs/{service_name}?environment=dev
{
  "config_data": { ... },
  "comment": "Initial dev config",
  "created_by": "admin"
}
```

#### Update Configuration (New Version)
```bash
PUT /api/configs/{service_name}?environment=dev
{
  "config_data": { ... },
  "comment": "Updated database connection",
  "created_by": "admin"
}
```

#### Delete Configuration
```bash
DELETE /api/configs/{service_name}?environment=dev&version=5
```

#### List All Configurations
```bash
GET /api/configs?service_name=parsing&environment=dev
```

### History and Comparison

#### Get Configuration History
```bash
GET /api/configs/{service_name}/history?environment=dev&limit=10
```

#### Compare Versions
```bash
GET /api/configs/{service_name}/diff?environment=dev&old_version=4&new_version=5
```

Returns:
```json
{
  "service_name": "parsing",
  "environment": "dev",
  "old_version": 4,
  "new_version": 5,
  "added": { "new_field": "value" },
  "removed": { "old_field": "value" },
  "changed": {
    "field_name": {
      "old": "old_value",
      "new": "new_value"
    }
  }
}
```

### Health and Monitoring

#### Health Check
```bash
GET /health
```

#### Service Statistics
```bash
GET /stats
```

## Configuration Schema

Configuration schema located at `documents/schemas/configs/config-registry.json`.

Key settings:
- `MESSAGE_BUS_*`: Message bus connection for notifications
- `DOCUMENT_DATABASE_*`: MongoDB connection for storage
- `HTTP_PORT`: Service port (default: 8000)
- `LOG_LEVEL`: Logging level

## Docker Deployment

The service is included in the main `docker-compose.yml`:

```yaml
config-registry:
  build: ./config-registry
  environment:
    - DOCUMENT_DATABASE_NAME=copilot_config
    - MESSAGE_BUS_HOST=messagebus
  depends_on:
    - documentdb
    - messagebus
  ports:
    - "127.0.0.1:8010:8000"
```

## Integration with Other Services

Services can integrate with the Config Registry in two ways:

### 1. Pull-Based (Startup)
Services fetch their configuration on startup:

```python
from copilot_config import RegistryConfigProvider

config_provider = RegistryConfigProvider(
    registry_url="http://config-registry:8000",
    service_name="parsing",
    environment="prod"
)
config = config_provider.get_config()
```

### 2. Push-Based (Hot-Reload)
Services subscribe to configuration change events:

```python
from copilot_config import ConfigWatcher

watcher = ConfigWatcher(
    registry_url="http://config-registry:8000",
    service_name="parsing",
    environment="prod",
    on_change=reload_config
)
watcher.start()
```

## Development

### Running Tests

```bash
cd config-registry
pytest tests/ -v
```

### Local Development

```bash
# Start dependencies
docker compose up -d documentdb messagebus

# Run service locally
cd config-registry
python main.py
```

## Security Considerations

- **Authentication**: Integrate with auth service for access control
- **Authorization**: Role-based access for config operations
- **Audit Logging**: All changes are logged with user attribution
- **Validation**: Configuration data is validated against schemas
- **Secrets**: Sensitive values should use secret management

## Related Documentation

- [Phase 1: Schema-Driven Configuration](../adapters/copilot_config/README.md)
- [Phase 2: Schema Versioning](../documents/SCHEMA_VERSIONING.md)
- [Phase 3: Hot-Reload Implementation](../adapters/copilot_config/HOT_RELOAD.md)
- [Configuration Migration Guide](../documents/CONFIGURATION_MIGRATION.md)

## License

MIT License - See [LICENSE](../LICENSE) for details.
