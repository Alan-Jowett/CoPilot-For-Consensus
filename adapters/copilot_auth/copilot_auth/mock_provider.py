# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Mock identity provider for testing and local development.

This module provides a simple in-memory identity provider that can be used
for testing and local development without requiring external authentication
services.
"""

from typing import Dict, Optional

from .models import User
from .provider import IdentityProvider, AuthenticationError


class MockIdentityProvider(IdentityProvider):
    """Mock identity provider for testing and local development.
    
    This provider maintains an in-memory dictionary of tokens to users,
    allowing for predictable testing without external dependencies.
    
    Attributes:
        users: Dictionary mapping tokens to User objects
    """
    
    def __init__(self):
        """Initialize the mock provider with an empty user dictionary."""
        self.users: Dict[str, User] = {}
    
    def add_user(self, token: str, user: User) -> None:
        """Add a user to the mock provider.
        
        Args:
            token: Authentication token for this user
            user: User object to associate with the token
        """
        self.users[token] = user
    
    def remove_user(self, token: str) -> None:
        """Remove a user from the mock provider.
        
        Args:
            token: Authentication token to remove
        """
        if token in self.users:
            del self.users[token]
    
    def get_user(self, token: str) -> Optional[User]:
        """Retrieve user information from an authentication token.
        
        Args:
            token: Authentication token
            
        Returns:
            User object if token is valid, None otherwise
            
        Raises:
            AuthenticationError: If token is empty or invalid format
        """
        if not token or not isinstance(token, str):
            raise AuthenticationError("Invalid token format")
        
        return self.users.get(token)
    
    def clear(self) -> None:
        """Clear all users from the provider."""
        self.users.clear()
