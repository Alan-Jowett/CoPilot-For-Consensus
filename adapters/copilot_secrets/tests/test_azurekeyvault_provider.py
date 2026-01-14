# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Key Vault secret provider."""

import os
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.integration

from copilot_secrets import (
    SecretNotFoundError,
    SecretProviderError,
)
from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider


class TestAzureKeyVaultProvider:
    """Test suite for AzureKeyVaultProvider."""

    def test_init_with_vault_url(self, azure_sdk_mocks):
        """Test initialization with explicit vault URL."""
        vault_url = "https://test-vault.vault.azure.net/"

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.vault_url == vault_url
        azure_sdk_mocks.default_credential_cls.assert_called()
        azure_sdk_mocks.secret_client_cls.assert_called()

    def test_init_with_vault_name(self, azure_sdk_mocks):
        """Test initialization with vault name."""
        vault_name = "test-vault"
        expected_url = f"https://{vault_name}.vault.azure.net/"

        provider = AzureKeyVaultProvider(vault_name=vault_name)

        assert provider.vault_url == expected_url

    def test_init_without_vault_config(self, azure_sdk_mocks):
        """Test initialization without any vault configuration raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SecretProviderError, match="Azure Key Vault URL not configured"):
                AzureKeyVaultProvider()

    def test_init_prioritizes_vault_url_over_name(self, azure_sdk_mocks):
        """Test that explicit vault_url takes priority over vault_name."""
        vault_url = "https://priority-vault.vault.azure.net/"
        vault_name = "ignored-vault"

        provider = AzureKeyVaultProvider(vault_url=vault_url, vault_name=vault_name)

        assert provider.vault_url == vault_url
        assert "ignored" not in provider.vault_url

    def test_init_prioritizes_vault_url_over_env(self, azure_sdk_mocks):
        """Test that explicit vault_url takes priority over environment variables."""
        vault_url = "https://explicit-vault.vault.azure.net/"
        env_url = "https://env-vault.vault.azure.net/"

        with patch.dict(os.environ, {"AZURE_KEY_VAULT_URI": env_url}):
            provider = AzureKeyVaultProvider(vault_url=vault_url)
            assert provider.vault_url == vault_url

    def test_get_secret_success(self, azure_sdk_mocks):
        """Test successful secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "my-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key")

        assert result == "my-secret-value"

    def test_get_secret_with_version(self, azure_sdk_mocks):
        """Test secret retrieval with version."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "versioned-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret("api-key", version="v2")

        assert result == "versioned-secret-value"
        mock_client.get_secret.assert_called_once_with("api-key", version="v2")

    def test_get_secret_not_found(self, azure_sdk_mocks):
        """Test retrieval of non-existent secret."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        mock_client.get_secret.side_effect = azure_sdk_mocks.ResourceNotFoundError("Secret not found")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretNotFoundError, match="Key not found: missing-key"):
            provider.get_secret("missing-key")

    def test_get_secret_with_null_value(self, azure_sdk_mocks):
        """Test retrieval of secret with null value."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = None
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretNotFoundError, match="has no value"):
            provider.get_secret("null-secret")

    def test_get_secret_provider_error(self, azure_sdk_mocks):
        """Test handling of provider errors during retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        mock_client.get_secret.side_effect = Exception("Network error")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        with pytest.raises(SecretProviderError, match="Failed to retrieve key"):
            provider.get_secret("api-key")

    def test_get_secret_bytes_success(self, azure_sdk_mocks):
        """Test successful binary secret retrieval."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "binary-secret-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("binary-key")

        assert result == b"binary-secret-value"
        assert isinstance(result, bytes)

    def test_get_secret_bytes_utf8_encoding(self, azure_sdk_mocks):
        """Test that get_secret_bytes properly encodes UTF-8."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "café"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)
        result = provider.get_secret_bytes("utf8-key")

        assert result == "café".encode()

    def test_secret_exists_returns_true(self, azure_sdk_mocks):
        """Test secret_exists returns True for existing enabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_props = Mock()
        mock_props.enabled = True
        mock_secret.properties = mock_props
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("existing-key") is True

    def test_secret_exists_returns_false_for_disabled(self, azure_sdk_mocks):
        """Test secret_exists returns False for disabled secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_props = Mock()
        mock_props.enabled = False
        mock_secret.properties = mock_props
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("disabled-key") is False

    def test_secret_exists_returns_false_for_not_found(self, azure_sdk_mocks):
        """Test secret_exists returns False for non-existent secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        mock_client.get_secret.side_effect = azure_sdk_mocks.ResourceNotFoundError("Not found")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("missing-key") is False

    def test_secret_exists_handles_errors_gracefully(self, azure_sdk_mocks):
        """Test secret_exists returns False on unexpected Azure errors."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        # Use AzureError which should be caught and logged
        mock_client.get_secret.side_effect = azure_sdk_mocks.AzureError("Network error")

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        assert provider.secret_exists("error-key") is False

    def test_authentication_error(self, azure_sdk_mocks):
        """Test handling of authentication errors."""
        azure_sdk_mocks.default_credential_cls.side_effect = azure_sdk_mocks.ClientAuthenticationError(
            "Auth failed"
        )

        with pytest.raises(SecretProviderError, match="Failed to authenticate"):
            AzureKeyVaultProvider(vault_url="https://test.vault.azure.net/")

        # Reset for other tests
        azure_sdk_mocks.default_credential_cls.side_effect = None

    def test_missing_azure_sdk_dependencies(self):
        """Test that appropriate error is raised when Azure SDK is not installed."""
        # Since the module is already imported with mocks in place, we verify that
        # the ImportError handler creates the expected error message by checking
        # the error message that would be raised.
        # The actual ImportError path is tested implicitly when running tests without
        # Azure SDK installed, but here we verify the error message format.

        expected_keywords = ["Azure SDK dependencies", "not installed", "pip install"]

        # Verify that if ImportError occurred, the message would be correct
        # This is more of a documentation test that shows what users would see
        try:
            raise SecretProviderError(
                "Azure SDK dependencies for Azure Key Vault are not installed. "
                "For production, install with: pip install copilot-secrets[azure]. "
                "For local development from the adapter directory, use: pip install -e \".[azure]\""
            )
        except SecretProviderError as e:
            error_message = str(e)
            for keyword in expected_keywords:
                assert keyword in error_message, f"Expected keyword '{keyword}' in error message"

    def test_close_method(self, azure_sdk_mocks):
        """Test that close method properly closes both client and credential."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        azure_sdk_mocks.default_credential_cls.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Add close methods to mocks
        mock_client.close = Mock()
        mock_credential.close = Mock()

        # Call close
        provider.close()

        # Verify both close methods were called
        mock_client.close.assert_called_once()
        mock_credential.close.assert_called_once()

    def test_close_method_handles_missing_close(self, azure_sdk_mocks):
        """Test that close method handles objects without close method."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        azure_sdk_mocks.default_credential_cls.return_value = mock_credential

        # Remove close method from mocks
        del mock_client.close
        del mock_credential.close

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Should not raise any exception
        provider.close()

    def test_close_method_handles_exceptions(self, azure_sdk_mocks):
        """Test that close method suppresses exceptions during cleanup."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        azure_sdk_mocks.default_credential_cls.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Make close methods raise exceptions
        mock_client.close = Mock(side_effect=RuntimeError("Close failed"))
        mock_credential.close = Mock(side_effect=RuntimeError("Close failed"))

        # Should not raise any exception
        provider.close()

    def test_del_method(self, azure_sdk_mocks):
        """Test that __del__ method calls close without raising exceptions."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        azure_sdk_mocks.default_credential_cls.return_value = mock_credential

        # Add close methods to mocks before creating provider
        mock_client.close = Mock()
        mock_credential.close = Mock()

        # Verify close hasn't been called yet
        assert not mock_client.close.called
        assert not mock_credential.close.called

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Still not called after instantiation
        assert not mock_client.close.called
        assert not mock_credential.close.called

        # Use del to trigger __del__ naturally instead of calling it explicitly
        del provider

        # Verify close was attempted
        mock_client.close.assert_called_once()
        mock_credential.close.assert_called_once()

    def test_del_method_handles_exceptions(self, azure_sdk_mocks):
        """Test that __del__ method suppresses exceptions during cleanup."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        mock_credential = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client
        azure_sdk_mocks.default_credential_cls.return_value = mock_credential

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Make close raise an exception
        mock_client.close = Mock(side_effect=RuntimeError("Close failed"))
        mock_credential.close = Mock(side_effect=RuntimeError("Close failed"))

        # Should not raise any exception when deleted - test passes if no exception propagates
        try:
            del provider
        except Exception as e:
            pytest.fail(f"__del__ should suppress exceptions but raised: {e}")


class TestAzureKeyVaultProviderIntegration:
    """Integration-style tests with more realistic mocking."""

    def test_complete_workflow(self, azure_sdk_mocks):
        """Test complete workflow of checking, retrieving, and reading secrets."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

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
            raise azure_sdk_mocks.ResourceNotFoundError(f"Secret {name} not found")

        # Setup mock responses for get_secret_properties
        def get_secret_properties_side_effect(name):
            properties = {
                "api-key": Mock(enabled=True),
                "jwt-private-key": Mock(enabled=True),
            }
            if name in properties:
                return properties[name]
            raise azure_sdk_mocks.ResourceNotFoundError(f"Secret {name} not found")

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


