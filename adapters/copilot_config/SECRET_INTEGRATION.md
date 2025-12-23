<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Secret Configuration Integration

This document describes the integration between `copilot_config` and `copilot_secrets` for unified configuration management.

## Overview

The `copilot_config` adapter now supports a `secret` source type that integrates with the `copilot_secrets` adapter. This allows services to have a unified configuration schema that pulls from multiple sources:

- **Environment variables** (`source: "env"`): Public configuration like ports, hostnames, feature flags
- **Secrets** (`source: "secret"`): Sensitive data like API keys, JWT keys, certificates
- **Static** (`source: "static"`): Hardcoded defaults for testing
- **Document stores** (`source: "storage"`): Dynamic runtime configuration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Service Code                        │
│                                                         │
│   config = load_typed_config("auth",                   │
│                secret_provider=secret_config)          │
│                                                         │
│   jwt_key = config.jwt_private_key  # From secrets    │
│   port = config.port                # From env        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              SchemaConfigLoader                         │
│  ┌──────────────────────────────────────────────┐     │
│  │ Field: jwt_private_key                       │     │
│  │ Source: secret                               │     │
│  │ → SecretConfigProvider.get("jwt_private_key")│     │
│  └──────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────┐     │
│  │ Field: port                                   │     │
│  │ Source: env                                   │     │
│  │ → EnvConfigProvider.get("PORT")              │     │
│  └──────────────────────────────────────────────┘     │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│SecretConfigProvider│   │EnvConfigProvider│
└────────┬───────────┘   └──────────────────┘
         │
         ▼
┌──────────────────┐
│LocalFileSecret   │
│Provider          │
│ (copilot_secrets)│
└────────┬───────────┘
         │
         ▼
┌──────────────────┐
│/run/secrets/     │
│├─ jwt_private_key│
│├─ jwt_public_key │
│└─ oauth_secret   │
└──────────────────┘
```

## Schema Definition

Define secret sources in your service schema JSON:

```json
{
  "service_name": "auth",
  "fields": {
    "port": {
      "type": "int",
      "source": "env",
      "env_var": "PORT",
      "default": 8000
    },
    "jwt_private_key": {
      "type": "string",
      "source": "secret",
      "secret_name": "jwt_private_key",
      "required": true,
      "description": "RSA private key for JWT signing"
    }
  }
}
```

### Field Schema Properties for Secrets

- `source`: Must be `"secret"`
- `secret_name`: Name of the secret (file name in local provider, key name in cloud providers)
- `required`: Boolean indicating if the secret must exist
- `default`: Default value if secret is missing and field is optional
- `type`: Data type (`"string"` for text secrets, use `get_bytes()` for binary)

## Usage

### Basic Usage

```python
from copilot_secrets import create_secret_provider
from copilot_config import SecretConfigProvider, load_typed_config

# 1. Create secret provider backend
secrets = create_secret_provider("local", base_path="/run/secrets")

# 2. Wrap in config provider
secret_config = SecretConfigProvider(secret_provider=secrets)

# 3. Load typed config (automatically uses env + secrets)
config = load_typed_config("auth", secret_provider=secret_config)

# 4. Access configuration
print(config.port)             # From environment
print(config.jwt_private_key)  # From secrets
```

### Docker Compose Setup

**docker-compose.yml:**
```yaml
services:
  auth:
    build: ./auth
    volumes:
      - ./secrets:/run/secrets:ro  # Read-only secret mount
    environment:
      PORT: 8000
      LOG_LEVEL: INFO
      SECRETS_BASE_PATH: /run/secrets
```

**Secret files:**
```
secrets/
├── jwt_private_key
├── jwt_public_key
└── github_oauth_client_secret
```

**Service code (auth/main.py):**
```python
import os
from copilot_secrets import create_secret_provider
from copilot_config import SecretConfigProvider, load_typed_config

# Initialize secret provider
base_path = os.getenv("SECRETS_BASE_PATH", "/run/secrets")
secrets = create_secret_provider("local", base_path=base_path)
secret_config = SecretConfigProvider(secret_provider=secrets)

# Load configuration
config = load_typed_config("auth", secret_provider=secret_config)

# Use configuration
app.config["JWT_PRIVATE_KEY"] = config.jwt_private_key
app.config["PORT"] = config.port
```

## Advanced Usage

### Manual Schema and Loader

For more control, create schema and loader manually:

```python
from copilot_secrets import create_secret_provider
from copilot_config import (
    SecretConfigProvider,
    EnvConfigProvider,
    ConfigSchema,
    SchemaConfigLoader,
)

