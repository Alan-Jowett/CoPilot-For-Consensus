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
        try:
            from copilot_secrets import AzureKeyVaultProvider
            
            # Verify class is importable
            assert AzureKeyVaultProvider is not None
            
        except ImportError as e:
            # Expected in local dev without [azure] extras
            if "Azure SDK dependencies" in str(e):
                pytest.skip("Azure SDK dependencies not installed (expected in local dev)")
            else:
                # Re-raise unexpected import errors
                raise

    def test_azure_provider_initialization_requires_config(self):
        """Test that Azure provider requires vault configuration.
        
        This verifies the provider fails gracefully when vault config is missing.
        """
        try:
            from copilot_secrets import SecretProviderError, create_secret_provider
            
            # Should raise error when no vault config provided
            with pytest.raises(SecretProviderError, match="Azure Key Vault URL not configured"):
                create_secret_provider("azure")
                
        except ImportError as e:
            if "Azure SDK dependencies" in str(e):
                pytest.skip("Azure SDK dependencies not installed (expected in local dev)")
            else:
                raise

    def test_secret_provider_factory_knows_azure(self):
        """Test that the secret provider factory recognizes 'azure' provider type."""
        from copilot_secrets import create_secret_provider
        
        # Factory should not raise "Unknown provider type" for azure
        # It may raise other errors (like missing config), but should recognize the type
        try:
            # This will fail with config error, not "unknown provider"
            create_secret_provider("azure")
        except Exception as e:
            # Should be a config error, not unknown provider type
            assert "Unknown provider type" not in str(e)
            # Should mention configuration requirement
            assert "configured" in str(e).lower() or "Azure SDK dependencies" in str(e)
