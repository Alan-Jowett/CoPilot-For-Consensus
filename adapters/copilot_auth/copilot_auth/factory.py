# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating identity providers from typed configuration.

copilot_auth has migrated to schema-driven typed configuration.
The supported providers are defined by the oidc_providers adapter schema:

- github
- google
- microsoft

This adapter intentionally does not provide backward compatibility with the old
"driver_name + DriverConfig" pattern.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from copilot_config.generated.adapters.oidc_providers import (
    AdapterConfig_OidcProviders,
    DriverConfig_OidcProviders_Github,
    DriverConfig_OidcProviders_Google,
    DriverConfig_OidcProviders_Microsoft,
)

from .github_provider import GitHubIdentityProvider
from .google_provider import GoogleIdentityProvider
from .microsoft_provider import MicrosoftIdentityProvider
from .provider import IdentityProvider

ProviderName = Literal["github", "google", "microsoft"]


def create_identity_provider(
    provider_name: ProviderName,
    driver_config: DriverConfig_OidcProviders_Github
    | DriverConfig_OidcProviders_Google
    | DriverConfig_OidcProviders_Microsoft,
    *,
    issuer: str | None = None,
) -> IdentityProvider:
    """Create a single identity provider from typed driver config.

    Args:
        provider_name: Provider name ("github", "google", "microsoft")
        driver_config: Generated driver config dataclass for that provider
        issuer: Optional service issuer used to default redirect URI to "{issuer}/callback"

    Returns:
        IdentityProvider instance
    """
    name = provider_name.lower()
    if name not in ("github", "google", "microsoft"):
        raise ValueError(f"Unknown identity provider: {provider_name}. Supported types: github, google, microsoft")

    default_redirect_uri = f"{issuer.rstrip('/')}/callback" if issuer else None

    if name == "github":
        if not isinstance(driver_config, DriverConfig_OidcProviders_Github):
            raise TypeError("github provider requires DriverConfig_OidcProviders_Github")
        if default_redirect_uri and not driver_config.github_redirect_uri:
            driver_config = replace(driver_config, github_redirect_uri=default_redirect_uri)
        return GitHubIdentityProvider.from_config(driver_config)
    if name == "google":
        if not isinstance(driver_config, DriverConfig_OidcProviders_Google):
            raise TypeError("google provider requires DriverConfig_OidcProviders_Google")
        if default_redirect_uri and not driver_config.google_redirect_uri:
            driver_config = replace(driver_config, google_redirect_uri=default_redirect_uri)
        return GoogleIdentityProvider.from_config(driver_config)
    if name == "microsoft":
        if not isinstance(driver_config, DriverConfig_OidcProviders_Microsoft):
            raise TypeError("microsoft provider requires DriverConfig_OidcProviders_Microsoft")
        if default_redirect_uri and not driver_config.microsoft_redirect_uri:
            driver_config = replace(driver_config, microsoft_redirect_uri=default_redirect_uri)
        return MicrosoftIdentityProvider.from_config(driver_config)

    raise ValueError(f"Unknown identity provider: {provider_name}. Supported types: github, google, microsoft")


def create_identity_providers(
    config: AdapterConfig_OidcProviders,
    *,
    issuer: str | None = None,
) -> dict[str, IdentityProvider]:
    """Create all configured identity providers from a composite adapter config.

    This matches the oidc_providers schema, which allows multiple concurrent providers.
    """
    composite = config.oidc_providers
    if composite is None:
        return {}

    providers: dict[str, IdentityProvider] = {}
    if composite.github is not None:
        providers["github"] = create_identity_provider(
            "github",
            composite.github,
            issuer=issuer,
        )
    if composite.google is not None:
        providers["google"] = create_identity_provider(
            "google",
            composite.google,
            issuer=issuer,
        )
    if composite.microsoft is not None:
        providers["microsoft"] = create_identity_provider(
            "microsoft",
            composite.microsoft,
            issuer=issuer,
        )

    return providers
