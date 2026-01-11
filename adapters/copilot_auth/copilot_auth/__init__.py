# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Authentication Adapter.

A shared library for identity and authentication across microservices
in the Copilot-for-Consensus system.

Minimal exports - services should use create_identity_provider():

    from copilot_config import load_service_config
    from copilot_auth import create_identity_provider

    config = load_service_config("auth")
    auth_adapter = config.get_adapter("identity_provider")
    provider = create_identity_provider(auth_adapter.driver_name, auth_adapter.driver_config)
"""

__version__ = "0.2.0"

from .factory import create_identity_provider
from .jwt_manager import JWTManager
from .middleware import JWTMiddleware, create_jwt_middleware
from .models import User
from .provider import AuthenticationError, IdentityProvider, ProviderError

__all__ = [
    # Factory function (all services should use this)
    "create_identity_provider",
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
