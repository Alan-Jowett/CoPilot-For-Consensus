# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for secret provider factory."""

import tempfile
from pathlib import Path

import pytest
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_AzureKeyVault,
    DriverConfig_SecretProvider_Local,
)
from copilot_secrets import (
    create_secret_provider,
)


class TestFactory:
    """Test suite for secret provider factory."""

    def test_create_local_provider(self):
        """Test creation of local file provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider(
                AdapterConfig_SecretProvider(
                    secret_provider_type="local",
                    driver=DriverConfig_SecretProvider_Local(base_path=tmpdir),
                )
            )
            from copilot_secrets.local_provider import LocalFileSecretProvider

            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_local_provider_empty_config(self):
        """Test creation of local file provider with explicit path in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider(
                AdapterConfig_SecretProvider(
                    secret_provider_type="local",
                    driver=DriverConfig_SecretProvider_Local(base_path=tmpdir),
                )
            )
            from copilot_secrets.local_provider import LocalFileSecretProvider

            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_unknown_provider(self):
        """Test creation with unknown provider type."""
        with pytest.raises(ValueError, match="Unknown secret_provider driver"):
            create_secret_provider(
                AdapterConfig_SecretProvider(  # type: ignore[arg-type]
                    secret_provider_type="unknown_type",
                    driver=DriverConfig_SecretProvider_Local(base_path="/run/secrets"),
                )
            )

    def test_create_provider_missing_driver_name(self):
        """Test that driver_name is required."""
        with pytest.raises(ValueError, match="secret_provider config is required"):
            create_secret_provider(None)  # type: ignore[arg-type]

    def test_factory_forwards_config_to_provider(self):
        """Test that factory forwards config to provider.from_config()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider(
                AdapterConfig_SecretProvider(
                    secret_provider_type="local",
                    driver=DriverConfig_SecretProvider_Local(base_path=tmpdir),
                )
            )
            from copilot_secrets.local_provider import LocalFileSecretProvider

            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)

    def test_create_azure_provider(self, azure_sdk_mocks):
        """Test creation of Azure Key Vault provider."""
        vault_url = "https://test-vault.vault.azure.net/"
        provider = create_secret_provider(
            AdapterConfig_SecretProvider(
                secret_provider_type="azure_key_vault",
                driver=DriverConfig_SecretProvider_AzureKeyVault(vault_url=vault_url),
            )
        )
        from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider

        assert isinstance(provider, AzureKeyVaultProvider)
        assert provider.vault_url == vault_url
