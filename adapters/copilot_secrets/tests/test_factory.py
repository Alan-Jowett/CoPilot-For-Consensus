# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for secret provider factory."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock Azure modules for Azure provider tests
mock_secret_client = MagicMock()
mock_default_credential = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock(SecretClient=mock_secret_client)
sys.modules['azure.identity'] = MagicMock(DefaultAzureCredential=mock_default_credential)
sys.modules['azure.core'] = MagicMock()
sys.modules['azure.core.exceptions'] = MagicMock()

from copilot_secrets import (
    SecretProviderError,
    create_secret_provider,
)


class TestFactory:
    """Test suite for secret provider factory."""

    def test_create_local_provider(self):
        """Test creation of local file provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"base_path": tmpdir}
            provider = create_secret_provider("local", config)
            from copilot_secrets.local_provider import LocalFileSecretProvider
            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_local_provider_empty_config(self):
        """Test creation of local file provider with explicit path in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"base_path": tmpdir}
            provider = create_secret_provider("local", config)
            from copilot_secrets.local_provider import LocalFileSecretProvider
            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_unknown_provider(self):
        """Test creation with unknown provider type."""
        with pytest.raises(SecretProviderError, match="Unknown secret provider driver"):
            create_secret_provider("unknown_type", {})

    def test_create_provider_missing_driver_name(self):
        """Test that driver_name is required."""
        with pytest.raises(SecretProviderError, match="driver_name parameter is required"):
            create_secret_provider(None, {})

    def test_factory_forwards_config_to_provider(self):
        """Test that factory forwards config to provider.from_config()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"base_path": tmpdir}
            provider = create_secret_provider("local", config)
            from copilot_secrets.local_provider import LocalFileSecretProvider
            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_azure_provider(self):
        """Test creation of Azure Key Vault provider."""
        vault_url = "https://test-vault.vault.azure.net/"
        config = {"vault_url": vault_url}
        provider = create_secret_provider("azure", config)
        from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider
        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == vault_url

    def test_create_azurekeyvault_provider_alias(self):
        """Test that 'azurekeyvault' is an alias for 'azure'."""
        vault_url = "https://test-vault.vault.azure.net/"
        config = {"vault_url": vault_url}
        provider = create_secret_provider("azurekeyvault", config)
        from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider
        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == vault_url
