# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for secret provider factory."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from copilot_secrets import (
    create_secret_provider,
    LocalFileSecretProvider,
    AzureKeyVaultProvider,
    SecretProviderError,
)


class TestFactory:
    """Test suite for secret provider factory."""
    
    def test_create_local_provider(self):
        """Test creation of local file provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider("local", base_path=tmpdir)
            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)
    
    def test_create_unknown_provider(self):
        """Test creation with unknown provider type."""
        with pytest.raises(SecretProviderError, match="Unknown provider type"):
            create_secret_provider("unknown_type")
    
    def test_factory_forwards_kwargs(self):
        """Test that factory forwards kwargs to provider constructor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider("local", base_path=tmpdir)
            assert provider.base_path == Path(tmpdir)
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_create_azure_provider(self, mock_credential, mock_client_class):
        """Test creation of Azure Key Vault provider."""
        vault_url = "https://test-vault.vault.azure.net/"
        provider = create_secret_provider("azure", vault_url=vault_url)
        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == vault_url
    
    @patch("copilot_secrets.azurekeyvault_provider.SecretClient")
    @patch("copilot_secrets.azurekeyvault_provider.DefaultAzureCredential")
    def test_create_azure_provider_with_name(self, mock_credential, mock_client_class):
        """Test creation of Azure provider with vault name."""
        vault_name = "test-vault"
        provider = create_secret_provider("azure", vault_name=vault_name)
        assert isinstance(provider, AzureKeyVaultProvider)
        assert "test-vault.vault.azure.net" in provider.vault_url
