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
    AzureKeyVaultProvider,
    LocalFileSecretProvider,
    SecretProviderError,
    create_secret_provider,
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

    def test_create_azure_provider(self):
        """Test creation of Azure Key Vault provider."""
        vault_url = "https://test-vault.vault.azure.net/"
        provider = create_secret_provider("azure", vault_url=vault_url)
        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == vault_url

    def test_create_azure_provider_with_name(self):
        """Test creation of Azure provider with vault name."""
        vault_name = "test-vault"
        provider = create_secret_provider("azure", vault_name=vault_name)
        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == f"https://{vault_name}.vault.azure.net/"
