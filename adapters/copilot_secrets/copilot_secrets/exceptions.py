# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Exceptions for secret management."""


class SecretError(Exception):
    """Base exception for secret management errors."""
    pass


class SecretNotFoundError(SecretError):
    """Raised when a requested secret does not exist."""
    pass


class SecretProviderError(SecretError):
    """Raised when the secret provider encounters an error."""
    pass
