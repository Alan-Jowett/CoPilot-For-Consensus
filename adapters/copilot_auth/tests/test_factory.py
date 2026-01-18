# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity provider factory with typed configs."""

import pytest
from copilot_auth import IdentityProvider, create_identity_provider
from copilot_config.generated.adapters.oidc_providers import (
    DriverConfig_OidcProviders_Github,
    DriverConfig_OidcProviders_Google,
    DriverConfig_OidcProviders_Microsoft,
)


class TestCreateIdentityProviderWithTypedConfig:
    """Tests for create_identity_provider factory with typed configs."""

    def test_create_github_provider_with_config(self):
        """Test creating a GitHub provider with typed config."""
        driver_config = DriverConfig_OidcProviders_Github(
            github_client_id="test-client-id",
            github_client_secret="test-client-secret",
            github_redirect_uri="https://auth.example.com/callback",
            github_api_base_url="https://api.github.com",
        )
        provider = create_identity_provider("github", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"
        assert provider.api_base_url == "https://api.github.com"

    def test_create_github_provider_with_custom_api_url(self):
        """Test creating a GitHub provider with custom API URL."""
        driver_config = DriverConfig_OidcProviders_Github(
            github_client_id="test-client-id",
            github_client_secret="test-client-secret",
            github_redirect_uri="https://auth.example.com/callback",
            github_api_base_url="https://github.enterprise.com/api",
        )
        provider = create_identity_provider("github", driver_config)

        assert provider.api_base_url == "https://github.enterprise.com/api"

    def test_create_google_provider_with_config(self):
        """Test creating a Google provider with typed config."""
        driver_config = DriverConfig_OidcProviders_Google(
            google_client_id="test-client-id",
            google_client_secret="test-client-secret",
            google_redirect_uri="https://auth.example.com/callback",
        )
        provider = create_identity_provider("google", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"

    def test_create_microsoft_provider_with_config(self):
        """Test creating a Microsoft provider with typed config."""
        driver_config = DriverConfig_OidcProviders_Microsoft(
            microsoft_client_id="test-client-id",
            microsoft_client_secret="test-client-secret",
            microsoft_redirect_uri="https://auth.example.com/callback",
            microsoft_tenant="common",
        )
        provider = create_identity_provider("microsoft", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"

    def test_create_provider_raises_error_for_unknown_type(self):
        """Test creating provider with unknown type raises error."""
        driver_config = DriverConfig_OidcProviders_Github(
            github_client_id="test-client-id",
            github_client_secret="test-client-secret",
            github_redirect_uri="https://auth.example.com/callback",
        )

        with pytest.raises(ValueError, match="Unknown identity provider"):
            create_identity_provider("unknown-provider", driver_config)

    def test_driver_name_is_case_insensitive(self):
        """Test that driver name is case insensitive."""
        driver_config = DriverConfig_OidcProviders_Github(
            github_client_id="test-client-id",
            github_client_secret="test-client-secret",
            github_redirect_uri="https://auth.example.com/callback",
        )

        provider1 = create_identity_provider("GITHUB", driver_config)
        provider2 = create_identity_provider("GitHub", driver_config)
        provider3 = create_identity_provider("github", driver_config)

        assert isinstance(provider1, IdentityProvider)
        assert isinstance(provider2, IdentityProvider)
        assert isinstance(provider3, IdentityProvider)
