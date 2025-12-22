# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Key Vault secret provider."""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock Azure modules globally before any imports
mock_secret_client = MagicMock()
mock_default_credential = MagicMock()
mock_resource_not_found = type('ResourceNotFoundError', (Exception,), {})
mock_client_auth_error = type('ClientAuthenticationError', (Exception,), {})

sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock(SecretClient=mock_secret_client)
sys.modules['azure.identity'] = MagicMock(DefaultAzureCredential=mock_default_credential)
sys.modules['azure.core'] = MagicMock()
sys.modules['azure.core.exceptions'] = MagicMock(
    ResourceNotFoundError=mock_resource_not_found,
    ClientAuthenticationError=mock_client_auth_error
)

from copilot_secrets import (
    AzureKeyVaultProvider,
    SecretNotFoundError,
    SecretProviderError,
)


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    mock_secret_client.reset_mock()
    mock_default_credential.reset_mock()
    yield


class TestAzureKeyVaultProvider:
    """Test suite for AzureKeyVaultProvider."""

    def test_init_with_vault_url(self):
        """Test initialization with explicit vault URL."""
        vault_url = "https://test-vault.vault.azure.net/"

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.vault_url == vault_url
        mock_default_credential.assert_called()
        mock_secret_client.assert_called()

    def test_init_with_vault_name(self):
        """Test initialization with vault name."""
        vault_name = "test-vault"
        expected_url = f"https://{vault_name}.vault.azure.net/"

        provider = AzureKeyVaultProvider(vault_name=vault_name)

        assert provider.vault_url == expected_url

    def test_init_with_env_var_uri(self):
        """Test initialization using AZURE_KEY_VAULT_URI environment variable."""
        vault_url = "https://env-vault.vault.azure.net/"

        with patch.dict(os.environ, {"AZURE_KEY_VAULT_URI": vault_url}):
            provider = AzureKeyVaultProvider()
            assert provider.vault_url == vault_url

    def test_init_with_env_var_name(self):
        """Test initialization using AZURE_KEY_VAULT_NAME environment variable."""
        vault_name = "env-vault"
        expected_url = f"https://{vault_name}.vault.azure.net/"

        with patch.dict(os.environ, {"AZURE_KEY_VAULT_NAME": vault_name}, clear=True):
            provider = AzureKeyVaultProvider()
            assert provider.vault_url == expected_url

    def test_init_without_vault_config(self):
        """Test initialization without any vault configuration raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SecretProviderError, match="Azure Key Vault URL not configured"):
                AzureKeyVaultProvider()

    def test_init_prioritizes_vault_url_over_name(self):
        """Test that explicit vault_url takes priority over vault_name."""
        vault_url = "https://priority-vault.vault.azure.net/"
        vault_name = "ignored-vault"

        provider = AzureKeyVaultProvider(vault_url=vault_url, vault_name=vault_name)

        assert provider.vault_url == vault_url
        assert "ignored" not in provider.vault_url

    def test_init_prioritizes_vault_url_over_env(self):
        """Test that explicit vault_url takes priority over environment variables."""
        vault_url = "https://explicit-vault.vault.azure.net/"
        env_url = "https://env-vault.vault.azure.net/"

        with patch.dict(os.environ, {"AZURE_KEY_VAULT_URI": env_url}):
            provider = AzureKeyVaultProvider(vault_url=vault_url)
            assert provider.vault_url == vault_url

    def test_get_secret_success(self):
        """Test successful secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "my-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key")

        assert result == "my-secret-value"

    def test_get_secret_with_version(self):
        """Test secret retrieval with version."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "versioned-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key", version="v2")

        assert result == "versioned-secret-value"
        mock_client.get_secret.assert_called_once_with("api-key", version="v2")

    def test_get_secret_not_found(self):
        """Test retrieval of non-existent secret."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client
        mock_client.get_secret.side_effect = mock_resource_not_found("Secret not found")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretNotFoundError, match="Secret not found: missing-key"):
            provider.get_secret("missing-key")

    def test_get_secret_with_null_value(self):
        """Test retrieval of secret with null value."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = None
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretNotFoundError, match="has no value"):
            provider.get_secret("null-secret")

    def test_get_secret_provider_error(self):
        """Test handling of provider errors during retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client
        mock_client.get_secret.side_effect = Exception("Network error")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretProviderError, match="Failed to retrieve secret"):
            provider.get_secret("api-key")

    def test_get_secret_bytes_success(self):
        """Test successful binary secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "binary-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("binary-key")

        assert result == b"binary-secret-value"
        assert isinstance(result, bytes)

    def test_get_secret_bytes_utf8_encoding(self):
        """Test that get_secret_bytes properly encodes UTF-8."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "café"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("utf8-key")

        assert result == "café".encode()

    def test_secret_exists_returns_true(self):
        """Test secret_exists returns True for existing enabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_props = Mock()
        mock_props.enabled = True
        mock_client.get_secret_properties.return_value = mock_props

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("existing-key") is True

    def test_secret_exists_returns_false_for_disabled(self):
        """Test secret_exists returns False for disabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        mock_props = Mock()
        mock_props.enabled = False
        mock_client.get_secret_properties.return_value = mock_props

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("disabled-key") is False

    def test_secret_exists_returns_false_for_not_found(self):
        """Test secret_exists returns False for non-existent secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client
        mock_client.get_secret_properties.side_effect = mock_resource_not_found("Not found")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("missing-key") is False

    def test_secret_exists_handles_errors_gracefully(self):
        """Test secret_exists returns False on unexpected errors."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client
        mock_client.get_secret_properties.side_effect = Exception("Network error")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("error-key") is False

    def test_authentication_error(self):
        """Test handling of authentication errors."""
        mock_default_credential.side_effect = mock_client_auth_error("Auth failed")

        with pytest.raises(SecretProviderError, match="Failed to authenticate"):
            AzureKeyVaultProvider(vault_url="https://test.vault.azure.net/")

        # Reset for other tests
        mock_default_credential.side_effect = None

    def test_missing_azure_sdk_dependencies(self):
        """Test that appropriate error is raised when Azure SDK is not installed."""
        # Save current azure modules
        saved_modules = {}
        azure_keys = [k for k in sys.modules.keys() if k.startswith('azure')]
        for key in azure_keys:
            saved_modules[key] = sys.modules.pop(key)
        
        try:
            # Make imports fail by removing azure from sys.modules
            # Import the module fresh which will trigger the ImportError
            with patch.dict(sys.modules, {k: None for k in azure_keys}):
                # Force reimport by removing cached module
                if 'copilot_secrets.azurekeyvault_provider' in sys.modules:
                    del sys.modules['copilot_secrets.azurekeyvault_provider']
                
                # This should raise SecretProviderError with installation instructions
                from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider as AKVReload
                
                with pytest.raises(SecretProviderError, match="Azure SDK dependencies.*not installed"):
                    AKVReload(vault_url="https://test.vault.azure.net/")
        finally:
            # Restore azure modules
            sys.modules.update(saved_modules)

    def test_close_method(self):
        """Test that close method properly closes both client and credential."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        mock_secret_client.return_value = mock_client
        mock_default_credential.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        # Add close methods to mocks
        mock_client.close = Mock()
        mock_credential.close = Mock()
        
        # Call close
        provider.close()
        
        # Verify both close methods were called
        mock_client.close.assert_called_once()
        mock_credential.close.assert_called_once()

    def test_close_method_handles_missing_close(self):
        """Test that close method handles objects without close method."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        mock_secret_client.return_value = mock_client
        mock_default_credential.return_value = mock_credential

        # Remove close method from mocks
        del mock_client.close
        del mock_credential.close

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        # Should not raise any exception
        provider.close()

    def test_close_method_handles_exceptions(self):
        """Test that close method suppresses exceptions during cleanup."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        mock_secret_client.return_value = mock_client
        mock_default_credential.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        # Make close methods raise exceptions
        mock_client.close = Mock(side_effect=RuntimeError("Close failed"))
        mock_credential.close = Mock(side_effect=RuntimeError("Close failed"))
        
        # Should not raise any exception
        provider.close()

    def test_del_method(self):
        """Test that __del__ method calls close without raising exceptions."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        mock_secret_client.return_value = mock_client
        mock_default_credential.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        # Add close methods to mocks
        mock_client.close = Mock()
        mock_credential.close = Mock()
        
        # Use del to trigger __del__ naturally instead of calling it explicitly
        del provider
        
        # Verify close was attempted
        mock_client.close.assert_called_once()
        mock_credential.close.assert_called_once()

    def test_del_method_handles_exceptions(self):
        """Test that __del__ method suppresses exceptions during cleanup."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        mock_secret_client.return_value = mock_client
        mock_default_credential.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        # Make close raise an exception
        mock_client.close = Mock(side_effect=RuntimeError("Close failed"))
        mock_credential.close = Mock(side_effect=RuntimeError("Close failed"))
        
        # Should not raise any exception when deleted
        del provider


class TestAzureKeyVaultProviderIntegration:
    """Integration-style tests with more realistic mocking."""

    def test_complete_workflow(self):
        """Test complete workflow of checking, retrieving, and reading secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_secret_client.return_value = mock_client

        # Setup mock responses for get_secret
        def get_secret_side_effect(name, version=None):
            secrets = {
                "api-key": Mock(value="key123"),
                "jwt-private-key": Mock(
                    value="-----BEGIN PRIVATE KEY-----\ndata\n-----END PRIVATE KEY-----"
                ),
            }
            if name in secrets:
                return secrets[name]
            raise mock_resource_not_found(f"Secret {name} not found")

        # Setup mock responses for get_secret_properties
        def get_secret_properties_side_effect(name):
            properties = {
                "api-key": Mock(enabled=True),
                "jwt-private-key": Mock(enabled=True),
            }
            if name in properties:
                return properties[name]
            raise mock_resource_not_found(f"Secret {name} not found")

        mock_client.get_secret.side_effect = get_secret_side_effect
        mock_client.get_secret_properties.side_effect = get_secret_properties_side_effect

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Check existence
        assert provider.secret_exists("api-key") is True
        assert provider.secret_exists("missing-key") is False

        # Retrieve secrets
        api_key = provider.get_secret("api-key")
        assert api_key == "key123"

        jwt_key = provider.get_secret("jwt-private-key")
        assert "BEGIN PRIVATE KEY" in jwt_key

        # Retrieve as bytes
        api_key_bytes = provider.get_secret_bytes("api-key")
        assert api_key_bytes == b"key123"
