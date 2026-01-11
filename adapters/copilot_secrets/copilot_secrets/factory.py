# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating secret providers."""

import logging

from copilot_config import DriverConfig

from .azurekeyvault_provider import AzureKeyVaultProvider
from .exceptions import SecretProviderError
from .local_provider import LocalFileSecretProvider
from .provider import SecretProvider

logger = logging.getLogger(__name__)


def create_secret_provider(
    driver_name: str,
    driver_config: DriverConfig
) -> SecretProvider:
    """Create a secret provider based on driver type and configuration.

    This factory requires a DriverConfig object to ensure consistent configuration
    handling throughout the codebase. Configuration validation and defaults are
    applied by the DriverConfig object before being passed to this factory.

    Args:
        driver_name: Type of provider to create ("local", "azure", "azurekeyvault")
        driver_config: DriverConfig instance with provider-specific attributes:
                      - local: base_path (optional)
                      - azure/azurekeyvault: vault_url or vault_name (at least one required)

    Returns:
        SecretProvider instance

    Raises:
        SecretProviderError: If driver_name is unknown
        SecretProviderError: If driver_config is not a DriverConfig instance
        AttributeError: If required config attributes are missing
    """
    if not driver_name:
        raise SecretProviderError(
            "driver_name parameter is required. "
            "Must be one of: local, azure, azurekeyvault"
        )

    if not isinstance(driver_config, DriverConfig):
        raise SecretProviderError(
            f"driver_config must be a DriverConfig instance, "
            f"got {type(driver_config).__name__}"
        )

    driver_lower = driver_name.lower()

    if driver_lower == "local":
        return LocalFileSecretProvider.from_config(driver_config)

    elif driver_lower in ("azure", "azurekeyvault"):
        return AzureKeyVaultProvider.from_config(driver_config)

    else:
        raise SecretProviderError(
            f"Unknown secret provider driver: {driver_name}. "
            f"Supported drivers: local, azure, azurekeyvault"
        )
