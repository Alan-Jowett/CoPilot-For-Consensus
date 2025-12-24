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
# Base installation
pip install -e .

# With Azure Key Vault support
pip install -e ".[azure]"
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

### Azure Key Vault Provider

Store and retrieve secrets from Azure Key Vault with managed identity support:

```python
from copilot_secrets import create_secret_provider

# Using vault name (simplest for Azure-hosted services)
provider = create_secret_provider("azure", vault_name="my-production-vault")

# Or using full vault URL
provider = create_secret_provider(
    "azure",
    vault_url="https://my-vault.vault.azure.net/"
)

# Retrieve secrets
api_key = provider.get_secret("api-key")
jwt_private_key = provider.get_secret("jwt-private-key")

# Retrieve specific version
old_key = provider.get_secret("api-key", version="abc123def456")

# Check if secret exists
if provider.secret_exists("optional-feature-key"):
    feature_key = provider.get_secret("optional-feature-key")
```

#### Configuration via Environment Variables

```python
import os
from copilot_secrets import create_secret_provider

# Option 1: Set vault name
os.environ["AZURE_KEY_VAULT_NAME"] = "my-vault"
provider = create_secret_provider("azure")

# Option 2: Set full vault URI
os.environ["AZURE_KEY_VAULT_URI"] = "https://my-vault.vault.azure.net/"
provider = create_secret_provider("azure")
```

#### Authentication Methods

The Azure provider uses `DefaultAzureCredential` from `azure-identity`, which tries multiple authentication methods in order:

1. **Managed Identity** (recommended for production)
   - Works automatically on Azure App Service, Azure Functions, Azure VMs, Azure Container Instances
   - No credentials needed in code or environment

2. **Environment Variables** (for local development or CI/CD)
   ```bash
   export AZURE_TENANT_ID="your-tenant-id"
   export AZURE_CLIENT_ID="your-client-id"
   export AZURE_CLIENT_SECRET="your-client-secret"
   ```

3. **Azure CLI** (for local development)
   ```bash
   az login
   # Then run your application
   ```

4. **Visual Studio Code** (for local development)
   - Azure Account extension automatically provides credentials

#### Docker/Kubernetes Deployment

```yaml
# docker-compose.yml
services:
  myservice:
    image: myservice:latest
    environment:
      AZURE_KEY_VAULT_NAME: my-production-vault
      # For managed identity on Azure, no additional config needed

      # For local dev with service principal:
      AZURE_TENANT_ID: ${AZURE_TENANT_ID}
      AZURE_CLIENT_ID: ${AZURE_CLIENT_ID}
      AZURE_CLIENT_SECRET: ${AZURE_CLIENT_SECRET}
```

#### Azure Key Vault Setup

1. **Create a Key Vault:**
   ```bash
   az keyvault create \
     --name my-vault \
     --resource-group my-rg \
     --location eastus
   ```

2. **Add secrets:**
   ```bash
   az keyvault secret set \
     --vault-name my-vault \
     --name api-key \
     --value "my-secret-api-key"
   ```

3. **Grant access to managed identity:**
   ```bash
   # For App Service or Azure Function
   az keyvault set-policy \
     --name my-vault \
     --object-id $(az webapp identity show \
       --name my-app \
       --resource-group my-rg \
       --query principalId -o tsv) \
     --secret-permissions get list
   ```

4. **Grant access to service principal (for local dev):**
   ```bash
   az keyvault set-policy \
     --name my-vault \
     --spn $AZURE_CLIENT_ID \
     --secret-permissions get list
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
6. **Azure Key Vault**:
   - Use managed identities instead of service principals when possible
   - Enable soft-delete and purge protection on Key Vaults
   - Use Azure RBAC or access policies to grant least-privilege access
   - Rotate secrets regularly and use versioning
   - Monitor access with Azure Monitor and Azure Key Vault logs

## License

MIT License - see [LICENSE](../../LICENSE) for details.
