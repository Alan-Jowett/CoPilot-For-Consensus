# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Secret-backed configuration provider using copilot_secrets."""

from typing import Any, Optional

from .base import ConfigProvider


class SecretConfigProvider(ConfigProvider):
    """Configuration provider that reads from secret storage.

    This provider wraps a copilot_secrets.SecretProvider to provide
    configuration values from secret stores (local files, Azure Key Vault, etc.).

    Example:
        >>> from copilot_secrets import create_secret_provider
        >>> from copilot_config import SecretConfigProvider
        >>>
        >>> secrets = create_secret_provider("local", base_path="/run/secrets")
        >>> config = SecretConfigProvider(secret_provider=secrets)
        >>>
        >>> jwt_key = config.get("jwt_private_key")
        >>> api_key = config.get("api_key")
    """

    def __init__(self, secret_provider: Any):
        """Initialize the secret config provider.

        Args:
            secret_provider: Instance of copilot_secrets.SecretProvider
        """
        self._secret_provider = secret_provider

    def get(self, key: str, default: Any = None) -> Any:
        """Get a secret value as a string.

        Args:
            key: Secret name
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        try:
            return self._secret_provider.get_secret(key)
        except Exception:
            # Return default if secret doesn't exist or provider fails
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a secret value as a boolean.

        Converts string values to boolean:
        - "true", "1", "yes", "on" -> True
        - "false", "0", "no", "off" -> False

        Args:
            key: Secret name
            default: Default value if secret not found

        Returns:
            Boolean value or default
        """
        value = self.get(key)
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        value_lower = str(value).lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        if value_lower in ("false", "0", "no", "off"):
            return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a secret value as an integer.

        Args:
            key: Secret name
            default: Default value if secret not found or conversion fails

        Returns:
            Integer value or default
        """
        value = self.get(key)
        if value is None:
            return default

        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_bytes(self, key: str, default: Optional[bytes] = None) -> Optional[bytes]:
        """Get a secret value as raw bytes.

        Useful for binary secrets like encryption keys or certificates.

        Args:
            key: Secret name
            default: Default value if secret not found

        Returns:
            Secret bytes or default
        """
        try:
            return self._secret_provider.get_secret_bytes(key)
        except Exception:
            return default

    def secret_exists(self, key: str) -> bool:
        """Check if a secret exists.

        Args:
            key: Secret name

        Returns:
            True if secret exists, False otherwise
        """
        try:
            return self._secret_provider.secret_exists(key)
        except Exception:
            return False
