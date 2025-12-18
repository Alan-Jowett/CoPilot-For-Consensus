# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating secret providers."""

from typing import Any, Dict

from .provider import SecretProvider
from .local_provider import LocalFileSecretProvider
from .exceptions import SecretProviderError


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
    providers: Dict[str, type] = {
        "local": LocalFileSecretProvider,
        # Future: "azure": AzureKeyVaultProvider,
        # Future: "aws": AWSSecretsManagerProvider,
        # Future: "gcp": GCPSecretManagerProvider,
    }
    
    if provider_type not in providers:
        raise SecretProviderError(
            f"Unknown provider type: {provider_type}. "
            f"Available: {', '.join(providers.keys())}"
        )
    
    provider_class = providers[provider_type]
    return provider_class(**kwargs)
