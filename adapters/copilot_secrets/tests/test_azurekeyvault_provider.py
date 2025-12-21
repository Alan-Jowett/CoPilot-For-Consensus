# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Key Vault secret provider."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from copilot_secrets import (
    AzureKeyVaultProvider,
    SecretNotFoundError,
    SecretProviderError,
)


class TestAzureKeyVaultProvider:
    """Test suite for AzureKeyVaultProvider."""
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_with_vault_url(self, mock_credential, mock_client_class):
        """Test initialization with explicit vault URL."""
        vault_url = "https://test-vault.vault.azure.net/"
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        assert provider.vault_url == vault_url
        mock_credential.assert_called_once()
        mock_client_class.assert_called_once()
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_with_vault_name(self, mock_credential, mock_client_class):
        """Test initialization with vault name."""
        vault_name = "test-vault"
        expected_url = f"https://{vault_name}.vault.azure.net/"
        
        provider = AzureKeyVaultProvider(vault_name=vault_name)
        
        assert provider.vault_url == expected_url
        mock_credential.assert_called_once()
        mock_client_class.assert_called_once()
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_with_env_var_uri(self, mock_credential, mock_client_class):
        """Test initialization using AZURE_KEY_VAULT_URI environment variable."""
        vault_url = "https://env-vault.vault.azure.net/"
        
        with patch.dict(os.environ, {"AZURE_KEY_VAULT_URI": vault_url}):
            provider = AzureKeyVaultProvider()
            assert provider.vault_url == vault_url
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_with_env_var_name(self, mock_credential, mock_client_class):
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
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_prioritizes_vault_url_over_name(self, mock_credential, mock_client_class):
        """Test that explicit vault_url takes priority over vault_name."""
        vault_url = "https://priority-vault.vault.azure.net/"
        vault_name = "ignored-vault"
        
        provider = AzureKeyVaultProvider(vault_url=vault_url, vault_name=vault_name)
        
        assert provider.vault_url == vault_url
        assert "ignored" not in provider.vault_url
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_init_prioritizes_vault_url_over_env(self, mock_credential, mock_client_class):
        """Test that explicit vault_url takes priority over environment variables."""
        vault_url = "https://explicit-vault.vault.azure.net/"
        env_url = "https://env-vault.vault.azure.net/"
        
        with patch.dict(os.environ, {"AZURE_KEY_VAULT_URI": env_url}):
            provider = AzureKeyVaultProvider(vault_url=vault_url)
            assert provider.vault_url == vault_url
    
    def test_init_missing_azure_sdk(self):
        """Test initialization fails gracefully when Azure SDK is not installed."""
        with patch.dict("sys.modules", {"azure.keyvault.secrets": None, "azure.identity": None}):
            with pytest.raises(SecretProviderError, match="Azure SDK not installed"):
                AzureKeyVaultProvider(vault_url="https://test.vault.azure.net/")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_success(self, mock_credential, mock_client_class):
        """Test successful secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "my-secret-value"
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key")
        
        assert result == "my-secret-value"
        mock_client.get_secret.assert_called_once_with("api-key")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_with_version(self, mock_credential, mock_client_class):
        """Test secret retrieval with version."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "versioned-secret-value"
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key", version="v2")
        
        assert result == "versioned-secret-value"
        mock_client.get_secret.assert_called_once_with("api-key", version="v2")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_not_found(self, mock_credential, mock_client_class):
        """Test retrieval of non-existent secret."""
        from azure.core.exceptions import ResourceNotFoundError
        
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        with pytest.raises(SecretNotFoundError, match="Secret not found: missing-key"):
            provider.get_secret("missing-key")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_with_null_value(self, mock_credential, mock_client_class):
        """Test retrieval of secret with null value."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = None
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        with pytest.raises(SecretNotFoundError, match="has no value"):
            provider.get_secret("null-secret")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_provider_error(self, mock_credential, mock_client_class):
        """Test handling of provider errors during retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_secret.side_effect = Exception("Network error")
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        with pytest.raises(SecretProviderError, match="Failed to retrieve secret"):
            provider.get_secret("api-key")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_bytes_success(self, mock_credential, mock_client_class):
        """Test successful binary secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "binary-secret-value"
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("binary-key")
        
        assert result == b"binary-secret-value"
        assert isinstance(result, bytes)
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_get_secret_bytes_utf8_encoding(self, mock_credential, mock_client_class):
        """Test that get_secret_bytes properly encodes UTF-8."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "café"
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("utf8-key")
        
        assert result == "café".encode("utf-8")
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_secret_exists_returns_true(self, mock_credential, mock_client_class):
        """Test secret_exists returns True for existing enabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.properties.enabled = True
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        assert provider.secret_exists("existing-key") is True
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_secret_exists_returns_false_for_disabled(self, mock_credential, mock_client_class):
        """Test secret_exists returns False for disabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.properties.enabled = False
        mock_client.get_secret.return_value = mock_secret
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        assert provider.secret_exists("disabled-key") is False
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_secret_exists_returns_false_for_not_found(self, mock_credential, mock_client_class):
        """Test secret_exists returns False for non-existent secrets."""
        from azure.core.exceptions import ResourceNotFoundError
        
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_secret.side_effect = ResourceNotFoundError("Not found")
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        assert provider.secret_exists("missing-key") is False
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_secret_exists_handles_errors_gracefully(self, mock_credential, mock_client_class):
        """Test secret_exists returns False on unexpected errors."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_secret.side_effect = Exception("Network error")
        
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        
        assert provider.secret_exists("error-key") is False
    
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_authentication_error(self, mock_credential):
        """Test handling of authentication errors."""
        from azure.core.exceptions import ClientAuthenticationError
        
        mock_credential.side_effect = ClientAuthenticationError("Auth failed")
        
        with pytest.raises(SecretProviderError, match="Failed to authenticate"):
            AzureKeyVaultProvider(vault_url="https://test.vault.azure.net/")


class TestAzureKeyVaultProviderIntegration:
    """Integration-style tests with more realistic mocking."""
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_complete_workflow(self, mock_credential, mock_client_class):
        """Test complete workflow of checking, retrieving, and reading secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Setup mock responses
        def get_secret_side_effect(name, version=None):
            secrets = {
                "api-key": Mock(value="key123", properties=Mock(enabled=True)),
                "jwt-private-key": Mock(
                    value="-----BEGIN PRIVATE KEY-----\ndata\n-----END PRIVATE KEY-----",
                    properties=Mock(enabled=True)
                ),
            }
            if name in secrets:
                return secrets[name]
            from azure.core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Secret {name} not found")
        
        mock_client.get_secret.side_effect = get_secret_side_effect
        
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