# Create providers
secrets = create_secret_provider("local", base_path="/run/secrets")
secret_provider = SecretConfigProvider(secret_provider=secrets)
env_provider = EnvConfigProvider()

# Load schema
schema = ConfigSchema.from_json_file("schemas/auth.json")

# Create loader with both providers
loader = SchemaConfigLoader(
    schema=schema,
    env_provider=env_provider,
    secret_provider=secret_provider,
)

# Load and validate
config = loader.load()
```

### Testing with Fake Secrets

For unit tests, create a fake secret provider:

```python
class FakeSecretProvider:
    def __init__(self, secrets: dict):
        self._secrets = secrets

    def get_secret(self, name: str) -> str:
        return self._secrets.get(name, "")

    def get_secret_bytes(self, name: str) -> bytes:
        return self.get_secret(name).encode()

    def secret_exists(self, name: str) -> bool:
        return name in self._secrets

# Use in tests
fake_secrets = FakeSecretProvider({
    "jwt_private_key": "TEST-KEY",
    "api_key": "TEST-API-KEY",
})

secret_config = SecretConfigProvider(secret_provider=fake_secrets)
config = load_typed_config("auth", secret_provider=secret_config)
```

## Cloud Provider Support (Future)

The architecture supports cloud secret providers:

```python
# Azure Key Vault (future)
from copilot_secrets import create_secret_provider
secrets = create_secret_provider(
    "azure",
    vault_url="https://myvault.vault.azure.net/"
)

# AWS Secrets Manager (future)
secrets = create_secret_provider(
    "aws",
    region="us-east-1"
)

# GCP Secret Manager (future)
secrets = create_secret_provider(
    "gcp",
    project_id="my-project"
)
```

## Security Best Practices

1. **File Permissions**: Set secret files to `0400` or `0600`
   ```bash
   chmod 0400 secrets/*
   ```

2. **Read-Only Mounts**: Always mount secret directories read-only
   ```yaml
   volumes:
     - ./secrets:/run/secrets:ro
   ```

3. **Never Log Secrets**: Secret values are never logged by providers
   ```python
   # Bad
   logger.info(f"JWT key: {config.jwt_private_key}")

   # Good
   logger.info("JWT key loaded successfully")
   ```

4. **Rotate Regularly**: Use versioned secrets and rotate keys
   ```python
   # With versioned secret stores
   secrets.get_secret("jwt_private_key", version="v2")
   ```

5. **Separate Public/Secret Config**: Keep public config in env, secrets in secret store
   - ✅ `PORT=8000` (environment)
   - ✅ `jwt_private_key` (secret file)
   - ❌ `JWT_PRIVATE_KEY=-----BEGIN...` (environment - insecure!)

## Migration from Environment Variables

**Before (insecure):**
```python
import os
jwt_key = os.getenv("JWT_PRIVATE_KEY")  # Secret in environment!
```

**After (secure):**
1. Move secret to file: `secrets/jwt_private_key`
2. Update schema to use `source: "secret"`
3. Update code:
   ```python
   from copilot_config import load_typed_config, SecretConfigProvider
   from copilot_secrets import create_secret_provider

   secrets = create_secret_provider("local", base_path="/run/secrets")
   secret_config = SecretConfigProvider(secret_provider=secrets)
   config = load_typed_config("auth", secret_provider=secret_config)
   jwt_key = config.jwt_private_key
   ```

## Troubleshooting

### Secret Not Found
```python
# Error: SecretNotFoundError: Secret not found: jwt_private_key

# Fix: Ensure secret file exists
ls -la /run/secrets/jwt_private_key

# Fix: Check SECRETS_BASE_PATH
echo $SECRETS_BASE_PATH
```

### Permission Denied
```bash
# Error: PermissionError: [Errno 13] Permission denied

# Fix: Adjust file permissions
chmod 0400 /run/secrets/jwt_private_key

# Fix: Run container with correct user
docker-compose.yml:
  auth:
    user: "1000:1000"  # Match file owner
```

### Configuration Validation Failed
```python
# Error: Required field 'jwt_private_key' is missing

# Fix: Ensure secret_provider is passed to load_typed_config
config = load_typed_config(
    "auth",
    secret_provider=secret_config  # Don't forget this!
)
```

## Testing

Run copilot_config tests with secret integration:

```bash
cd adapters/copilot_config
pytest tests/test_secret_provider.py -v
pytest tests/test_secret_integration.py -v
```

## See Also

- [copilot_secrets README](../copilot_secrets/README.md)
- [copilot_config README](README.md)
- [Example: secret_config_example.py](examples/secret_config_example.py)
- [Example Schema: auth-example.json](examples/auth-example.json)
