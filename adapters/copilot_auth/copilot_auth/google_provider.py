# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Google OIDC identity provider.

This module provides authentication via Google OAuth/OIDC, allowing users to
authenticate using their Google accounts.
"""

from typing import Any

from .models import User
from .oidc_provider import OIDCProvider


class GoogleIdentityProvider(OIDCProvider):
    """Google OIDC identity provider.

    This provider authenticates users via Google OAuth/OIDC and retrieves
    their profile information from Google's userinfo endpoint.

    Attributes:
        client_id: Google OAuth client ID
        client_secret: Google OAuth client secret
        redirect_uri: OAuth callback URL
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        """Initialize the Google identity provider.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth callback URL
        """
        discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            discovery_url=discovery_url,
            scopes=["openid", "profile", "email"],
        )

    def _map_userinfo_to_user(self, userinfo: dict[str, Any], provider_id: str) -> User:
        """Map Google userinfo to User model.

        Args:
            userinfo: Raw userinfo from Google
            provider_id: Provider identifier ("google")

        Returns:
            User object with mapped fields
        """
        # Extract user ID (Google's "sub" claim)
        user_id = userinfo.get("sub", "unknown")

        # Extract email (verified)
        email = userinfo.get("email", "")
        if not email:
            raise ValueError("Google userinfo missing email")

        # Extract name
        name = userinfo.get("name", "")
        if not name:
            name = userinfo.get("given_name", "") + " " + userinfo.get("family_name", "")
            name = name.strip() or email

        # Default role
        roles = ["contributor"]

        # No organization info from standard Google OIDC
        affiliations: list[str] = []

        return User(
            id=f"google:{user_id}",
            email=email,
            name=name,
            roles=roles,
            affiliations=affiliations,
        )
