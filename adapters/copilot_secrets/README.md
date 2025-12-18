<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# copilot_secrets

Secret management adapter for retrieving sensitive configuration data like API keys, JWT signing keys, and certificates.

## Features

- **Unified Interface**: Single API for accessing secrets from multiple backends
- **Local File Storage**: Read secrets from filesystem (Docker volumes, Kubernetes secrets)
- **Extensible**: Designed for future cloud provider integrations (Azure Key Vault, AWS Secrets Manager, GCP Secret Manager)
- **Security**: Path traversal prevention, binary secret support
- **Type-Safe**: String and binary secret retrieval methods

## Installation

```bash
pip install -e .
```

## Usage

### Local File Provider

Store secrets as individual files in a directory:

```python
from copilot_secrets import create_secret_provider

# Initialize provider
provider = create_secret_provider("local", base_path="/run/secrets")

# Retrieve text secrets
api_key = provider.get_secret("api_key")
jwt_private_key = provider.get_secret("jwt_private_key")

# Retrieve binary secrets (e.g., certificates)
cert_bytes = provider.get_secret_bytes("tls_cert.pem")

# Check if secret exists
if provider.secret_exists("optional_key"):
    key = provider.get_secret("optional_key")
```

### Docker Volume Example

Mount secrets as a volume in `docker-compose.yml`:

```yaml
services:
  myservice:
    image: myservice:latest
    volumes:
      - ./secrets:/run/secrets:ro
    environment:
      SECRETS_BASE_PATH: /run/secrets
```

Service code:

```python
import os
from copilot_secrets import create_secret_provider

base_path = os.getenv("SECRETS_BASE_PATH", "/run/secrets")
secrets = create_secret_provider("local", base_path=base_path)

jwt_key = secrets.get_secret("jwt_private_key")
```

### Secret File Structure

```
/run/secrets/
├── api_key                  # Plain text API key
├── jwt_private_key          # RSA private key (PEM)
├── jwt_public_key           # RSA public key (PEM)
└── database_password        # Database credentials
```

Each file contains exactly one secret. Whitespace is automatically stripped for text secrets.

## Architecture

### Provider Interface

All secret providers implement the `SecretProvider` abstract base class:

```python
class SecretProvider(ABC):
    def get_secret(self, secret_name: str, version: Optional[str] = None) -> str:
        """Retrieve a secret as a string."""
        pass
    
    def get_secret_bytes(self, secret_name: str, version: Optional[str] = None) -> bytes:
        """Retrieve a secret as raw bytes."""
        pass
    
    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists."""
        pass
```

### Local File Provider

- **Storage**: One file per secret in a base directory
- **Security**: Path traversal prevention (`..` and absolute paths blocked)
- **Text Mode**: Strips whitespace, reads as UTF-8
- **Binary Mode**: Preserves all bytes (for keys, certs)

### Future Providers

Planned implementations:

- **Azure Key Vault**: `create_secret_provider("azure", vault_url="https://...")`
- **AWS Secrets Manager**: `create_secret_provider("aws", region="us-east-1")`
- **GCP Secret Manager**: `create_secret_provider("gcp", project_id="...")`

## Error Handling

```python
from copilot_secrets import (
    SecretNotFoundError,
    SecretProviderError,
)

try:
    key = provider.get_secret("missing_key")
except SecretNotFoundError:
    print("Secret does not exist")
except SecretProviderError as e:
    print(f"Provider error: {e}")
```

## Testing

Run unit tests:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=copilot_secrets --cov-report=term --cov-report=html
```

## Integration with Auth Service

The auth service can use this adapter for JWT key management:

```python
from copilot_secrets import create_secret_provider

secrets = create_secret_provider("local", base_path="/app/config")

jwt_manager = JWTManager(
    private_key_path=None,  # Load from secrets instead
    public_key_path=None,
    private_key=secrets.get_secret("jwt_private_key"),
    public_key=secrets.get_secret("jwt_public_key"),
)
```

## Security Considerations

1. **File Permissions**: Secret files should be readable only by the service user (mode 0400 or 0600)
2. **Path Validation**: Provider prevents path traversal attacks (`../`, absolute paths)
3. **No Logging**: Secret values are never logged by the provider
4. **Volume Mounts**: Use read-only mounts (`:ro`) when mounting secret directories
5. **Kubernetes Secrets**: Compatible with `kubectl create secret generic` mounted secrets

## License

MIT License - see [LICENSE](../../LICENSE) for details.
