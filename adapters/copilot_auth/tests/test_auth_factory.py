# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity provider factory."""

import pytest

from copilot_auth import (
    create_identity_provider,
    MockIdentityProvider,
    GitHubIdentityProvider,
    DatatrackerIdentityProvider,
)


class TestCreateIdentityProvider:
    """Tests for create_identity_provider factory function."""

    def test_create_mock_provider(self):
        """Test creating a mock provider."""
        provider = create_identity_provider("mock")
        
        assert isinstance(provider, MockIdentityProvider)

    def test_create_github_provider_with_parameters(self):
        """Test creating a GitHub provider with parameters."""
        provider = create_identity_provider(
            "github",
            client_id="test-client-id",
            client_secret="test-client-secret"
        )
        
        assert isinstance(provider, GitHubIdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"

    def test_create_github_provider_with_custom_api_url(self):
        """Test creating a GitHub provider with custom API URL."""
        provider = create_identity_provider(
            "github",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_base_url="https://github.enterprise.com/api"
        )
        
        assert isinstance(provider, GitHubIdentityProvider)
        assert provider.api_base_url == "https://github.enterprise.com/api"

    def test_create_github_provider_requires_api_base_url(self):
        """Test creating a GitHub provider requires api_base_url parameter."""
        with pytest.raises(ValueError, match="api_base_url parameter is required"):
            create_identity_provider(
                "github",
                client_id="test-client-id",
                client_secret="test-client-secret"
            )

    def test_create_github_provider_requires_credentials(self):
        """Test creating a GitHub provider without credentials raises error."""
        with pytest.raises(ValueError, match="client_id parameter is required"):
            create_identity_provider(
                "github",
                api_base_url="https://api.github.com"
            )

    def test_create_github_provider_requires_secret(self):
        """Test creating a GitHub provider without secret raises error."""
        with pytest.raises(ValueError, match="client_secret parameter is required"):
            create_identity_provider(
                "github",
                client_id="test-client-id",
                api_base_url="https://api.github.com"
            )

    def test_create_github_provider_from_environment(self, monkeypatch):
        """Test that factory doesn't read from environment automatically."""
        monkeypatch.setenv("GITHUB_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "env-client-secret")
        
        # Should still raise error because parameters must be explicit
        with pytest.raises(ValueError, match="client_id parameter is required"):
            create_identity_provider("github")

    def test_create_github_provider_raises_error_without_credentials(self, monkeypatch):
        """Test creating a GitHub provider without credentials raises error."""
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        
        with pytest.raises(ValueError, match="client_id parameter is required"):
            create_identity_provider("github", api_base_url="https://api.github.com")

    def test_create_datatracker_provider(self):
        """Test creating a Datatracker provider."""
        provider = create_identity_provider(
            "datatracker",
            api_base_url="https://datatracker.ietf.org/api"
        )
        
        assert isinstance(provider, DatatrackerIdentityProvider)
        assert provider.api_base_url == "https://datatracker.ietf.org/api"

    def test_create_datatracker_provider_requires_api_base_url(self):
        """Test creating a Datatracker provider requires api_base_url."""
        with pytest.raises(ValueError, match="api_base_url parameter is required"):
            create_identity_provider("datatracker")

    def test_create_datatracker_provider_with_custom_api_url(self):
        """Test creating a Datatracker provider with custom API URL."""
        provider = create_identity_provider(
            "datatracker",
            api_base_url="https://test.datatracker.ietf.org/api"
        )
        
        assert isinstance(provider, DatatrackerIdentityProvider)
        assert provider.api_base_url == "https://test.datatracker.ietf.org/api"

    def test_create_datatracker_provider_from_environment(self, monkeypatch):
        """Test that factory doesn't read from environment automatically."""
        monkeypatch.setenv("DATATRACKER_API_BASE_URL", "https://custom.datatracker.ietf.org/api")
        
        # Should still raise error because parameters must be explicit
        with pytest.raises(ValueError, match="api_base_url parameter is required"):
            create_identity_provider("datatracker")

    def test_provider_type_parameter_is_required(self):
        """Test that provider_type parameter is required."""
        with pytest.raises(ValueError, match="provider_type parameter is required"):
            create_identity_provider()

    def test_create_provider_with_default_from_environment(self, monkeypatch):
        """Test that factory doesn't read provider type from environment."""
        monkeypatch.setenv("IDENTITY_PROVIDER", "mock")
        
        # Should still raise error because provider_type must be explicit
        with pytest.raises(ValueError, match="provider_type parameter is required"):
            create_identity_provider()

    def test_create_provider_defaults_to_mock_without_environment(self, monkeypatch):
        """Test that provider_type parameter is required even without environment."""
        monkeypatch.delenv("IDENTITY_PROVIDER", raising=False)
        
        with pytest.raises(ValueError, match="provider_type parameter is required"):
            create_identity_provider()

    def test_create_provider_raises_error_for_unknown_type(self):
        """Test creating provider with unknown type raises error."""
        with pytest.raises(ValueError, match="Unknown identity provider type"):
            create_identity_provider("unknown-provider")

    def test_provider_type_is_case_insensitive(self):
        """Test that provider type is case insensitive."""
        provider1 = create_identity_provider("MOCK")
        provider2 = create_identity_provider("Mock")
        provider3 = create_identity_provider("mock")
        
        assert isinstance(provider1, MockIdentityProvider)
        assert isinstance(provider2, MockIdentityProvider)
        assert isinstance(provider3, MockIdentityProvider)
