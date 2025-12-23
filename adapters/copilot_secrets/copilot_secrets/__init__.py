# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Secret management adapter for accessing API keys, JWT keys, and other sensitive data.

This adapter provides a unified interface for retrieving secrets from various storage
backends including local file systems, Docker volumes, and cloud secret stores.

Example:
    >>> from copilot_secrets import create_secret_provider, LocalFileSecretProvider
    >>> provider = create_secret_provider("local", base_path="/app/secrets")
    >>> jwt_key = provider.get_secret("jwt_private_key")
"""

from .exceptions import SecretError, SecretNotFoundError, SecretProviderError
from .provider import SecretProvider
from .local_provider import LocalFileSecretProvider
from .azurekeyvault_provider import AzureKeyVaultProvider
from .factory import create_secret_provider

__all__ = [
    "SecretProvider",
    "LocalFileSecretProvider",
    "AzureKeyVaultProvider",
    "create_secret_provider",
    "SecretError",
    "SecretNotFoundError",
    "SecretProviderError",
]

__version__ = "0.1.0"
