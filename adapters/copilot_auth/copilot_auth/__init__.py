# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Authentication Adapter.

A shared library for identity and authentication across microservices
in the Copilot-for-Consensus system. Supports multiple authentication
providers including GitHub OAuth, Google OIDC, Microsoft Entra ID,
IETF Datatracker, and mock providers for testing.
"""

__version__ = "0.2.0"

from .datatracker_provider import DatatrackerIdentityProvider
from .factory import create_identity_provider
from .github_provider import GitHubIdentityProvider
from .google_provider import GoogleIdentityProvider
from .jwt_manager import JWTManager
from .microsoft_provider import MicrosoftIdentityProvider
from .middleware import JWTMiddleware, create_jwt_middleware
from .mock_provider import MockIdentityProvider
from .models import User
from .oidc_provider import OIDCProvider
from .provider import AuthenticationError, IdentityProvider, ProviderError

__all__ = [
    # Version
    "__version__",
    # Models
    "User",
    # Providers
    "IdentityProvider",
    "OIDCProvider",
    "MockIdentityProvider",
    "GitHubIdentityProvider",
    "GoogleIdentityProvider",
    "MicrosoftIdentityProvider",
    "DatatrackerIdentityProvider",
    # JWT
    "JWTManager",
    # Factory
    "create_identity_provider",
    # Exceptions
    "AuthenticationError",
    "ProviderError",
    # Middleware
    "JWTMiddleware",
    "create_jwt_middleware",
]
