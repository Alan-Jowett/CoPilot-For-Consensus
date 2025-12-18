# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for secret-backed configuration."""

import tempfile
import json
import os
from pathlib import Path

import pytest

from copilot_config import (
    SchemaConfigLoader,
    ConfigSchema,
    SecretConfigProvider,
    EnvConfigProvider,
)


class FakeSecretProvider:
    """Fake secret provider for testing."""
    
    def __init__(self, secrets: dict):
        self._secrets = secrets
    
    def get_secret(self, name: str) -> str:
        if name not in self._secrets:
            raise KeyError(f"Secret not found: {name}")
        return self._secrets[name]
    
    def get_secret_bytes(self, name: str) -> bytes:
        return self.get_secret(name).encode()
    
    def secret_exists(self, name: str) -> bool:
        return name in self._secrets


class TestSecretIntegration:
    """Integration tests for secret configuration."""
    
    def test_mixed_config_sources(self):
        """Test configuration from both env vars and secrets."""
        # Create fake secret provider
        fake_secrets = FakeSecretProvider({
            "jwt_private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...",
            "api_key": "secret-api-key-12345",
        })
        
        # Create providers
        secret_provider = SecretConfigProvider(secret_provider=fake_secrets)
        env_provider = EnvConfigProvider(environ={
            "SERVICE_NAME": "test-service",
            "PORT": "8080",
            "DEBUG": "true",
        })
        
        # Create schema
        schema = ConfigSchema(
            service_name="test-service",
            fields={
                "service_name": ConfigSchema._parse_field_spec("service_name", {
                    "type": "string",
                    "source": "env",
                    "env_var": "SERVICE_NAME",
                    "required": True,
                }),
                "port": ConfigSchema._parse_field_spec("port", {
                    "type": "int",
                    "source": "env",
                    "env_var": "PORT",
                    "default": 3000,
                }),
                "debug": ConfigSchema._parse_field_spec("debug", {
                    "type": "bool",
                    "source": "env",
                    "env_var": "DEBUG",
                    "default": False,
                }),
                "jwt_private_key": ConfigSchema._parse_field_spec("jwt_private_key", {
                    "type": "string",
                    "source": "secret",
                    "secret_name": "jwt_private_key",
                    "required": True,
                }),
                "api_key": ConfigSchema._parse_field_spec("api_key", {
                    "type": "string",
                    "source": "secret",
                    "secret_name": "api_key",
                    "required": True,
                }),
            }
        )
        
        # Load configuration
        loader = SchemaConfigLoader(
            schema=schema,
            env_provider=env_provider,
            secret_provider=secret_provider,
        )
        
        config = loader.load()
        
        # Verify configuration
        assert config["service_name"] == "test-service"
        assert config["port"] == 8080
        assert config["debug"] is True
        assert config["jwt_private_key"] == "-----BEGIN PRIVATE KEY-----\nMIIE..."
        assert config["api_key"] == "secret-api-key-12345"
    
    def test_optional_secret_with_fallback(self):
        """Test optional secret with default value."""
        fake_secrets = FakeSecretProvider({
            "required_key": "value",
        })
        
        secret_provider = SecretConfigProvider(secret_provider=fake_secrets)
        
        schema = ConfigSchema(
            service_name="test",
            fields={
                "required_key": ConfigSchema._parse_field_spec("required_key", {
                    "type": "string",
                    "source": "secret",
                    "required": True,
                }),
                "optional_key": ConfigSchema._parse_field_spec("optional_key", {
                    "type": "string",
                    "source": "secret",
                    "required": False,
                    "default": "default-value",
                }),
            }
        )
        
        loader = SchemaConfigLoader(schema=schema, secret_provider=secret_provider)
        config = loader.load()
        
        assert config["required_key"] == "value"
        assert config["optional_key"] == "default-value"
    
    def test_schema_with_secret_source(self):
        """Test loading schema that specifies secret source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create schema file
            schema_path = Path(tmpdir) / "auth.json"
            schema_data = {
                "service_name": "auth",
                "fields": {
                    "port": {
                        "type": "int",
                        "source": "env",
                        "env_var": "PORT",
                        "default": 8000,
                    },
                    "jwt_private_key": {
                        "type": "string",
                        "source": "secret",
                        "secret_name": "jwt_private_key",
                        "required": True,
                        "description": "RSA private key for JWT signing",
                    },
                    "oidc_client_secret": {
                        "type": "string",
                        "source": "secret",
                        "secret_name": "oidc_client_secret",
                        "required": True,
                        "description": "OAuth client secret",
                    },
                }
            }
            
            with open(schema_path, "w") as f:
                json.dump(schema_data, f)
            
            # Load schema from file
            schema = ConfigSchema.from_json_file(str(schema_path))
            
            # Verify schema parsing
            assert schema.service_name == "auth"
            assert schema.fields["jwt_private_key"].source == "secret"
            assert schema.fields["jwt_private_key"].secret_name == "jwt_private_key"
            assert schema.fields["jwt_private_key"].required is True
            
            # Load config with providers
            fake_secrets = FakeSecretProvider({
                "jwt_private_key": "RSA-KEY-DATA",
                "oidc_client_secret": "CLIENT-SECRET",
            })
            
            secret_provider = SecretConfigProvider(secret_provider=fake_secrets)
            env_provider = EnvConfigProvider(environ={"PORT": "9000"})
            
            loader = SchemaConfigLoader(
                schema=schema,
                env_provider=env_provider,
                secret_provider=secret_provider,
            )
            
            config = loader.load()
            
            assert config["port"] == 9000
            assert config["jwt_private_key"] == "RSA-KEY-DATA"
            assert config["oidc_client_secret"] == "CLIENT-SECRET"
