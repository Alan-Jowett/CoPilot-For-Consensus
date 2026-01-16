# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating secret providers."""

from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_AzureKeyVault,
    DriverConfig_SecretProvider_Local,
)

from .azurekeyvault_provider import AzureKeyVaultProvider
from .local_provider import LocalFileSecretProvider
from .provider import SecretProvider

_DriverConfig: TypeAlias = DriverConfig_SecretProvider_Local | DriverConfig_SecretProvider_AzureKeyVault


def _build_local(config: _DriverConfig) -> SecretProvider:
    if not isinstance(config, DriverConfig_SecretProvider_Local):
        raise TypeError("driver config must be DriverConfig_SecretProvider_Local")
    return LocalFileSecretProvider.from_config(config)


def _build_azure_key_vault(config: _DriverConfig) -> SecretProvider:
    if not isinstance(config, DriverConfig_SecretProvider_AzureKeyVault):
        raise TypeError("driver config must be DriverConfig_SecretProvider_AzureKeyVault")
    return AzureKeyVaultProvider.from_config(config)


def create_secret_provider(
    config: AdapterConfig_SecretProvider,
) -> SecretProvider:
    """Create a secret provider based on driver type and configuration.

    Args:
        config: Typed AdapterConfig_SecretProvider instance.

    Returns:
        SecretProvider instance

    Raises:
        ValueError: If config is missing or driver type is unknown
        ValueError: If driver config is invalid against schema
    """
    return create_adapter(
        config,
        adapter_name="secret_provider",
        get_driver_type=lambda c: c.secret_provider_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "local": _build_local,
            "azure_key_vault": _build_azure_key_vault,
        },
    )
