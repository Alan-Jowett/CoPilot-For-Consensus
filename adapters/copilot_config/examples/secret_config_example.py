# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example: Using secret configuration with copilot_config and copilot_secrets.

This example demonstrates how to use the SecretConfigProvider to load
configuration from both environment variables and secret storage.
"""

import os
from copilot_secrets import create_secret_provider
from copilot_config import (
    SecretConfigProvider,
    EnvConfigProvider,
    SchemaConfigLoader,
    ConfigSchema,
)


def main():
    """Example of loading configuration with secrets."""
    
    # 1. Create secret provider (from copilot_secrets)
    #    In production, secrets are mounted as Docker volumes or from cloud key vault
    secret_base_path = os.getenv("SECRETS_BASE_PATH", "/run/secrets")
    secrets = create_secret_provider("local", base_path=secret_base_path)
    
    # 2. Wrap it in a SecretConfigProvider (for copilot_config)
    secret_config = SecretConfigProvider(secret_provider=secrets)
    
    # 3. Create environment provider for non-secret config
    env_config = EnvConfigProvider()
    
    # 4. Define your service schema
    schema = ConfigSchema(
        service_name="auth",
        fields={
            # Public config from environment
            "service_name": ConfigSchema._parse_field_spec("service_name", {
                "type": "string",
                "source": "env",
                "env_var": "SERVICE_NAME",
                "default": "auth-service",
            }),
            "port": ConfigSchema._parse_field_spec("port", {
                "type": "int",
                "source": "env",
                "env_var": "PORT",
                "default": 8000,
            }),
            "log_level": ConfigSchema._parse_field_spec("log_level", {
                "type": "string",
                "source": "env",
                "env_var": "LOG_LEVEL",
                "default": "INFO",
            }),
            
            # Sensitive config from secrets
            "jwt_private_key": ConfigSchema._parse_field_spec("jwt_private_key", {
                "type": "string",
                "source": "secret",
                "secret_name": "jwt_private_key",
                "required": True,
                "description": "RSA private key for JWT signing (PEM format)",
            }),
            "jwt_public_key": ConfigSchema._parse_field_spec("jwt_public_key", {
                "type": "string",
                "source": "secret",
                "secret_name": "jwt_public_key",
                "required": True,
                "description": "RSA public key for JWT verification (PEM format)",
            }),
            "oidc_client_secret": ConfigSchema._parse_field_spec("oidc_client_secret", {
                "type": "string",
                "source": "secret",
                "secret_name": "github_oauth_client_secret",
                "required": True,
                "description": "OAuth client secret for GitHub",
            }),
        }
    )
    
    # 5. Load configuration
    loader = SchemaConfigLoader(
        schema=schema,
        env_provider=env_config,
        secret_provider=secret_config,
    )
    
    config = loader.load()
    
    # 6. Use configuration
    print(f"Service: {config['service_name']}")
    print(f"Port: {config['port']}")
    print(f"Log Level: {config['log_level']}")
    print(f"JWT Private Key: {'*' * 40}... (loaded from secrets)")
    print(f"OAuth Client Secret: {'*' * 20}... (loaded from secrets)")
    
    return config


def schema_based_example():
    """Example using schema JSON file."""
    
    # Schema file content (documents/schemas/configs/auth.json):
    # {
    #   "service_name": "auth",
    #   "fields": {
    #     "port": {
    #       "type": "int",
    #       "source": "env",
    #       "env_var": "PORT",
    #       "default": 8000
    #     },
    #     "jwt_private_key": {
    #       "type": "string",
    #       "source": "secret",
    #       "secret_name": "jwt_private_key",
    #       "required": true,
    #       "description": "RSA private key for JWT signing"
    #     }
    #   }
    # }
    
    # Load schema from file
    schema = ConfigSchema.from_json_file("documents/schemas/configs/auth.json")
    
    # Create providers
    secrets = create_secret_provider("local", base_path="/run/secrets")
    secret_config = SecretConfigProvider(secret_provider=secrets)
    env_config = EnvConfigProvider()
    
    # Load config
    loader = SchemaConfigLoader(
        schema=schema,
        env_provider=env_config,
        secret_provider=secret_config,
    )
    
    config = loader.load()
    return config


def docker_compose_example():
    """Example Docker Compose configuration for secret mounting.
    
    docker-compose.yml:
    
    ```yaml
    services:
      auth:
        build: ./auth
        volumes:
          - ./secrets:/run/secrets:ro  # Mount secrets read-only
        environment:
          SERVICE_NAME: auth-service
          PORT: 8000
          LOG_LEVEL: INFO
          SECRETS_BASE_PATH: /run/secrets
    ```
    
    Secrets directory structure:
    
    ```
    secrets/
    ├── jwt_private_key          # PEM-encoded RSA private key
    ├── jwt_public_key           # PEM-encoded RSA public key
    └── github_oauth_client_secret
    ```
    
    Service code:
    
    ```python
    from copilot_secrets import create_secret_provider
    from copilot_config import SecretConfigProvider, load_typed_config
    
    # Initialize secret provider
    secrets = create_secret_provider("local", base_path="/run/secrets")
    secret_config = SecretConfigProvider(secret_provider=secrets)
    
    # Load config with schema
    config = load_typed_config("auth", secret_provider=secret_config)
    
    # Access config
    print(f"JWT key loaded: {len(config['jwt_private_key'])} bytes")
    ```
    """
    pass


if __name__ == "__main__":
    # Note: This example requires actual secret files to run
    # Set up test secrets first:
    #   mkdir -p /tmp/test-secrets
    #   echo "test-jwt-key" > /tmp/test-secrets/jwt_private_key
    #   echo "test-public-key" > /tmp/test-secrets/jwt_public_key
    #   echo "test-client-secret" > /tmp/test-secrets/github_oauth_client_secret
    #   export SECRETS_BASE_PATH=/tmp/test-secrets
    
    try:
        config = main()
        print("\n✅ Configuration loaded successfully!")
    except Exception as e:
        print(f"\n❌ Error loading configuration: {e}")
        print("\nMake sure secret files exist in SECRETS_BASE_PATH")
