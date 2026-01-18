# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Key Vault secret provider."""

import logging

from copilot_config.generated.adapters.secret_provider import DriverConfig_SecretProvider_AzureKeyVault

from .exceptions import SecretNotFoundError, SecretProviderError
from .provider import SecretProvider

logger = logging.getLogger("copilot_secrets.azurekeyvault")


class AzureKeyVaultProvider(SecretProvider):
    """Secret provider that retrieves secrets from Azure Key Vault.

    This provider uses Azure SDK to access secrets from Azure Key Vault,
    supporting both managed identity (recommended for production) and
    environment-based credentials for local development.

    Authentication methods (in order of precedence):
    1. Managed Identity (DefaultAzureCredential handles this automatically)
    2. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
    3. Azure CLI credentials (for local development)

    Configuration via driver_config:
    - vault_url: Full Key Vault URL (e.g., "https://my-vault.vault.azure.net/")
    - vault_name: Key Vault name (e.g., "my-vault") - used to construct URL if vault_url not provided

    Example:
        >>> # Using vault name via from_config
        >>> provider = AzureKeyVaultProvider.from_config({"vault_name": "my-production-vault"})
        >>> api_key = provider.get_secret("api-key")

        >>> # Using full URI
        >>> provider = AzureKeyVaultProvider(vault_url="https://my-vault.vault.azure.net/")
        >>> jwt_key = provider.get_secret("jwt-private-key")

    Attributes:
        vault_url: Azure Key Vault URL
        client: SecretClient instance for accessing Key Vault
        _credential: DefaultAzureCredential instance used for authentication
    """

    def __init__(self, vault_url: str | None = None, vault_name: str | None = None):
        """Initialize the Azure Key Vault secret provider.

        Args:
            vault_url: Full Azure Key Vault URL (e.g., "https://my-vault.vault.azure.net/")
                      Required if vault_name is not provided
            vault_name: Name of the Key Vault (e.g., "my-vault")
                       Used to construct URL if vault_url is not provided
                       Ignored if vault_url is provided

        Raises:
            SecretProviderError: If neither vault_url nor vault_name is provided, or if authentication fails
        """
        try:
            from azure.core.exceptions import AzureError, ClientAuthenticationError
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as e:
            raise SecretProviderError(
                "Azure SDK dependencies for Azure Key Vault are not installed. "
                "For production, install with: pip install copilot-secrets[azure]. "
                'For local development from the adapter directory, use: pip install -e ".[azure]"'
            ) from e

        # Determine vault URL
        self.vault_url = self._determine_vault_url(vault_url, vault_name)

        # Initialize Azure credentials
        try:
            self._credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=self._credential)
            logger.info(f"Initialized Azure Key Vault provider for {self.vault_url}")
        except ClientAuthenticationError as e:
            raise SecretProviderError(f"Failed to authenticate with Azure Key Vault: {e}") from e
        except ValueError as e:
            raise SecretProviderError(f"Invalid Azure Key Vault URL '{self.vault_url}': {e}") from e
        except AzureError as e:
            # Catch other Azure SDK exceptions (network, service errors, etc.)
            raise SecretProviderError(f"Azure Key Vault client error: {e}") from e

    @classmethod
    def from_config(
        cls,
        driver_config: DriverConfig_SecretProvider_AzureKeyVault,
    ) -> "AzureKeyVaultProvider":
        """Create AzureKeyVaultProvider from driver_config.

        Args:
            driver_config: DriverConfig instance with vault_url or vault_name attribute.
                          At least one must be provided.

        Returns:
            AzureKeyVaultProvider instance

        Raises:
            AttributeError: If both vault_url and vault_name are missing
        """
        return cls(vault_url=driver_config.vault_url, vault_name=driver_config.vault_name)

    def close(self) -> None:
        """Close the Azure Key Vault client and credential connections.

        Attempts to close both the SecretClient and DefaultAzureCredential.
        Gracefully handles cases where close methods don't exist or raise exceptions.
        """
        # Close client if it has a close method
        if hasattr(self.client, "close"):
            try:
                self.client.close()
            except Exception:
                # Suppress exceptions during cleanup
                pass

        # Close credential if it has a close method
        if hasattr(self._credential, "close"):
            try:
                self._credential.close()
            except Exception:
                # Suppress exceptions during cleanup
                pass

    def __del__(self) -> None:
        """Best-effort cleanup of underlying Azure credential when garbage collected."""
        try:
            self.close()
        except (AttributeError, TypeError, RuntimeError):
            # Suppress expected errors during interpreter shutdown
            # Do not use logging here as logger may not be available
            pass

    def _determine_vault_url(self, vault_url: str | None, vault_name: str | None) -> str:
        """Determine the vault URL from parameters.

        Args:
            vault_url: Explicitly provided vault URL
            vault_name: Explicitly provided vault name

        Returns:
            Fully qualified vault URL

        Raises:
            SecretProviderError: If vault URL cannot be determined
        """
        # Priority 1: Explicitly provided vault_url
        if vault_url:
            return vault_url

        # Priority 2: vault_name parameter
        if vault_name:
            return f"https://{vault_name}.vault.azure.net/"

        # No vault configuration found
        raise SecretProviderError(
            "Azure Key Vault URL not configured. Provide vault_url or vault_name in driver_config."
        )

    @staticmethod
    def _normalize_secret_name(key_name: str) -> str:
        """Normalize secret name from snake_case to hyphenated format for Azure Key Vault.

        Azure Key Vault secret names can only contain alphanumeric characters and hyphens.
        This method transforms internal secret names (using underscores) to Key Vault-compatible
        names (using hyphens).

        Args:
            key_name: Secret name in snake_case format (e.g., "jwt_private_key")

        Returns:
            Secret name with hyphens (e.g., "jwt-private-key")

        Example:
            >>> AzureKeyVaultProvider._normalize_secret_name("jwt_private_key")
            'jwt-private-key'
            >>> AzureKeyVaultProvider._normalize_secret_name("mongodb_root_username")
            'mongodb-root-username'
        """
        return key_name.replace("_", "-")

    def get_secret(self, key_name: str, version: str | None = None) -> str:
        """Retrieve a secret by name from Azure Key Vault.

        Args:
            key_name: Name of the secret (e.g., "jwt_private_key" or "jwt-private-key")
                     Underscores are automatically converted to hyphens for Key Vault compatibility
            version: Optional version identifier for the secret
                    If not provided, retrieves the latest version

        Returns:
            Secret value as a string

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        # Normalize secret name for Azure Key Vault (convert underscores to hyphens)
        vault_key_name = self._normalize_secret_name(key_name)

        try:
            if version:
                secret = self.client.get_secret(vault_key_name, version=version)
            else:
                secret = self.client.get_secret(vault_key_name)

            if secret.value is None:
                raise SecretNotFoundError(f"Key '{key_name}' (vault name: '{vault_key_name}') has no value")

            return secret.value

        except SecretNotFoundError:
            # Re-raise SecretNotFoundError without wrapping
            raise
        except ResourceNotFoundError as e:
            raise SecretNotFoundError(f"Key not found: {key_name} (vault name: {vault_key_name})") from e
        except AzureError as e:
            # Handle Azure SDK network, service, and authentication errors
            raise SecretProviderError(
                f"Failed to retrieve key '{key_name}' (vault name: '{vault_key_name}'): {e}"
            ) from e
        except Exception as e:
            # Wrap any unexpected exceptions in SecretProviderError
            raise SecretProviderError(
                f"Failed to retrieve key '{key_name}' (vault name: '{vault_key_name}'): {e}"
            ) from e

    def get_secret_bytes(self, key_name: str, version: str | None = None) -> bytes:
        """Retrieve a secret as raw bytes from Azure Key Vault.

        Azure Key Vault stores secrets as strings, so this method retrieves
        the secret as a string and encodes it to UTF-8 bytes.

        Args:
            key_name: Name of the secret (e.g., "jwt_private_key" or "jwt-private-key")
                     Underscores are automatically converted to hyphens for Key Vault compatibility
            version: Optional version identifier for the secret

        Returns:
            Secret value as bytes (UTF-8 encoded)

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        secret_str = self.get_secret(key_name, version=version)
        return secret_str.encode("utf-8")

    def secret_exists(self, key_name: str) -> bool:
        """Check if a secret exists in Azure Key Vault.

        Args:
            key_name: Name of the secret to check (e.g., "jwt_private_key" or "jwt-private-key")
                     Underscores are automatically converted to hyphens for Key Vault compatibility

        Returns:
            True if secret exists and is enabled, False otherwise
        """
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        # Normalize secret name for Azure Key Vault (convert underscores to hyphens)
        vault_key_name = self._normalize_secret_name(key_name)

        try:
            # Fetch secret metadata; get_secret returns value + properties
            secret = self.client.get_secret(vault_key_name)
            return bool(secret and getattr(secret.properties, "enabled", True))

        except ResourceNotFoundError:
            # Secret does not exist
            return False
        except AzureError as e:
            # Log Azure SDK network/service/authentication errors and return False for robustness
            # Note: Only logging the key name (metadata), not any sensitive value
            logger.warning(f"Error checking if key '{key_name}' (vault name: '{vault_key_name}') exists in vault: {e}")
            return False
