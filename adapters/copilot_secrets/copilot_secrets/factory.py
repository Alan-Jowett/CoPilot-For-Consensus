# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating secret providers."""

from typing import Any, cast

from .azurekeyvault_provider import AzureKeyVaultProvider
from .exceptions import SecretProviderError
from .local_provider import LocalFileSecretProvider
from .provider import SecretProvider


def create_secret_provider(provider_type: str, **kwargs: Any) -> SecretProvider:
    """Factory function to create secret providers.

    Args:
        provider_type: Type of provider to create ("local", "azure", etc.)
        **kwargs: Provider-specific configuration

    Returns:
        SecretProvider instance

    Raises:
        SecretProviderError: If provider_type is unknown

    Example:
        >>> provider = create_secret_provider("local", base_path="/app/secrets")
    """
    providers: dict[str, type] = {
        "local": LocalFileSecretProvider,
        "azure": AzureKeyVaultProvider,
        # Future: "aws": AWSSecretsManagerProvider,
        # Future: "gcp": GCPSecretManagerProvider,
    }

    if provider_type not in providers:
        raise SecretProviderError(
            f"Unknown provider type: {provider_type}. "
            f"Available: {', '.join(providers.keys())}"
        )

    provider_class = providers[provider_type]
    return cast(SecretProvider, provider_class(**kwargs))
