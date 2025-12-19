# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity providers."""

import pytest
from unittest.mock import patch

from copilot_auth import (
    User,
    IdentityProvider,
    MockIdentityProvider,
    GitHubIdentityProvider,
    DatatrackerIdentityProvider,
    AuthenticationError,
)


class TestMockIdentityProvider:
    """Tests for MockIdentityProvider."""

    def test_provider_initialization(self):
        """Test provider initializes with empty users dictionary."""
        provider = MockIdentityProvider()
        
        assert isinstance(provider, IdentityProvider)
        assert len(provider.users) == 0

    def test_add_user(self):
        """Test adding a user to the provider."""
        provider = MockIdentityProvider()
        user = User(
            id="user-123",
            email="test@example.com",
            name="Test User"
        )
        
        provider.add_user("token-123", user)
        
        assert len(provider.users) == 1
        assert provider.users["token-123"] == user

    def test_get_user_returns_user_for_valid_token(self):
        """Test get_user returns user for valid token."""
        provider = MockIdentityProvider()
        user = User(
            id="user-456",
            email="test@example.com",
            name="Test User"
        )
        provider.add_user("valid-token", user)
        
        result = provider.get_user("valid-token")
        
        assert result == user

    def test_get_user_returns_none_for_invalid_token(self):
        """Test get_user returns None for unknown token."""
        provider = MockIdentityProvider()
        
        result = provider.get_user("unknown-token")
        
        assert result is None

    def test_get_user_raises_error_for_empty_token(self):
        """Test get_user raises error for empty token."""
        provider = MockIdentityProvider()
        
        with pytest.raises(AuthenticationError):
            provider.get_user("")

    def test_get_user_raises_error_for_non_string_token(self):
        """Test get_user raises error for non-string token."""
        provider = MockIdentityProvider()
        
        with pytest.raises(AuthenticationError):
            provider.get_user(None)

    def test_remove_user(self):
        """Test removing a user from the provider."""
        provider = MockIdentityProvider()
        user = User(id="user-789", email="test@example.com", name="Test User")
        provider.add_user("token-789", user)
        
        provider.remove_user("token-789")
        
        assert len(provider.users) == 0
        assert provider.get_user("token-789") is None

    def test_remove_nonexistent_user_does_not_error(self):
        """Test removing nonexistent user does not raise error."""
        provider = MockIdentityProvider()
        
        # Should not raise exception and state should remain valid
        provider.remove_user("nonexistent-token")
        assert len(provider.users) == 0

    def test_clear_removes_all_users(self):
        """Test clear removes all users."""
        provider = MockIdentityProvider()
        user1 = User(id="user-1", email="test1@example.com", name="User 1")
        user2 = User(id="user-2", email="test2@example.com", name="User 2")
        provider.add_user("token-1", user1)
        provider.add_user("token-2", user2)
        
        provider.clear()
        
        assert len(provider.users) == 0

    def test_multiple_users_with_different_tokens(self):
        """Test managing multiple users with different tokens."""
        provider = MockIdentityProvider()
        user1 = User(id="user-1", email="test1@example.com", name="User 1")
        user2 = User(id="user-2", email="test2@example.com", name="User 2")
        user3 = User(id="user-3", email="test3@example.com", name="User 3")
        
        provider.add_user("token-1", user1)
        provider.add_user("token-2", user2)
        provider.add_user("token-3", user3)
        
        assert len(provider.users) == 3
        assert provider.get_user("token-1") == user1
        assert provider.get_user("token-2") == user2
        assert provider.get_user("token-3") == user3


class TestGitHubIdentityProvider:
    """Tests for GitHubIdentityProvider scaffold."""

    def test_provider_initialization(self):
        """Test provider initializes with required parameters."""
        provider = GitHubIdentityProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://auth.example.com/callback"
        )
        
        assert isinstance(provider, IdentityProvider)
        assert provider.client_id == "test-client-id"
        assert provider.client_secret == "test-client-secret"
        assert provider.api_base_url == "https://api.github.com"

    def test_provider_initialization_with_custom_api_url(self):
        """Test provider initializes with custom API URL."""
        provider = GitHubIdentityProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://auth.example.com/callback",
            api_base_url="https://github.enterprise.com/api"
        )
        
        assert provider.api_base_url == "https://github.enterprise.com/api"

    def test_get_user_raises_not_implemented(self):
        """Test get_user attempts to fetch user info and raises error on failure."""
        import httpx
        
        provider = GitHubIdentityProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://auth.example.com/callback"
        )
        
        # Mock httpx to raise an error
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Network error")
            
            from copilot_auth.provider import ProviderError
            
            with pytest.raises(ProviderError):
                provider.get_user("test-token")


class TestDatatrackerIdentityProvider:
    """Tests for DatatrackerIdentityProvider scaffold."""

    def test_provider_initialization(self):
        """Test provider initializes with default API URL."""
        provider = DatatrackerIdentityProvider()
        
        assert isinstance(provider, IdentityProvider)
        assert provider.api_base_url == "https://datatracker.ietf.org/api"

    def test_provider_initialization_with_custom_api_url(self):
        """Test provider initializes with custom API URL."""
        provider = DatatrackerIdentityProvider(
            api_base_url="https://test.datatracker.ietf.org/api"
        )
        
        assert provider.api_base_url == "https://test.datatracker.ietf.org/api"

    def test_get_user_raises_not_implemented(self):
        """Test get_user raises NotImplementedError (scaffold)."""
        provider = DatatrackerIdentityProvider()
        
        with pytest.raises(NotImplementedError):
            provider.get_user("test-token")
