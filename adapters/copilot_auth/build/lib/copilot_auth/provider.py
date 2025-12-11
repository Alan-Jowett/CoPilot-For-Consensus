# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract identity provider interface for authentication.

This module defines the contract that all identity providers must implement,
enabling support for multiple authentication strategies (GitHub OAuth,
Datatracker login, email-based auth, etc.) without coupling services to
a specific provider.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .models import User


class IdentityProvider(ABC):
    """Abstract base class for identity providers.
    
    All identity providers must implement the get_user method to retrieve
    user information based on an authentication token.
    """
    
    @abstractmethod
    def get_user(self, token: str) -> Optional[User]:
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


class AuthenticationError(Exception):
    """Raised when authentication fails due to invalid credentials."""
    pass


class ProviderError(Exception):
    """Raised when the identity provider service is unavailable."""
    pass
