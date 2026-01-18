# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Microsoft Entra ID (Azure AD) OIDC identity provider.

This module provides authentication via Microsoft Entra ID OAuth/OIDC,
allowing users to authenticate using their Microsoft accounts.
"""

from typing import Any

from copilot_config.generated.adapters.oidc_providers import DriverConfig_OidcProviders_Microsoft

from .models import User
from .oidc_provider import OIDCProvider


class MicrosoftIdentityProvider(OIDCProvider):
    """Microsoft Entra ID OIDC identity provider.

    This provider authenticates users via Microsoft OAuth/OIDC and retrieves
    their profile information from Microsoft's userinfo endpoint.

    Attributes:
        client_id: Microsoft OAuth client ID
        client_secret: Microsoft OAuth client secret
        redirect_uri: OAuth callback URL
        tenant: Azure AD tenant ID (schema default: "common" for multi-tenant)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant: str,
    ):
        """Initialize the Microsoft identity provider.

        Args:
            client_id: Microsoft OAuth client ID
            client_secret: Microsoft OAuth client secret
            redirect_uri: OAuth callback URL
            tenant: Azure AD tenant ID
        """
        discovery_url = f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            discovery_url=discovery_url,
            scopes=["openid", "profile", "email"],
        )

        self.tenant = tenant

    @classmethod
    def from_config(cls, driver_config: DriverConfig_OidcProviders_Microsoft) -> "MicrosoftIdentityProvider":
        """Create MicrosoftIdentityProvider from typed config.

        Args:
            driver_config: DriverConfig object with Microsoft OAuth configuration

        Returns:
            MicrosoftIdentityProvider instance

        """
        client_id = driver_config.microsoft_client_id
        client_secret = driver_config.microsoft_client_secret
        redirect_uri = driver_config.microsoft_redirect_uri
        tenant = driver_config.microsoft_tenant

        if not client_id or not client_secret:
            raise ValueError("MicrosoftIdentityProvider requires microsoft_client_id and microsoft_client_secret")

        if not redirect_uri:
            raise ValueError("MicrosoftIdentityProvider requires microsoft_redirect_uri (or a service-level default)")

        if not tenant:
            tenant = "common"

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            tenant=tenant,
        )

    def _map_userinfo_to_user(self, userinfo: dict[str, Any], provider_id: str) -> User:
        """Map Microsoft userinfo to User model.

        Args:
            userinfo: Raw userinfo from Microsoft
            provider_id: Provider identifier ("microsoft")

        Returns:
            User object with mapped fields
        """
        del provider_id
        # Extract user ID (Microsoft's "oid" or "sub")
        user_id = userinfo.get("oid") or userinfo.get("sub", "unknown")

        # Extract email
        email = userinfo.get("email") or userinfo.get("preferred_username", "")
        if not email:
            raise ValueError("Microsoft userinfo missing email")

        # Extract name
        name = userinfo.get("name", "")
        if not name:
            name = userinfo.get("given_name", "") + " " + userinfo.get("family_name", "")
            name = name.strip() or email

        # Default role
        roles = ["contributor"]

        # Extract tenant info as affiliation
        affiliations = []
        tenant_id = userinfo.get("tid")
        if tenant_id and tenant_id != "common":
            affiliations.append(f"microsoft:tenant:{tenant_id}")

        return User(
            id=f"microsoft:{user_id}",
            email=email,
            name=name,
            roles=roles,
            affiliations=affiliations,
        )
