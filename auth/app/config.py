# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service configuration.

Uses schema-driven typed configuration (generated dataclasses) via copilot_config.
"""

import logging

from copilot_config.runtime_loader import get_config
from copilot_config.generated.services.auth import ServiceConfig_Auth

logger = logging.getLogger(__name__)


def load_auth_config() -> ServiceConfig_Auth:
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
        >>> print(config.service_settings.issuer)
        'http://localhost:8090'
        >>> print(config.service_settings.jwt_algorithm)
        'RS256'
    """
    config = get_config("auth")
    logger.info("Auth configuration loaded successfully")
    return config
