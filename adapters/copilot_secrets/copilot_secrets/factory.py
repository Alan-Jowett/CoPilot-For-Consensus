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


class _DictConfig:
    """Wrapper to allow attribute access on a dictionary or empty config."""

    def __init__(self, data: dict | None = None):
        """Initialize with optional dictionary data."""
        if data:
            self.__dict__.update(data)


def create_secret_provider(
    driver_name: str,
    driver_config: DriverConfig | dict | None = None
) -> SecretProvider:
    """Create a secret provider based on driver type and configuration.

    This factory accepts a DriverConfig object or a dictionary.

    Args:
        driver_name: Type of provider to create ("local", "azure", "azurekeyvault")
        driver_config: DriverConfig instance or dict with attributes:
                      - local: base_path (optional)
                      - azure/azurekeyvault: vault_url or vault_name (at least one required)

    Returns:
        SecretProvider instance

    Raises:
        SecretProviderError: If driver_name is unknown
        AttributeError: If required config attributes are missing
    """
    if not driver_name:
        raise SecretProviderError(
            "driver_name parameter is required. "
            "Must be one of: local, azure, azurekeyvault"
        )

    driver_lower = driver_name.lower()

    # Wrap dict in a config object that allows attribute access
    if isinstance(driver_config, dict):
        driver_config = _DictConfig(driver_config)
    elif driver_config is None:
        driver_config = _DictConfig()

    if driver_lower == "local":
        return LocalFileSecretProvider.from_config(driver_config)

    elif driver_lower in ("azure", "azurekeyvault"):
        return AzureKeyVaultProvider.from_config(driver_config)

    else:
        raise SecretProviderError(
            f"Unknown secret provider driver: {driver_name}. "
            f"Supported drivers: local, azure, azurekeyvault"
        )
