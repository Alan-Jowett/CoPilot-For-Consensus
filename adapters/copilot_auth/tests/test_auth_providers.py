# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for identity providers."""

from unittest.mock import Mock, patch

import httpx
import pytest
from copilot_auth import AuthenticationError, IdentityProvider, User

# Import provider implementations from internal modules
from copilot_auth.datatracker_provider import DatatrackerIdentityProvider
from copilot_auth.github_provider import GitHubIdentityProvider
from copilot_auth.google_provider import GoogleIdentityProvider
from copilot_auth.microsoft_provider import MicrosoftIdentityProvider
from copilot_auth.mock_provider import MockIdentityProvider


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
            redirect_uri="https://auth.example.com/callback",
            api_base_url="https://api.github.com",
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
        provider = GitHubIdentityProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://auth.example.com/callback",
            api_base_url="https://api.github.com",
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


class TestGitHubIdentityProviderExtended:
    """Extended tests for GitHubIdentityProvider to improve coverage."""

    def test_from_config(self):
        """Test from_config creates provider from DriverConfig."""
        mock_config = Mock()
        mock_config.github_client_id = "config-client-id"
        mock_config.github_client_secret = "config-secret"
        mock_config.github_redirect_uri = "https://config.example.com/callback"
        mock_config.github_api_base_url = "https://api.github.com"
        
        provider = GitHubIdentityProvider.from_config(mock_config)
        
        assert provider.client_id == "config-client-id"
        assert provider.client_secret == "config-secret"
        assert provider.redirect_uri == "https://config.example.com/callback"
        assert provider.api_base_url == "https://api.github.com"

    def test_discover_sets_endpoints(self):
        """Test discover sets GitHub OAuth endpoints."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        provider.discover()
        
        assert provider._authorization_endpoint == "https://github.com/login/oauth/authorize"
        assert provider._token_endpoint == "https://github.com/login/oauth/access_token"
        assert provider._userinfo_endpoint == "https://api.github.com/user"
        assert provider._jwks_uri is None
        assert provider._issuer is None

    def test_validate_id_token_raises_error(self):
        """Test validate_id_token raises error for GitHub OAuth."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            provider.validate_id_token("fake-token", "fake-nonce")
        
        assert "GitHub OAuth does not provide an id_token" in str(exc_info.value)

    def test_get_user_organizations_success(self):
        """Test _get_user_organizations fetches orgs successfully."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        mock_response = Mock()
        mock_response.json.return_value = [
            {"login": "org1", "id": 1},
            {"login": "org2", "id": 2},
        ]
        
        with patch("httpx.get", return_value=mock_response) as mock_get:
            orgs = provider._get_user_organizations("test-token")
            
            mock_get.assert_called_once_with(
                "https://api.github.com/user/orgs",
                headers={"Authorization": "Bearer test-token"},
                timeout=10.0,
            )
            assert orgs == ["org1", "org2"]

    def test_get_user_organizations_http_error(self):
        """Test _get_user_organizations returns empty list on error."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Network error")
            orgs = provider._get_user_organizations("test-token")
            
            assert orgs == []

    def test_map_userinfo_to_user_with_full_data(self):
        """Test _map_userinfo_to_user maps complete userinfo."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        userinfo = {
            "id": 12345,
            "login": "testuser",
            "email": "test@example.com",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "github")
        
        assert user.id == "github:12345"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.roles == ["contributor"]
        assert user.affiliations == []

    def test_map_userinfo_to_user_missing_email(self):
        """Test _map_userinfo_to_user generates email when missing."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        userinfo = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "github")
        
        assert user.email == "testuser@users.noreply.github.com"

    def test_map_userinfo_to_user_missing_name(self):
        """Test _map_userinfo_to_user uses login when name missing."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        userinfo = {
            "id": 12345,
            "login": "testuser",
            "email": "test@example.com",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "github")
        
        assert user.name == "testuser"

    def test_map_userinfo_to_user_missing_id(self):
        """Test _map_userinfo_to_user uses login when id missing."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        userinfo = {
            "login": "testuser",
            "email": "test@example.com",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "github")
        
        assert user.id == "github:testuser"

    def test_get_user_with_organizations(self):
        """Test get_user fetches user info and organizations."""
        provider = GitHubIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            api_base_url="https://api.github.com",
        )
        
        # Mock userinfo response
        userinfo_response = Mock()
        userinfo_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": "test@example.com",
            "name": "Test User",
        }
        
        # Mock orgs response
        orgs_response = Mock()
        orgs_response.json.return_value = [
            {"login": "org1"},
            {"login": "org2"},
        ]
        
        with patch("httpx.get") as mock_get:
            # First call: userinfo, second call: orgs
            mock_get.side_effect = [userinfo_response, orgs_response]
            
            user = provider.get_user("test-token")
            
            assert user is not None
            assert user.id == "github:12345"
            assert "org1" in user.affiliations
            assert "org2" in user.affiliations


