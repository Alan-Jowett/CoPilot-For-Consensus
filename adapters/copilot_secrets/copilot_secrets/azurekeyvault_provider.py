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
            from azure.core.exceptions import ClientAuthenticationError
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as e:
            raise SecretProviderError(
                "Azure SDK not installed. Install with: pip install copilot-secrets[azure]"
            ) from e

        # Determine vault URL
        self.vault_url = self._determine_vault_url(vault_url, vault_name)

        # Initialize Azure credentials
        try:
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            logger.info(f"Initialized Azure Key Vault provider for {self.vault_url}")
        except ClientAuthenticationError as e:
            raise SecretProviderError(f"Failed to authenticate with Azure Key Vault: {e}") from e
        except Exception as e:
            raise SecretProviderError(f"Failed to initialize Azure Key Vault client: {e}") from e

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

    def get_secret(self, secret_name: str, version: str | None = None) -> str:
        """Retrieve a secret by name from Azure Key Vault.

        Args:
            secret_name: Name of the secret in Key Vault
            version: Optional version identifier for the secret
                    If not provided, retrieves the latest version

        Returns:
            Secret value as a string

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        try:
            from azure.core.exceptions import ResourceNotFoundError

            if version:
                secret = self.client.get_secret(secret_name, version=version)
            else:
                secret = self.client.get_secret(secret_name)

            if secret.value is None:
                raise SecretNotFoundError(f"Secret '{secret_name}' has no value")

            return secret.value

        except SecretNotFoundError:
            # Re-raise SecretNotFoundError without wrapping
            raise
        except ResourceNotFoundError as e:
            raise SecretNotFoundError(f"Secret not found: {secret_name}") from e
        except Exception as e:
            raise SecretProviderError(f"Failed to retrieve secret '{secret_name}': {e}") from e

    def get_secret_bytes(self, secret_name: str, version: str | None = None) -> bytes:
        """Retrieve a secret as raw bytes from Azure Key Vault.

        Azure Key Vault stores secrets as strings, so this method retrieves
        the secret as a string and encodes it to UTF-8 bytes.

        Args:
            secret_name: Name of the secret in Key Vault
            version: Optional version identifier for the secret

        Returns:
            Secret value as bytes (UTF-8 encoded)

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretProviderError: If retrieval fails
        """
        secret_str = self.get_secret(secret_name, version=version)
        return secret_str.encode("utf-8")

    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists in Azure Key Vault.

        Args:
            secret_name: Name of the secret to check

        Returns:
            True if secret exists and is enabled, False otherwise
        """
        try:
            from azure.core.exceptions import ResourceNotFoundError

            # Use get_secret_properties to check existence without retrieving value
            props = self.client.get_secret(secret_name)
            return props is not None and props.properties.enabled

        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.warning(f"Error checking if secret '{secret_name}' exists: {e}")
            return False
