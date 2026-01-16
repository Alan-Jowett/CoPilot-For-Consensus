# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Secret management adapter for accessing API keys, JWT keys, and other sensitive data.

This adapter provides a unified interface for retrieving secrets from various storage
backends including local file systems, Docker volumes, and cloud secret stores.

Example:
    >>> from copilot_secrets import create_secret_provider
    >>> from copilot_config.generated.adapters.secret_provider import (
    ...     AdapterConfig_SecretProvider,
    ...     DriverConfig_SecretProvider_Local,
    ... )
    >>> provider = create_secret_provider(
    ...     AdapterConfig_SecretProvider(
    ...         secret_provider_type="local",
    ...         driver=DriverConfig_SecretProvider_Local(base_path="/app/secrets"),
    ...     )
    ... )
    >>> jwt_key = provider.get_secret("jwt_private_key")
"""

from .exceptions import SecretError, SecretNotFoundError, SecretProviderError
from .factory import create_secret_provider

__all__ = [
    "__version__",
    "create_secret_provider",
    "SecretError",
    "SecretNotFoundError",
    "SecretProviderError",
]

__version__ = "0.1.0"
