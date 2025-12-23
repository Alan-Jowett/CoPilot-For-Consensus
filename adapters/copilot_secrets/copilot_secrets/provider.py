# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base secret provider interface."""

from abc import ABC, abstractmethod
from typing import Optional


class SecretProvider(ABC):
    """Abstract base class for secret providers.

    Implementations must provide methods to retrieve secrets from their
    respective storage backends (filesystem, cloud key vaults, etc.).
    """

    @abstractmethod
    def get_secret(self, key_name: str, version: Optional[str] = None) -> str:
        """Retrieve a secret by name.

        Args:
            key_name: Name/identifier of the secret
            version: Optional version identifier (for versioned secret stores)

        Returns:
            Secret value as a string

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        pass

    @abstractmethod
    def get_secret_bytes(self, key_name: str, version: Optional[str] = None) -> bytes:
        """Retrieve a secret as raw bytes.

        Useful for binary secrets like encryption keys or certificates.

        Args:
            key_name: Name/identifier of the secret
            version: Optional version identifier

        Returns:
            Secret value as bytes

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        pass

    @abstractmethod
    def secret_exists(self, key_name: str) -> bool:
        """Check if a secret exists.

        Args:
            key_name: Name/identifier of the secret

        Returns:
            True if secret exists, False otherwise
        """
        pass
