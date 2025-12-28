# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service configuration.

Uses copilot_config adapter with TypedConfig for schema-driven configuration.
Secrets are automatically integrated based on schema metadata.
"""

import tempfile
from pathlib import Path

from copilot_config import load_typed_config
from copilot_logging import create_logger

logger = create_logger(logger_type="stdout", level="INFO", name="auth.config")


def load_auth_config():
    """Load auth service configuration from environment and secrets.

    Uses copilot_config with schema-driven configuration loading.
    Secrets integration is handled transparently by load_typed_config
    based on configuration in docs/schemas/configs/auth.json.

    Returns:
        TypedConfig instance with validated configuration

    Example:
        >>> config = load_auth_config()
        >>> print(config.issuer)
        'http://localhost:8090'
        >>> print(config.jwt_algorithm)
        'RS256'
    """
    config = load_typed_config("auth")
    logger.info("Auth configuration loaded successfully")

    # Handle JWT key file setup for RS256
    # JWTManager needs file paths, so we write secrets to temp files
    if config.jwt_algorithm == "RS256":
        if hasattr(config, 'jwt_private_key') and config.jwt_private_key:
            # Write secrets to temp files
            temp_dir = Path(tempfile.gettempdir()) / "auth_keys"
            temp_dir.mkdir(parents=True, exist_ok=True)

            private_key_path = temp_dir / "jwt_private.pem"
            public_key_path = temp_dir / "jwt_public.pem"

            private_key_path.write_text(config.jwt_private_key)
            if hasattr(config, 'jwt_public_key') and config.jwt_public_key:
                public_key_path.write_text(config.jwt_public_key)

    return config
