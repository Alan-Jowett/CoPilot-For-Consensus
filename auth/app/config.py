# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service configuration.

Uses copilot_config adapter with ServiceConfig for schema-driven configuration.
Secrets are integrated based on schema metadata.
"""

import logging
import tempfile
from pathlib import Path

from copilot_config import load_service_config

logger = logging.getLogger(__name__)


def load_auth_config():
    """Load auth service configuration from environment and secrets.

    Uses copilot_config with schema-driven configuration loading.
    Secrets integration is handled transparently by load_typed_config
    based on configuration in docs/schemas/configs/auth.json.

    In Azure Container Apps, secrets are accessed directly from Azure Key Vault
    via the schema-configured `secret_provider` adapter (driver: `azure_key_vault`).

    Returns:
        TypedConfig instance with validated configuration

    Example:
        >>> config = load_auth_config()
        >>> print(config.issuer)
        'http://localhost:8090'
        >>> print(config.jwt_algorithm)
        'RS256'
    """
    config = load_service_config("auth")
    logger.info("Auth configuration loaded successfully")

    # Handle JWT key file setup for RS256
    # JWTManager needs file paths, so we write secrets to temp files
    # In Azure, JWT keys are fetched from Key Vault via SDK using managed identity
    if config.jwt_algorithm == "RS256":
        if hasattr(config, 'jwt_private_key') and config.jwt_private_key:
            # Write secrets to temp files
            temp_dir = Path(tempfile.gettempdir()) / "auth_keys"
            temp_dir.mkdir(parents=True, exist_ok=True)

            private_key_path = temp_dir / "jwt_private.pem"
            public_key_path = temp_dir / "jwt_public.pem"

            private_key_path.write_text(config.jwt_private_key)
            logger.info("JWT private key loaded and written to temp file")

            if hasattr(config, 'jwt_public_key') and config.jwt_public_key:
                public_key_path.write_text(config.jwt_public_key)
                logger.info("JWT public key loaded and written to temp file")

    return config
