# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity provider factory with DriverConfig."""

import pytest
from copilot_auth import IdentityProvider, create_identity_provider


class MockDriverConfig:
    """Mock DriverConfig for testing."""

    def __init__(self, config_dict):
        self._config = config_dict

    def __getattr__(self, name: str):
        """Support attribute access to config values."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self._config.get(name)

    def get(self, key, default=None):
        """Get config value by key."""
        return self._config.get(key, default)


class TestCreateIdentityProviderWithDriverConfig:
    """Tests for create_identity_provider factory with DriverConfig."""

    def test_create_mock_provider(self):
        """Test creating a mock provider with DriverConfig."""
        driver_config = MockDriverConfig({})
        provider = create_identity_provider("mock", driver_config)

        assert isinstance(provider, IdentityProvider)

    def test_create_github_provider_with_config(self):
        """Test creating a GitHub provider with DriverConfig."""
        driver_config = MockDriverConfig({
            "github_client_id": "test-client-id",
            "github_client_secret": "test-client-secret",
            "github_redirect_uri": "https://auth.example.com/callback",
            "github_api_base_url": "https://api.github.com"
        })
        provider = create_identity_provider("github", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"
        assert provider.api_base_url == "https://api.github.com"

    def test_create_github_provider_with_custom_api_url(self):
        """Test creating a GitHub provider with custom API URL."""
        driver_config = MockDriverConfig({
            "github_client_id": "test-client-id",
            "github_client_secret": "test-client-secret",
            "github_redirect_uri": "https://auth.example.com/callback",
            "github_api_base_url": "https://github.enterprise.com/api"
        })
        provider = create_identity_provider("github", driver_config)

        assert provider.api_base_url == "https://github.enterprise.com/api"

    def test_create_google_provider_with_config(self):
        """Test creating a Google provider with DriverConfig."""
        driver_config = MockDriverConfig({
            "google_client_id": "test-client-id",
            "google_client_secret": "test-client-secret",
            "google_redirect_uri": "https://auth.example.com/callback",
        })
        provider = create_identity_provider("google", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"

    def test_create_microsoft_provider_with_config(self):
        """Test creating a Microsoft provider with DriverConfig."""
        driver_config = MockDriverConfig({
            "microsoft_client_id": "test-client-id",
            "microsoft_client_secret": "test-client-secret",
            "microsoft_redirect_uri": "https://auth.example.com/callback",
            "microsoft_tenant": "common",
        })
        provider = create_identity_provider("microsoft", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"

    def test_create_datatracker_provider_with_config(self):
        """Test creating a Datatracker provider with DriverConfig."""
        driver_config = MockDriverConfig({
            "api_base_url": "https://datatracker.ietf.org/api"
        })
        provider = create_identity_provider("datatracker", driver_config)

        assert isinstance(provider, IdentityProvider)
        assert provider.api_base_url == "https://datatracker.ietf.org/api"

    def test_create_datatracker_provider_with_custom_api_url(self):
        """Test creating a Datatracker provider with custom API URL."""
        driver_config = MockDriverConfig({
            "api_base_url": "https://test.datatracker.ietf.org/api"
        })
        provider = create_identity_provider("datatracker", driver_config)

        assert provider.api_base_url == "https://test.datatracker.ietf.org/api"

    def test_create_datatracker_provider_requires_api_base_url(self):
        """Test creating a Datatracker provider requires api_base_url."""
        driver_config = MockDriverConfig({})

        with pytest.raises(ValueError, match="requires 'api_base_url'"):
            create_identity_provider("datatracker", driver_config)

    def test_driver_name_parameter_is_required(self):
        """Test that driver_name parameter is required."""
        driver_config = MockDriverConfig({})

        with pytest.raises(ValueError, match="driver_name parameter is required"):
            create_identity_provider("", driver_config)

    def test_create_provider_raises_error_for_unknown_type(self):
        """Test creating provider with unknown type raises error."""
        driver_config = MockDriverConfig({})

        with pytest.raises(ValueError, match="Unknown identity provider"):
            create_identity_provider("unknown-provider", driver_config)

    def test_driver_name_is_case_insensitive(self):
        """Test that driver name is case insensitive."""
        driver_config = MockDriverConfig({})

        provider1 = create_identity_provider("MOCK", driver_config)
        provider2 = create_identity_provider("Mock", driver_config)
        provider3 = create_identity_provider("mock", driver_config)

        assert isinstance(provider1, IdentityProvider)
        assert isinstance(provider2, IdentityProvider)
        assert isinstance(provider3, IdentityProvider)