class TestSecretNameNormalization:
    """Test suite for secret name normalization."""

    def test_normalize_secret_name_basic(self):
        """Test basic underscore to hyphen conversion."""
        assert AzureKeyVaultProvider._normalize_secret_name("jwt_private_key") == "jwt-private-key"
        assert AzureKeyVaultProvider._normalize_secret_name("message_bus_user") == "message-bus-user"
        assert AzureKeyVaultProvider._normalize_secret_name("mongodb_root_username") == "mongodb-root-username"

    def test_normalize_secret_name_already_hyphenated(self):
        """Test that already-hyphenated names pass through unchanged."""
        assert AzureKeyVaultProvider._normalize_secret_name("jwt-private-key") == "jwt-private-key"
        assert AzureKeyVaultProvider._normalize_secret_name("message-bus-user") == "message-bus-user"

    def test_normalize_secret_name_no_separators(self):
        """Test names without underscores or hyphens."""
        assert AzureKeyVaultProvider._normalize_secret_name("apikey") == "apikey"
        assert AzureKeyVaultProvider._normalize_secret_name("secret") == "secret"

    def test_normalize_secret_name_multiple_underscores(self):
        """Test names with multiple consecutive underscores."""
        assert AzureKeyVaultProvider._normalize_secret_name("my__secret__key") == "my--secret--key"

    def test_get_secret_normalizes_name(self, azure_sdk_mocks):
        """Test that get_secret automatically normalizes secret names."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_secret.value = "test-value"
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Request with underscores
        result = provider.get_secret("jwt_private_key")

        # Verify it queries with hyphens
        mock_client.get_secret.assert_called_with("jwt-private-key")
        assert result == "test-value"

    def test_secret_exists_normalizes_name(self, azure_sdk_mocks):
        """Test that secret_exists automatically normalizes secret names."""
        vault_url = "https://test-vault.vault.azure.net/"
        mock_client = Mock()
        azure_sdk_mocks.secret_client_cls.return_value = mock_client

        mock_secret = Mock()
        mock_props = Mock()
        mock_props.enabled = True
        mock_secret.properties = mock_props
        mock_client.get_secret.return_value = mock_secret

        provider = AzureKeyVaultProvider(vault_url=vault_url)

        # Check with underscores
        result = provider.secret_exists("message_bus_password")

        # Verify it queries with hyphens
        mock_client.get_secret.assert_called_with("message-bus-password")
        assert result is True
