# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Key Vault secret provider."""

import os

from copilot_logging import create_logger

from .exceptions import SecretNotFoundError, SecretProviderError
from .provider import SecretProvider

logger = create_logger(logger_type="stdout", level="INFO", name="copilot_secrets.azurekeyvault")


class AzureKeyVaultProvider(SecretProvider):
    """Secret provider that retrieves secrets from Azure Key Vault.

    This provider uses Azure SDK to access secrets from Azure Key Vault,
    supporting both managed identity (recommended for production) and
    environment-based credentials for local development.

    Authentication methods (in order of precedence):
    1. Managed Identity (DefaultAzureCredential handles this automatically)
    2. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
    3. Azure CLI credentials (for local development)

    Configuration via environment variables:
    - AZURE_KEY_VAULT_NAME: Name of the Key Vault (e.g., "my-vault")
    - AZURE_KEY_VAULT_URI: Full URI (e.g., "https://my-vault.vault.azure.net/")
      If both are provided, URI takes precedence.

    Example:
        >>> # Using vault name
        >>> os.environ["AZURE_KEY_VAULT_NAME"] = "my-production-vault"
        >>> provider = AzureKeyVaultProvider()
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
                      If not provided, uses AZURE_KEY_VAULT_URI environment variable
            vault_name: Name of the Key Vault (e.g., "my-vault")
                       If not provided, uses AZURE_KEY_VAULT_NAME environment variable
                       Ignored if vault_url is provided

        Raises:
            SecretProviderError: If vault URL cannot be determined or authentication fails
        """
        try:
            from azure.core.exceptions import AzureError, ClientAuthenticationError, ResourceNotFoundError
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as e:
            raise SecretProviderError(
                "Azure SDK dependencies for Azure Key Vault are not installed. "
                "For production, install with: pip install copilot-secrets[azure]. "
                "For local development from the adapter directory, use: pip install -e \".[azure]\""
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

    def close(self) -> None:
        """Release any resources held by this provider."""
        # Close the SecretClient first
        client = getattr(self, "client", None)
        if client is not None:
            try:
                close_method = getattr(client, "close", None)
                if callable(close_method):
                    close_method()
            except (AttributeError, TypeError, RuntimeError):
                # Suppress expected errors during cleanup
                pass

        # Then close the credential
        credential = getattr(self, "_credential", None)
        if credential is not None:
            try:
                close_method = getattr(credential, "close", None)
                if callable(close_method):
                    close_method()
            except (AttributeError, TypeError, RuntimeError):
                # Suppress expected errors during cleanup to avoid impacting application shutdown
                # AttributeError: close method not available
                # TypeError: close is not callable
                # RuntimeError: cleanup during shutdown
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
        """Determine the vault URL from parameters or environment variables.

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

        # Priority 2: AZURE_KEY_VAULT_URI environment variable
        env_uri = os.getenv("AZURE_KEY_VAULT_URI")
        if env_uri:
            return env_uri

        # Priority 3: vault_name parameter
        if vault_name:
            return f"https://{vault_name}.vault.azure.net/"

        # Priority 4: AZURE_KEY_VAULT_NAME environment variable
        env_name = os.getenv("AZURE_KEY_VAULT_NAME")
        if env_name:
            return f"https://{env_name}.vault.azure.net/"

        # No vault configuration found
        raise SecretProviderError(
            "Azure Key Vault URL not configured. Provide vault_url parameter or set "
            "AZURE_KEY_VAULT_URI or AZURE_KEY_VAULT_NAME environment variable"
        )

    def get_secret(self, key_name: str, version: str | None = None) -> str:
        """Retrieve a secret by name from Azure Key Vault.

        Args:
            key_name: Name of the secret in Key Vault
            version: Optional version identifier for the secret
                    If not provided, retrieves the latest version

        Returns:
            Secret value as a string

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        try:
            if version:
                secret = self.client.get_secret(key_name, version=version)
            else:
                secret = self.client.get_secret(key_name)

            if secret.value is None:
                raise SecretNotFoundError(f"Key '{key_name}' has no value")

            return secret.value

        except SecretNotFoundError:
            # Re-raise SecretNotFoundError without wrapping
            raise
        except ResourceNotFoundError as e:
            raise SecretNotFoundError(f"Key not found: {key_name}") from e
        except AzureError as e:
            # Handle Azure SDK network, service, and authentication errors
            raise SecretProviderError(f"Failed to retrieve key '{key_name}': {e}") from e
        except Exception as e:
            # Wrap any unexpected exceptions in SecretProviderError
            raise SecretProviderError(f"Failed to retrieve key '{key_name}': {e}") from e

    def get_secret_bytes(self, key_name: str, version: str | None = None) -> bytes:
        """Retrieve a secret as raw bytes from Azure Key Vault.

        Azure Key Vault stores secrets as strings, so this method retrieves
        the secret as a string and encodes it to UTF-8 bytes.

        Args:
            key_name: Name of the secret in Key Vault
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
            key_name: Name of the secret to check

        Returns:
            True if secret exists and is enabled, False otherwise
        """
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        try:
            # Fetch secret metadata; get_secret returns value + properties
            secret = self.client.get_secret(key_name)
            return bool(secret and getattr(secret.properties, "enabled", True))

        except ResourceNotFoundError:
            # Secret does not exist
            return False
        except AzureError as e:
            # Log Azure SDK network/service/authentication errors and return False for robustness
            # Note: Only logging the key name (metadata), not any sensitive value
            logger.warning(f"Error checking if key '{key_name}' exists in vault: {e}")
            return False
