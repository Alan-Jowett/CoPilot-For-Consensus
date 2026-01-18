# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service application package."""

__version__ = "0.1.0"

# Supported authentication providers.
# All current providers use OAuth and require credentials (client ID and secret).
SUPPORTED_PROVIDERS = ["github", "google", "microsoft"]

# Alias for OAuth-based providers.
# Kept for semantic clarity in error messages and potential future distinction
# if non-OAuth providers (e.g., SAML, LDAP) are introduced.
OAUTH_PROVIDERS = SUPPORTED_PROVIDERS