class TestGoogleIdentityProviderExtended:
    """Extended tests for GoogleIdentityProvider to improve coverage."""

    def test_initialization(self):
        """Test GoogleIdentityProvider initializes correctly."""
        provider = GoogleIdentityProvider(
            client_id="google-client-id",
            client_secret="google-secret",
            redirect_uri="https://example.com/callback",
        )
        
        assert provider.client_id == "google-client-id"
        assert provider.client_secret == "google-secret"
        assert provider.redirect_uri == "https://example.com/callback"
        assert provider.discovery_url == "https://accounts.google.com/.well-known/openid-configuration"
        assert provider.scopes == ["openid", "profile", "email"]

    def test_from_config(self):
        """Test from_config creates provider from DriverConfig."""
        mock_config = Mock()
        mock_config.google_client_id = "config-client-id"
        mock_config.google_client_secret = "config-secret"
        mock_config.google_redirect_uri = "https://config.example.com/callback"
        
        provider = GoogleIdentityProvider.from_config(mock_config)
        
        assert provider.client_id == "config-client-id"
        assert provider.client_secret == "config-secret"
        assert provider.redirect_uri == "https://config.example.com/callback"

    def test_map_userinfo_to_user_with_full_data(self):
        """Test _map_userinfo_to_user maps complete userinfo."""
        provider = GoogleIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
        )
        
        userinfo = {
            "sub": "google-user-123",
            "email": "test@example.com",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "google")
        
        assert user.id == "google:google-user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.roles == ["contributor"]
        assert user.affiliations == []

    def test_map_userinfo_to_user_missing_email(self):
        """Test _map_userinfo_to_user raises error when email missing."""
        provider = GoogleIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
        )
        
        userinfo = {
            "sub": "google-user-123",
            "name": "Test User",
        }
        
        with pytest.raises(ValueError) as exc_info:
            provider._map_userinfo_to_user(userinfo, "google")
        
        assert "missing email" in str(exc_info.value)

    def test_map_userinfo_to_user_missing_name_uses_given_family(self):
        """Test _map_userinfo_to_user constructs name from given_name and family_name."""
        provider = GoogleIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
        )
        
        userinfo = {
            "sub": "google-user-123",
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "google")
        
        assert user.name == "Test User"

    def test_map_userinfo_to_user_missing_name_fallback_to_email(self):
        """Test _map_userinfo_to_user falls back to email when name missing."""
        provider = GoogleIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
        )
        
        userinfo = {
            "sub": "google-user-123",
            "email": "test@example.com",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "google")
        
        assert user.name == "test@example.com"


class TestMicrosoftIdentityProviderExtended:
    """Extended tests for MicrosoftIdentityProvider to improve coverage."""

    def test_initialization(self):
        """Test MicrosoftIdentityProvider initializes correctly."""
        provider = MicrosoftIdentityProvider(
            client_id="ms-client-id",
            client_secret="ms-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        assert provider.client_id == "ms-client-id"
        assert provider.client_secret == "ms-secret"
        assert provider.redirect_uri == "https://example.com/callback"
        assert provider.tenant == "common"
        assert "login.microsoftonline.com/common/v2.0" in provider.discovery_url
        assert provider.scopes == ["openid", "profile", "email"]

    def test_initialization_with_tenant(self):
        """Test MicrosoftIdentityProvider with specific tenant."""
        provider = MicrosoftIdentityProvider(
            client_id="ms-client-id",
            client_secret="ms-secret",
            redirect_uri="https://example.com/callback",
            tenant="contoso.onmicrosoft.com",
        )
        
        assert provider.tenant == "contoso.onmicrosoft.com"
        assert "login.microsoftonline.com/contoso.onmicrosoft.com/v2.0" in provider.discovery_url

    def test_from_config(self):
        """Test from_config creates provider from DriverConfig."""
        mock_config = Mock()
        mock_config.microsoft_client_id = "config-client-id"
        mock_config.microsoft_client_secret = "config-secret"
        mock_config.microsoft_redirect_uri = "https://config.example.com/callback"
        mock_config.microsoft_tenant = "test-tenant"
        
        provider = MicrosoftIdentityProvider.from_config(mock_config)
        
        assert provider.client_id == "config-client-id"
        assert provider.client_secret == "config-secret"
        assert provider.redirect_uri == "https://config.example.com/callback"
        assert provider.tenant == "test-tenant"

    def test_map_userinfo_to_user_with_full_data_and_tenant(self):
        """Test _map_userinfo_to_user maps complete userinfo with tenant."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="test-tenant",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "tid": "tenant-123",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.id == "microsoft:ms-user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.roles == ["contributor"]
        assert "microsoft:tenant:tenant-123" in user.affiliations

    def test_map_userinfo_to_user_without_tenant(self):
        """Test _map_userinfo_to_user without tenant affiliation."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "tid": "common",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.affiliations == []

    def test_map_userinfo_to_user_uses_sub_when_oid_missing(self):
        """Test _map_userinfo_to_user uses sub when oid missing."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "sub": "ms-user-sub",
            "email": "test@example.com",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.id == "microsoft:ms-user-sub"

    def test_map_userinfo_to_user_missing_email_uses_preferred_username(self):
        """Test _map_userinfo_to_user uses preferred_username when email missing."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "preferred_username": "test@example.com",
            "name": "Test User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.email == "test@example.com"

    def test_map_userinfo_to_user_missing_email_raises_error(self):
        """Test _map_userinfo_to_user raises error when email missing."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "name": "Test User",
        }
        
        with pytest.raises(ValueError) as exc_info:
            provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert "missing email" in str(exc_info.value)

    def test_map_userinfo_to_user_missing_name_uses_given_family(self):
        """Test _map_userinfo_to_user constructs name from given_name and family_name."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.name == "Test User"

    def test_map_userinfo_to_user_missing_name_fallback_to_email(self):
        """Test _map_userinfo_to_user falls back to email when name missing."""
        provider = MicrosoftIdentityProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback",
            tenant="common",
        )
        
        userinfo = {
            "oid": "ms-user-123",
            "email": "test@example.com",
        }
        
        user = provider._map_userinfo_to_user(userinfo, "microsoft")
        
        assert user.name == "test@example.com"
