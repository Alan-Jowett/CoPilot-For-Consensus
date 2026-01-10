# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract identity provider interface for authentication.

This module defines the contract that all identity providers must implement,
enabling support for multiple authentication strategies (GitHub OAuth,
Datatracker login, email-based auth, etc.) without coupling services to
a specific provider.
"""

from abc import ABC, abstractmethod

from .models import User


class IdentityProvider(ABC):
    """Abstract base class for identity providers.

    All identity providers must implement the get_user method to retrieve
    user information based on an authentication token.
    """

    @abstractmethod
    def get_user(self, token: str) -> User | None:
        """Retrieve user information from an authentication token.

        Args:
            token: Authentication token (format depends on provider)

        Returns:
            User object if token is valid, None otherwise

        Raises:
            AuthenticationError: If authentication fails due to invalid token
            ProviderError: If the provider service is unavailable
        """
        pass

    def validate_and_get_user(self, token_response: dict, nonce: str | None = None) -> User | None:
        """Validate token response and retrieve user info.

        This method encapsulates provider-specific token handling. Default implementation
        uses access_token directly. OIDC providers should override to validate id_token.

        Args:
            token_response: OAuth token response containing access_token and optionally id_token
            nonce: Nonce value for id_token validation (OIDC only)

        Returns:
            User object if validation succeeds, None otherwise

        Raises:
            AuthenticationError: If token validation or user retrieval fails
            ProviderError: If the provider service is unavailable
        """
        # Default implementation: just use access_token
        access_token = token_response.get("access_token")
        if not access_token:
            raise AuthenticationError("No access token in response")
        
        return self.get_user(access_token)


class AuthenticationError(Exception):
    """Raised when authentication fails due to invalid credentials."""
    pass


class ProviderError(Exception):
    """Raised when the identity provider service is unavailable."""
    pass
