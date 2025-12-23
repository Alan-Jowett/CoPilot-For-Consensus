# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Authentication and identity models for Copilot-for-Consensus.

This module defines user identity and authentication models used across
the Copilot-for-Consensus system.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class User:
    """Represents an authenticated user in the system.

    This model encapsulates user identity information retrieved from
    various authentication providers (GitHub OAuth, Datatracker, etc.).

    Attributes:
        id: Unique identifier for the user (provider-specific)
        email: User's email address
        name: User's display name
        roles: List of roles assigned to the user (e.g., ["contributor", "chair"])
        affiliations: List of organizational affiliations (e.g., ["IETF", "W3C"])
    """
    id: str
    email: str
    name: str
    roles: List[str] = field(default_factory=list)
    affiliations: List[str] = field(default_factory=list)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role.

        Args:
            role: Role to check for

        Returns:
            True if user has the role, False otherwise
        """
        return role in self.roles

    def has_affiliation(self, affiliation: str) -> bool:
        """Check if user has a specific affiliation.

        Args:
            affiliation: Affiliation to check for

        Returns:
            True if user has the affiliation, False otherwise
        """
        return affiliation in self.affiliations

    def to_dict(self) -> dict:
        """Convert user to dictionary for serialization.

        Returns:
            Dictionary representation of the user
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "roles": self.roles,
            "affiliations": self.affiliations,
        }
