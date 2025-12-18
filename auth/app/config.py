# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service configuration.

Uses copilot_config adapter with TypedConfig for schema-driven configuration.
"""

import os
from pathlib import Path
import tempfile

from copilot_config import load_typed_config, SecretConfigProvider, TypedConfig
from copilot_secrets import create_secret_provider


def load_auth_config() -> TypedConfig:
    """Load auth service configuration from environment and secrets.
    
    Uses copilot_config with schema-driven configuration loading.
    Secrets are loaded from SECRETS_BASE_PATH (default: /run/secrets).
    
    Configuration is accessed via attributes (config.issuer, config.jwt_algorithm, etc.)
    See documents/schemas/configs/auth.json for complete schema.
    
    Returns:
        TypedConfig instance with validated configuration
        
    Example:
        >>> config = load_auth_config()
        >>> print(config.issuer)
        'http://localhost:8090'
        >>> print(config.jwt_algorithm)
        'RS256'
    """
    # Create secret provider - factory reads provider type and config from environment
    secrets = create_secret_provider()
    secret_config = SecretConfigProvider(secret_provider=secrets)
    
    # Load configuration from schema
    schema_dir = os.getenv("SCHEMA_DIR")
    if not schema_dir:
        # Default to repository schemas directory
        repo_root = Path(__file__).parent.parent.parent
        schema_dir = str(repo_root / "documents" / "schemas" / "configs")
    
    config = load_typed_config(
        "auth",
        schema_dir=schema_dir,
        secret_provider=secret_config,
    )
    
    # Handle JWT key file setup for RS256
    # JWTManager needs file paths, so we write secrets to temp files
    if config.jwt_algorithm == "RS256":
        if hasattr(config, 'jwt_private_key') and config.jwt_private_key:
            # Write secrets to temp files
            temp_dir = Path(tempfile.gettempdir()) / "auth_keys"
            temp_dir.mkdir(exist_ok=True)
            
            private_key_path = temp_dir / "jwt_private.pem"
            public_key_path = temp_dir / "jwt_public.pem"
            
            private_key_path.write_text(config.jwt_private_key)
            if hasattr(config, 'jwt_public_key') and config.jwt_public_key:
                public_key_path.write_text(config.jwt_public_key)
            
            # Add paths as dynamic attributes (TypedConfig allows this for processing)
            object.__setattr__(config._config, '_jwt_private_key_path', str(private_key_path))
            object.__setattr__(config._config, '_jwt_public_key_path', str(public_key_path))
        else:
            # Fallback to default dev keys in config/ for local development
            base_path = Path(__file__).parent.parent / "config"
            object.__setattr__(config._config, '_jwt_private_key_path', str(base_path / "dev_jwt_private.pem"))
            object.__setattr__(config._config, '_jwt_public_key_path', str(base_path / "dev_jwt_public.pem"))
    
    return config
