# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# MongoDB Environment Variable Migration Guide

## Overview

This guide explains the migration from `MONGO_*` to `DOC_DB_*` environment variables for MongoDB configuration in the Copilot-for-Consensus project.

## Background

Previously, there was an inconsistency between:
- **docker-compose.yml**: Used `MONGO_*` environment variables
- **Service config schemas**: Expected `DOC_DB_*` environment variables

This mismatch caused MongoDB authentication and config loading failures for services.

## Changes

### New Standard: DOC_DB_* Variables

All services now use the following environment variables for document store (MongoDB) configuration:

| New Variable | Old Variable | Description | Default |
|-------------|--------------|-------------|---------|
| `DOC_DB_HOST` | `MONGO_HOST` | MongoDB hostname | `documentdb` |
| `DOC_DB_PORT` | `MONGO_PORT` | MongoDB port | `27017` |
| `DOC_DB_NAME` | `MONGO_DB` | Database name | `copilot` |
| `DOC_DB_USER` | `MONGO_USER` | MongoDB username | (empty) |
| `DOC_DB_PASSWORD` | `MONGO_PASSWORD` | MongoDB password | (empty) |

### Additional Variable

| Variable | Description | Default |
|----------|-------------|---------|
| `DOC_STORE_TYPE` | Document store type | `mongodb` |

## Migration Instructions

### Option 1: Update docker-compose.yml (Recommended)

If you have a custom docker-compose.yml or .env file, update your environment variables:

```yaml
services:
  myservice:
    environment:
      # Old (deprecated)
      # - MONGO_HOST=documentdb
      # - MONGO_PORT=27017
      # - MONGO_DB=copilot
      # - MONGO_USER=root
      # - MONGO_PASSWORD=example
      
      # New (recommended)
      - DOC_STORE_TYPE=mongodb
      - DOC_DB_HOST=documentdb
      - DOC_DB_PORT=27017
      - DOC_DB_NAME=copilot
      - DOC_DB_USER=root
      - DOC_DB_PASSWORD=example
```

### Option 2: Update .env file

If you use a `.env` file:

```bash
# Old (deprecated)
# MONGO_HOST=documentdb
# MONGO_PORT=27017
# MONGO_DB=copilot
# MONGO_USER=root
# MONGO_PASSWORD=example

# New (recommended)
DOC_STORE_TYPE=mongodb
DOC_DB_HOST=documentdb
DOC_DB_PORT=27017
DOC_DB_NAME=copilot
DOC_DB_USER=root
DOC_DB_PASSWORD=example
```

## Backward Compatibility

The system maintains **full backward compatibility** with the old `MONGO_*` variables:

- If both `DOC_DB_*` and `MONGO_*` are set, `DOC_DB_*` takes precedence
- If only `MONGO_*` is set, it will be used with a **deprecation warning**
- If neither is set, defaults are used

### Deprecation Warnings

When using old `MONGO_*` variables, you'll see warnings like:

```
DeprecationWarning: MONGO_HOST is deprecated. Please use DOC_DB_HOST instead.
```

These warnings are informational and don't prevent the system from working.

## Migration Timeline

1. **Current**: Both `MONGO_*` and `DOC_DB_*` are supported
2. **Next Release**: Deprecation warnings for `MONGO_*` variables
3. **Future Release**: `MONGO_*` support may be removed

## Services Affected

All services that connect to MongoDB now use `DOC_DB_*` variables:

- ingestion
- parsing
- chunking
- embedding
- orchestrator
- summarization
- reporting

## Testing Your Migration

After updating your environment variables:

1. Start the services:
   ```bash
   docker-compose up -d
   ```

2. Check service logs for deprecation warnings:
   ```bash
   docker-compose logs | grep -i "deprecated"
   ```

3. Verify services connect to MongoDB:
   ```bash
   docker-compose logs | grep -i "connected"
   ```

4. Check health endpoints:
   ```bash
   curl http://localhost:8000/health  # ingestion
   curl http://localhost:8080/health  # reporting
   ```

## Troubleshooting

### Service can't connect to MongoDB

**Symptom**: Error logs showing "Failed to connect to document store"

**Solution**: Verify environment variables are set correctly:
```bash
docker-compose exec myservice env | grep DOC_DB
```

### Deprecation warnings in logs

**Symptom**: Warnings about `MONGO_*` variables being deprecated

**Solution**: Update your environment variables to use `DOC_DB_*` as shown above.

### Mixed old and new variables

**Symptom**: Unexpected values being used

**Solution**: Remove old `MONGO_*` variables and use only `DOC_DB_*` variables for consistency.

## Questions?

If you encounter issues during migration:

1. Check the [CONFIGURATION_MIGRATION.md](./CONFIGURATION_MIGRATION.md) guide
2. Review service-specific README files
3. Check service logs for connection errors
4. Verify MongoDB container is running: `docker-compose ps documentdb`

## Examples

### Docker Compose Example

```yaml
services:
  parsing:
    image: copilot-parsing:latest
    environment:
      - SCHEMA_DIR=/app/documents/schemas/configs
      - MESSAGE_BUS_HOST=messagebus
      - MESSAGE_BUS_PORT=5672
      - DOC_STORE_TYPE=mongodb
      - DOC_DB_HOST=documentdb
      - DOC_DB_PORT=27017
      - DOC_DB_NAME=copilot
      - DOC_DB_USER=${MONGO_INITDB_ROOT_USERNAME:-root}
      - DOC_DB_PASSWORD=${MONGO_INITDB_ROOT_PASSWORD:-example}
```

### Kubernetes ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mongodb-config
data:
  DOC_STORE_TYPE: "mongodb"
  DOC_DB_HOST: "mongodb-service"
  DOC_DB_PORT: "27017"
  DOC_DB_NAME: "copilot"
```

### Docker Run Example

```bash
docker run -d \
  -e DOC_STORE_TYPE=mongodb \
  -e DOC_DB_HOST=documentdb \
  -e DOC_DB_PORT=27017 \
  -e DOC_DB_NAME=copilot \
  -e DOC_DB_USER=root \
  -e DOC_DB_PASSWORD=example \
  copilot-parsing:latest
```
