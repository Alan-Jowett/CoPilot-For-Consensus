# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""GitHub OAuth identity provider.

This module provides authentication via GitHub OAuth, allowing users to
authenticate using their GitHub accounts.
"""

from typing import Any, Dict, Optional

import httpx

from .models import User
from .oidc_provider import OIDCProvider
from .provider import AuthenticationError, ProviderError


class GitHubIdentityProvider(OIDCProvider):
    """GitHub OAuth/OIDC identity provider.
    
    This provider authenticates users via GitHub OAuth and retrieves
    their profile information from the GitHub API.
    
    Attributes:
        client_id: GitHub OAuth application client ID
        client_secret: GitHub OAuth application client secret
        redirect_uri: OAuth callback URL
        api_base_url: Base URL for GitHub API (default: https://api.github.com)
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        api_base_url: str = "https://api.github.com",
    ):
        """Initialize the GitHub identity provider.
        
        Args:
            client_id: GitHub OAuth application client ID
            client_secret: GitHub OAuth application client secret
            redirect_uri: OAuth callback URL
            api_base_url: Base URL for GitHub API
        """
        # GitHub uses token.actions.githubusercontent.com for OIDC
        discovery_url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
        
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            discovery_url=discovery_url,
            scopes=["openid", "read:user", "user:email"],
        )
        
        self.api_base_url = api_base_url
    
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
    
    def _map_userinfo_to_user(self, userinfo: Dict[str, Any], provider_id: str) -> User:
        """Map GitHub userinfo to User model.
        
        Args:
            userinfo: Raw userinfo from GitHub
            provider_id: Provider identifier ("github")
        
        Returns:
            User object with mapped fields
        """
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
        affiliations = []
        
        return User(
            id=f"github:{user_id}",
            email=email,
            name=name,
            roles=roles,
            affiliations=affiliations,
        )
    
    def get_user(self, token: str) -> Optional[User]:
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
