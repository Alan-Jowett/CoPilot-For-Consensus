# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating secret providers."""

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.secret_provider import AdapterConfig_SecretProvider

from .azurekeyvault_provider import AzureKeyVaultProvider
from .local_provider import LocalFileSecretProvider
from .provider import SecretProvider


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
            "local": LocalFileSecretProvider.from_config,
            "azure_key_vault": AzureKeyVaultProvider.from_config,
        },
    )
