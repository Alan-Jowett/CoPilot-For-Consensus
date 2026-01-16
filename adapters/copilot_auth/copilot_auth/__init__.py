# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Authentication Adapter.

A shared library for identity and authentication across microservices
in the Copilot-for-Consensus system.

Minimal exports.

This adapter has migrated to schema-driven typed configuration via the
`oidc_providers` adapter schema. The factory functions now take generated
dataclasses from `copilot_config.generated.adapters.oidc_providers`.
"""

__version__ = "0.2.0"

from .factory import create_identity_provider, create_identity_providers
from .jwt_manager import JWTManager
from .middleware import JWTMiddleware, create_jwt_middleware
from .models import User
from .provider import AuthenticationError, IdentityProvider, ProviderError

__all__ = [
    # Factory function (all services should use this)
    "create_identity_provider",
    "create_identity_providers",
    # Base class (for type hints)
    "IdentityProvider",
    # JWT components
    "JWTManager",
    "JWTMiddleware",
    "create_jwt_middleware",
    # Models
    "User",
    # Exceptions (for error handling)
    "AuthenticationError",
    "ProviderError",
]
