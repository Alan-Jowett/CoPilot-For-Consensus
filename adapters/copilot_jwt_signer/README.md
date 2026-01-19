# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# JWT Signer Adapter

This adapter provides abstraction for JWT signing operations, supporting both local file-based signing and Azure Key Vault cryptographic operations.

## Features

- **Local Signing**: File-based RSA, EC, and HMAC signing
- **Key Vault Signing**: Azure Key Vault cryptographic operations (no private key egress)
- **Algorithm Support**: RS256, RS384, RS512, ES256, ES384, ES512, HS256, HS384, HS512
- **Key Rotation**: Support for multiple key versions via JWKS
- **Resilience**: Retry logic, circuit breaker, and health checks

## Installation

```bash
# For local signing only
pip install -e .

# For Key Vault signing
pip install -e ".[azure]"
```

## Usage

### Using the Factory (Recommended)

The factory function follows the standard adapter pattern used across the project:

```python
from copilot_jwt_signer import create_jwt_signer
from copilot_config import DriverConfig

# Local RSA signing
config = DriverConfig(
    algorithm="RS256",
    key_id="my-key-2024",
    private_key_path="/path/to/private.pem",
    public_key_path="/path/to/public.pem"
)
signer = create_jwt_signer("local", config)

# Key Vault signing
config = DriverConfig(
    algorithm="RS256",
    key_id="my-key-2024",
    key_vault_url="https://my-vault.vault.azure.net/",
    key_name="jwt-signing-key",
    max_retries=3,
    retry_delay=0.5
)
signer = create_jwt_signer("keyvault", config)

# Sign a message
message = b"header.payload"
signature = signer.sign(message)

# Get public key for JWKS
jwk = signer.get_public_key_jwk()
```

### Direct Instantiation (Advanced)

For direct instantiation without the factory:

```python
from copilot_jwt_signer import LocalJWTSigner
from pathlib import Path

signer = LocalJWTSigner(
    algorithm="RS256",
    private_key_path=Path("/path/to/private.pem"),
    public_key_path=Path("/path/to/public.pem"),
    key_id="my-key-2024"
)
```

### Health Check

```python
# Check if signer is healthy
if signer.health_check():
    print("Signer is healthy")
else:
    print("Signer is unhealthy")
```

## Configuration

### Local Signer

- `algorithm`: Signing algorithm (RS256, RS384, RS512, ES256, ES384, ES512, HS256, HS384, HS512)
- `private_key_path`: Path to private key PEM file (for asymmetric algorithms)
- `public_key_path`: Path to public key PEM file (for asymmetric algorithms)
- `secret_key`: HMAC secret (for symmetric algorithms)
- `key_id`: Key identifier for rotation support

### Key Vault Signer

- `algorithm`: Signing algorithm (RS256, RS384, RS512, ES256, ES384, ES512)
- `key_vault_url`: Azure Key Vault URL
- `key_name`: Name of the key in Key Vault
- `key_version`: Optional specific version (uses latest if not specified)
- `key_id`: Key identifier for JWT header
- `max_retries`: Maximum retry attempts (default: 3)
- `retry_delay`: Initial retry delay in seconds (default: 1.0)
- `circuit_breaker_threshold`: Failures before opening circuit (default: 5)
- `circuit_breaker_timeout`: Seconds before retry after circuit opens (default: 60)

## Architecture

The adapter uses a provider pattern with three main components:

1. **JWTSigner** (abstract base class): Defines the interface for signing operations
2. **LocalJWTSigner**: Implements local file-based signing
3. **KeyVaultJWTSigner**: Implements Azure Key Vault cryptographic operations

## Security

### Local Signer

- Private keys stored on disk (consider using Key Vault for production)
- Supports encrypted private keys with password protection
- HMAC secrets should be kept in secure storage

### Key Vault Signer

- Private key never leaves Key Vault
- Uses managed identity for authentication (no credentials in code)
- Supports RBAC with least-privilege permissions (`crypto/sign`, `keys/get`)
- Circuit breaker prevents cascading failures

## Testing

```bash
# Run unit tests
pytest

# Run with coverage
pytest --cov=copilot_jwt_signer --cov-report=html
```

## License

MIT License - See LICENSE file for details
