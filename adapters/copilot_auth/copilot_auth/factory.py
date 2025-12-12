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
from .datatracker_provider import DatatrackerIdentityProvider


def create_identity_provider(
    provider_type: Optional[str] = None,
    **kwargs
) -> IdentityProvider:
    """Create an identity provider based on type.
    
    This factory method creates the appropriate identity provider based on
    the provider_type parameter or the IDENTITY_PROVIDER environment variable.
    
    Supported provider types:
    - "mock": MockIdentityProvider for testing/local dev
    - "github": GitHubIdentityProvider for GitHub OAuth
    - "datatracker": DatatrackerIdentityProvider for IETF Datatracker
    
    Args:
        provider_type: Type of provider to create. If None, reads from
                      IDENTITY_PROVIDER environment variable (default: "mock")
        **kwargs: Provider-specific configuration parameters:
            - For GitHub: client_id, client_secret, api_base_url
            - For Datatracker: api_base_url
            
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
        ...     client_secret="your_client_secret"
        ... )
        
        >>> # Create provider from environment variable
        >>> os.environ["IDENTITY_PROVIDER"] = "mock"
        >>> provider = create_identity_provider()
    """
    if provider_type is None:
        provider_type = os.environ.get("IDENTITY_PROVIDER", "mock")
    
    provider_type = provider_type.lower()
    
    if provider_type == "mock":
        return MockIdentityProvider()
    
    elif provider_type == "github":
        client_id = kwargs.get("client_id") or os.environ.get("GITHUB_CLIENT_ID")
        client_secret = kwargs.get("client_secret") or os.environ.get("GITHUB_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError(
                "GitHub provider requires 'client_id' and 'client_secret' "
                "parameters or GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET "
                "environment variables"
            )
        
        api_base_url = kwargs.get("api_base_url") or os.environ.get(
            "GITHUB_API_BASE_URL",
            "https://api.github.com"
        )
        
        return GitHubIdentityProvider(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=api_base_url
        )
    
    elif provider_type == "datatracker":
        api_base_url = kwargs.get("api_base_url") or os.environ.get(
            "DATATRACKER_API_BASE_URL",
            "https://datatracker.ietf.org/api"
        )
        
        return DatatrackerIdentityProvider(api_base_url=api_base_url)
    
    else:
        raise ValueError(
            f"Unknown identity provider type: {provider_type}. "
            f"Supported types: mock, github, datatracker"
        )
