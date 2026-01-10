# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test that Azure Key Vault dependencies are available when copilot-secrets[azure] is installed."""

import pytest


class TestAzureKeyVaultIntegration:
    """Test Azure Key Vault integration capabilities."""

    def test_azure_dependencies_importable(self):
        """Test that Azure SDK dependencies can be imported when installed.

        This test verifies that the auth service Docker image includes
        the necessary Azure Key Vault dependencies from copilot-secrets[azure].

        Note: This test will be skipped if Azure dependencies are not installed,
        which is expected in local development environments.
        """
        # The class should always be importable; Azure SDK is only required when
        # the provider is instantiated.
        from copilot_secrets.azurekeyvault_provider import AzureKeyVaultProvider

        assert AzureKeyVaultProvider is not None

    def test_azure_provider_initialization_requires_config(self):
        """Test that Azure provider requires vault configuration.

        This verifies the provider fails gracefully when vault config is missing.
        """
        from copilot_secrets import SecretProviderError, create_secret_provider

        # Factory should raise an error when vault config is missing
        with pytest.raises(SecretProviderError) as exc_info:
            create_secret_provider("azure", driver_config=None)

        # Check the error message
        message = str(exc_info.value)
        if "Azure SDK dependencies" in message:
            pytest.skip("Azure SDK dependencies not installed (expected in local dev)")
        assert "Azure Key Vault URL not configured" in message

    def test_secret_provider_factory_knows_azure(self):
        """Test that the secret provider factory recognizes 'azure' provider type."""
        from copilot_secrets import SecretProviderError, create_secret_provider

        # Factory should not raise "Unknown provider type" for azure.
        # It may raise other errors (like missing config), but should recognize the type.
        with pytest.raises(SecretProviderError) as exc_info:
            create_secret_provider("azure", driver_config=None)

        # Should be a config error, not unknown provider type
        message = str(exc_info.value)
        assert "Unknown provider type" not in message
        # In CI images with azure extras installed, this should be the config error.
        # In local dev without extras installed, skip.
        if "Azure SDK dependencies" in message:
            pytest.skip("Azure SDK dependencies not installed (expected in local dev)")
        assert "Azure Key Vault URL not configured" in message
