# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity provider factory."""

import os
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

    def test_create_github_provider_from_environment(self, monkeypatch):
        """Test creating a GitHub provider from environment variables."""
        monkeypatch.setenv("GITHUB_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "env-client-secret")
        
        provider = create_identity_provider("github")
        
        assert isinstance(provider, GitHubIdentityProvider)
        assert provider.client_id == "env-client-id"
        assert provider.client_secret == "env-client-secret"

    def test_create_github_provider_raises_error_without_credentials(self):
        """Test creating a GitHub provider without credentials raises error."""
        with pytest.raises(ValueError, match="requires 'client_id' and 'client_secret'"):
            create_identity_provider("github")

    def test_create_datatracker_provider(self):
        """Test creating a Datatracker provider."""
        provider = create_identity_provider("datatracker")
        
        assert isinstance(provider, DatatrackerIdentityProvider)
        assert provider.api_base_url == "https://datatracker.ietf.org/api"

    def test_create_datatracker_provider_with_custom_api_url(self):
        """Test creating a Datatracker provider with custom API URL."""
        provider = create_identity_provider(
            "datatracker",
            api_base_url="https://test.datatracker.ietf.org/api"
        )
        
        assert isinstance(provider, DatatrackerIdentityProvider)
        assert provider.api_base_url == "https://test.datatracker.ietf.org/api"

    def test_create_datatracker_provider_from_environment(self, monkeypatch):
        """Test creating a Datatracker provider from environment variables."""
        monkeypatch.setenv("DATATRACKER_API_BASE_URL", "https://custom.datatracker.ietf.org/api")
        
        provider = create_identity_provider("datatracker")
        
        assert isinstance(provider, DatatrackerIdentityProvider)
        assert provider.api_base_url == "https://custom.datatracker.ietf.org/api"

    def test_create_provider_with_default_from_environment(self, monkeypatch):
        """Test creating provider with type from environment variable."""
        monkeypatch.setenv("IDENTITY_PROVIDER", "mock")
        
        provider = create_identity_provider()
        
        assert isinstance(provider, MockIdentityProvider)

    def test_create_provider_defaults_to_mock_without_environment(self, monkeypatch):
        """Test creating provider defaults to mock when no environment variable."""
        monkeypatch.delenv("IDENTITY_PROVIDER", raising=False)
        
        provider = create_identity_provider()
        
        assert isinstance(provider, MockIdentityProvider)

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

    def test_parameters_override_environment_variables(self, monkeypatch):
        """Test that explicit parameters override environment variables."""
        monkeypatch.setenv("GITHUB_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "env-client-secret")
        
        provider = create_identity_provider(
            "github",
            client_id="param-client-id",
            client_secret="param-client-secret"
        )
        
        assert provider.client_id == "param-client-id"
        assert provider.client_secret == "param-client-secret"
