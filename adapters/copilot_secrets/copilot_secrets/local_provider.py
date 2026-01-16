# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local filesystem secret provider."""

import logging
from pathlib import Path

from copilot_config.generated.adapters.secret_provider import DriverConfig_SecretProvider_Local

from .exceptions import SecretNotFoundError, SecretProviderError
from .provider import SecretProvider

logger = logging.getLogger("copilot_secrets.local")


class LocalFileSecretProvider(SecretProvider):
    """Secret provider that reads secrets from local filesystem.

    Secrets are stored as individual files in a base directory. Each file
    contains one secret, with the filename serving as the secret name.

    This provider is suitable for:
    - Docker volume-mounted secrets
    - Kubernetes mounted secrets
    - Local development with file-based secrets

    Example:
        >>> provider = LocalFileSecretProvider(base_path="/run/secrets")
        >>> jwt_key = provider.get_secret("jwt_private_key")
        >>> # Reads from /run/secrets/jwt_private_key

    Attributes:
        base_path: Directory containing secret files
    """

    def __init__(self, base_path: str):
        """Initialize the local file secret provider.

        Args:
            base_path: Base directory containing secret files

        Raises:
            SecretProviderError: If base_path does not exist or is not a directory
        """
        self.base_path = Path(base_path)

        if not self.base_path.exists():
            raise SecretProviderError("Secret base path does not exist")

        if not self.base_path.is_dir():
            raise SecretProviderError("Secret base path is not a directory")

        logger.info("Initialized local secret provider")

    @classmethod
    def from_config(
        cls,
        driver_config: DriverConfig_SecretProvider_Local,
    ) -> "LocalFileSecretProvider":
        """Create LocalFileSecretProvider from driver_config.

        Args:
            driver_config: DriverConfig instance with base_path attribute.
                          Value must be provided (no default).

        Returns:
            LocalFileSecretProvider instance

        Raises:
            AttributeError: If base_path attribute is missing
        """
        return cls(base_path=driver_config.base_path)

    def _get_secret_path(self, key_name: str) -> Path:
        """Get the resolved path for a secret, validating against path traversal.

        Args:
            key_name: Name of the secret

        Returns:
            Resolved path to the secret file

        Raises:
            SecretProviderError: If path traversal is attempted
        """
        potential_path = (self.base_path / key_name).resolve()
        base_resolved = self.base_path.resolve()

        # Ensure the resolved path is within the base directory
        try:
            potential_path.relative_to(base_resolved)
        except ValueError as e:
            raise SecretProviderError(
                f"Invalid secret name (path traversal detected): {key_name}"
            ) from e

        return potential_path

    def get_secret(self, key_name: str, version: str | None = None) -> str:
        """Retrieve a secret by name.

        Args:
            key_name: Name of the secret (filename in base_path)
            version: Ignored for local filesystem provider

        Returns:
            Secret value as a string (whitespace stripped)

        Raises:
            SecretNotFoundError: If the secret file does not exist
            SecretProviderError: If reading the file fails
        """
        secret_path = self._get_secret_path(key_name)

        if not secret_path.exists():
            raise SecretNotFoundError(f"Secret not found: {key_name}")

        if not secret_path.is_file():
            raise SecretProviderError(f"Secret path is not a file: {key_name}")

        try:
            with open(secret_path, encoding="utf-8") as f:
                content = f.read().strip()
            return content

        except OSError as e:
            raise SecretProviderError(f"Failed to read secret {key_name}: {e}") from e

    def get_secret_bytes(self, key_name: str, version: str | None = None) -> bytes:
        """Retrieve a secret as raw bytes.

        Args:
            key_name: Name of the secret (filename in base_path)
            version: Ignored for local filesystem provider

        Returns:
            Secret value as bytes

        Raises:
            SecretNotFoundError: If the secret file does not exist
            SecretProviderError: If reading the file fails
        """
        secret_path = self._get_secret_path(key_name)

        if not secret_path.exists():
            raise SecretNotFoundError(f"Secret not found: {key_name}")

        if not secret_path.is_file():
            raise SecretProviderError(f"Secret path is not a file: {key_name}")

        try:
            with open(secret_path, "rb") as f:
                content = f.read()
            return content

        except OSError as e:
            raise SecretProviderError(f"Failed to read secret {key_name}: {e}") from e

    def secret_exists(self, key_name: str) -> bool:
        """Check if a secret exists.

        Args:
            key_name: Name of the secret

        Returns:
            True if secret file exists and is readable, False otherwise
        """
        try:
            secret_path = self._get_secret_path(key_name)
            return secret_path.is_file()
        except SecretProviderError:
            return False
