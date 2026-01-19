# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""GitHub OAuth identity provider.

This module provides authentication via GitHub OAuth, allowing users to
authenticate using their GitHub accounts.
"""

from typing import Any

import httpx
from copilot_config.generated.adapters.oidc_providers import DriverConfig_OidcProviders_Github

from .models import User
from .oidc_provider import OIDCProvider
from .provider import AuthenticationError


class GitHubIdentityProvider(OIDCProvider):
    """GitHub OAuth/OIDC identity provider.

    This provider authenticates users via GitHub OAuth and retrieves
    their profile information from the GitHub API.

    Attributes:
        client_id: GitHub OAuth application client ID
        client_secret: GitHub OAuth application client secret
        redirect_uri: OAuth callback URL
        api_base_url: Base URL for GitHub API
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        api_base_url: str,
    ):
        """Initialize the GitHub identity provider.

        Args:
            client_id: GitHub OAuth application client ID
            client_secret: GitHub OAuth application client secret
            redirect_uri: OAuth callback URL
            api_base_url: Base URL for GitHub API
        """
        # NOTE: Standard GitHub OAuth is **not** OIDC and has no discovery document.
        # We therefore wire endpoints manually to the OAuth authorize/token/userinfo URLs.
        # This provider will surface an explicit error if an ID token is expected, because
        # GitHub OAuth does not issue id_tokens. For GitHub Actions OIDC, you must configure
        # that separately (token.actions.githubusercontent.com).

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            discovery_url="",  # placeholder; discover() is overridden
            scopes=["read:user", "user:email"],
        )

        self.api_base_url = api_base_url

    @classmethod
    def from_config(cls, driver_config: DriverConfig_OidcProviders_Github) -> "GitHubIdentityProvider":
        """Create GitHubIdentityProvider from typed config.

        Args:
            driver_config: DriverConfig object with GitHub OAuth configuration

        Returns:
            GitHubIdentityProvider instance

        """
        client_id = driver_config.github_client_id
        client_secret = driver_config.github_client_secret
        redirect_uri = driver_config.github_redirect_uri
        api_base_url = driver_config.github_api_base_url

        if not client_id or not client_secret:
            raise ValueError("GitHubIdentityProvider requires github_client_id and github_client_secret")

        if not redirect_uri:
            raise ValueError("GitHubIdentityProvider requires github_redirect_uri (or a service-level default)")

        if not api_base_url:
            api_base_url = "https://api.github.com"

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            api_base_url=api_base_url,
        )

    def discover(self) -> None:
        """Set GitHub OAuth endpoints explicitly (no OIDC discovery)."""
        # Authorization and token endpoints for standard GitHub OAuth apps
        self._authorization_endpoint = "https://github.com/login/oauth/authorize"
        self._token_endpoint = "https://github.com/login/oauth/access_token"
        # Userinfo via REST API
        self._userinfo_endpoint = f"{self.api_base_url}/user"
        # No JWKS / issuer because GitHub OAuth does not return id_tokens
        self._jwks_uri = None
        self._issuer = None

    def validate_id_token(self, id_token: str, nonce: str, leeway: int = 60) -> dict[str, Any]:
        """GitHub OAuth does not issue ID tokens; fail fast with guidance."""
        del id_token, nonce, leeway
        raise AuthenticationError(
            "GitHub OAuth does not provide an id_token. "
            "Use an OIDC-capable provider or configure GitHub Actions OIDC separately."
        )

    def _get_user_organizations(self, access_token: str) -> list[str]:
        """Retrieve user's GitHub organizations.

        Args:
            access_token: GitHub OAuth access token

        Returns:
            List of organization names
        """
        try:
            response = httpx.get(
                f"{self.api_base_url}/user/orgs",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            orgs = response.json()
            return [org.get("login", "") for org in orgs if org.get("login")]

        except httpx.HTTPError:
            # Organizations are optional, return empty list on error
            return []

    def _map_userinfo_to_user(self, userinfo: dict[str, Any], provider_id: str) -> User:
        """Map GitHub userinfo to User model.

        Args:
            userinfo: Raw userinfo from GitHub
            provider_id: Provider identifier ("github")

        Returns:
            User object with mapped fields
        """
        del provider_id
        # Extract user ID
        user_id = str(userinfo.get("id", ""))
        if not user_id:
            user_id = userinfo.get("login", "unknown")

        # Extract email (may be None if not public)
        email = userinfo.get("email", "")
        if not email:
            # Try to get primary verified email
            email = f"{userinfo.get('login', 'unknown')}@users.noreply.github.com"

        # Extract name
        name = userinfo.get("name") or userinfo.get("login", "Unknown")

        # Default role
        roles = ["contributor"]

        # Organizations become affiliations
        affiliations: list[str] = []

        return User(
            id=f"github:{user_id}",
            email=email,
            name=name,
            roles=roles,
            affiliations=affiliations,
        )

    def get_user(self, token: str) -> User | None:
        """Retrieve user information from a GitHub OAuth token.

        Args:
            token: GitHub OAuth access token

        Returns:
            User object if token is valid, None otherwise

        Raises:
            AuthenticationError: If token is invalid
            ProviderError: If GitHub API is unavailable
        """
        # Get basic user info via OIDC userinfo endpoint
        user = super().get_user(token)

        if user:
            # Fetch organizations and add as affiliations
            orgs = self._get_user_organizations(token)
            user.affiliations.extend(orgs)

        return user
