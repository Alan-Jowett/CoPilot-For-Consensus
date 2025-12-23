# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating identity providers based on configuration.

This module provides a factory function to create identity provider instances
based on configuration or environment variables, enabling easy switching
between authentication strategies.
"""

import os
from typing import Optional

from .provider import IdentityProvider
from .mock_provider import MockIdentityProvider
from .github_provider import GitHubIdentityProvider
from .google_provider import GoogleIdentityProvider
from .microsoft_provider import MicrosoftIdentityProvider
from .datatracker_provider import DatatrackerIdentityProvider


def create_identity_provider(
    provider_type: Optional[str] = None,
    **kwargs
) -> IdentityProvider:
    """Create an identity provider based on type.

    This factory method creates the appropriate identity provider based on
    the provider_type parameter.

    Supported provider types:
    - "mock": MockIdentityProvider for testing/local dev
    - "github": GitHubIdentityProvider for GitHub OAuth
    - "google": GoogleIdentityProvider for Google OIDC
    - "microsoft": MicrosoftIdentityProvider for Microsoft Entra ID
    - "datatracker": DatatrackerIdentityProvider for IETF Datatracker

    Args:
        provider_type: Type of provider to create (required).
                      Options: "mock", "github", "google", "microsoft", "datatracker"
        **kwargs: Provider-specific configuration parameters:
            - For GitHub: client_id (required), client_secret (required),
                         redirect_uri (required), api_base_url (optional)
            - For Google: client_id (required), client_secret (required),
                         redirect_uri (required)
            - For Microsoft: client_id (required), client_secret (required),
                            redirect_uri (required), tenant (optional, default: "common")
            - For Datatracker: api_base_url (required)

    Returns:
        IdentityProvider instance

    Raises:
        ValueError: If provider_type is unknown or required parameters are missing

    Examples:
        >>> # Create mock provider for testing
        >>> provider = create_identity_provider("mock")

        >>> # Create GitHub provider
        >>> provider = create_identity_provider(
        ...     "github",
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret",
        ...     redirect_uri="https://auth.example.com/callback"
        ... )

        >>> # Create Google provider
        >>> provider = create_identity_provider(
        ...     "google",
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret",
        ...     redirect_uri="https://auth.example.com/callback"
        ... )

        >>> # Create Microsoft provider
        >>> provider = create_identity_provider(
        ...     "microsoft",
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret",
        ...     redirect_uri="https://auth.example.com/callback",
        ...     tenant="common"
        ... )

        >>> # Create Datatracker provider
        >>> provider = create_identity_provider(
        ...     "datatracker",
        ...     api_base_url="https://datatracker.ietf.org/api"
        ... )
    """
    if not provider_type:
        raise ValueError(
            "provider_type parameter is required. "
            "Must be one of: mock, github, google, microsoft, datatracker"
        )

    provider_type = provider_type.lower()

    if provider_type == "mock":
        return MockIdentityProvider()

    elif provider_type == "github":
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")
        redirect_uri = kwargs.get("redirect_uri")

        if not client_id:
            raise ValueError(
                "client_id parameter is required for GitHub provider. "
                "Provide the GitHub OAuth client ID explicitly"
            )

        if not client_secret:
            raise ValueError(
                "client_secret parameter is required for GitHub provider. "
                "Provide the GitHub OAuth client secret explicitly"
            )

        if not redirect_uri:
            raise ValueError(
                "redirect_uri parameter is required for GitHub provider. "
                "Provide the OAuth callback URL explicitly"
            )

        api_base_url = kwargs.get("api_base_url", "https://api.github.com")

        return GitHubIdentityProvider(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            api_base_url=api_base_url
        )

    elif provider_type == "google":
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")
        redirect_uri = kwargs.get("redirect_uri")

        if not client_id:
            raise ValueError(
                "client_id parameter is required for Google provider. "
                "Provide the Google OAuth client ID explicitly"
            )

        if not client_secret:
            raise ValueError(
                "client_secret parameter is required for Google provider. "
                "Provide the Google OAuth client secret explicitly"
            )

        if not redirect_uri:
            raise ValueError(
                "redirect_uri parameter is required for Google provider. "
                "Provide the OAuth callback URL explicitly"
            )

        return GoogleIdentityProvider(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )

    elif provider_type == "microsoft":
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")
        redirect_uri = kwargs.get("redirect_uri")
        tenant = kwargs.get("tenant", "common")

        if not client_id:
            raise ValueError(
                "client_id parameter is required for Microsoft provider. "
                "Provide the Microsoft OAuth client ID explicitly"
            )

        if not client_secret:
            raise ValueError(
                "client_secret parameter is required for Microsoft provider. "
                "Provide the Microsoft OAuth client secret explicitly"
            )

        if not redirect_uri:
            raise ValueError(
                "redirect_uri parameter is required for Microsoft provider. "
                "Provide the OAuth callback URL explicitly"
            )

        return MicrosoftIdentityProvider(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            tenant=tenant
        )

    elif provider_type == "datatracker":
        api_base_url = kwargs.get("api_base_url")
        if not api_base_url:
            raise ValueError(
                "api_base_url parameter is required for Datatracker provider. "
                "Specify the Datatracker API base URL (e.g., 'https://datatracker.ietf.org/api')"
            )

        return DatatrackerIdentityProvider(api_base_url=api_base_url)

    else:
        raise ValueError(
            f"Unknown identity provider type: {provider_type}. "
            f"Supported types: mock, github, google, microsoft, datatracker"
        )
