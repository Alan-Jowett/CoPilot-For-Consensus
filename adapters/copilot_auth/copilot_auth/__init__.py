# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Authentication Adapter.

A shared library for identity and authentication across microservices
in the Copilot-for-Consensus system. Supports multiple authentication
providers including GitHub OAuth, IETF Datatracker, and mock providers
for testing.
"""

__version__ = "0.1.0"

from .models import User
from .provider import IdentityProvider, AuthenticationError, ProviderError
from .mock_provider import MockIdentityProvider
from .github_provider import GitHubIdentityProvider
from .datatracker_provider import DatatrackerIdentityProvider
from .factory import create_identity_provider

__all__ = [
    # Version
    "__version__",
    # Models
    "User",
    # Providers
    "IdentityProvider",
    "MockIdentityProvider",
    "GitHubIdentityProvider",
    "DatatrackerIdentityProvider",
    # Factory
    "create_identity_provider",
    # Exceptions
    "AuthenticationError",
    "ProviderError",
]
