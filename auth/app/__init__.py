# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service application package."""

__version__ = "0.1.0"

# Supported authentication providers
SUPPORTED_PROVIDERS = ["github", "google", "microsoft"]

# Providers that need OAuth configuration guidance
# All providers require OAuth credentials (client ID and secret)
OAUTH_PROVIDERS = ["github", "google", "microsoft"]

