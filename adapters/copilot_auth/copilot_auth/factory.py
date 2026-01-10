# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating identity providers based on configuration.

This module provides a factory function to create identity provider instances
based on driver configuration, enabling easy switching between authentication
strategies.
"""

from copilot_config import DriverConfig

from .datatracker_provider import DatatrackerIdentityProvider
from .github_provider import GitHubIdentityProvider
from .google_provider import GoogleIdentityProvider
from .microsoft_provider import MicrosoftIdentityProvider
from .mock_provider import MockIdentityProvider
from .provider import IdentityProvider


def create_identity_provider(
    driver_name: str,
    driver_config: DriverConfig
) -> IdentityProvider:
    """Create an identity provider from DriverConfig.

    Args:
        driver_name: Type of provider ("mock", "github", "google", "microsoft", "datatracker")
        driver_config: DriverConfig object with provider configuration

    Returns:
        IdentityProvider instance

    Raises:
        ValueError: If driver_name is unknown

    Examples:
        >>> from copilot_config import load_driver_config
        >>> driver_config = load_driver_config("auth", "identity_provider", "github", {...})
        >>> provider = create_identity_provider("github", driver_config)
    """
    if not driver_name:
        raise ValueError(
            "driver_name parameter is required. "
            "Must be one of: mock, github, google, microsoft, datatracker"
        )

    driver_name = driver_name.lower()

    if driver_name == "mock":
        return MockIdentityProvider.from_config(driver_config)
    elif driver_name == "github":
        return GitHubIdentityProvider.from_config(driver_config)
    elif driver_name == "google":
        return GoogleIdentityProvider.from_config(driver_config)
    elif driver_name == "microsoft":
        return MicrosoftIdentityProvider.from_config(driver_config)
    elif driver_name == "datatracker":
        return DatatrackerIdentityProvider.from_config(driver_config)
    else:
        raise ValueError(
            f"Unknown identity provider driver: {driver_name}. "
            f"Supported types: mock, github, google, microsoft, datatracker"
        )
