# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Exceptions for JWT signing operations."""


class JWTSignerError(Exception):
    """Base exception for JWT signing errors."""
    pass


class KeyVaultSignerError(JWTSignerError):
    """Exception for Key Vault signing errors."""
    pass


class SigningTimeoutError(JWTSignerError):
    """Exception raised when signing operation times out."""
    pass


class CircuitBreakerOpenError(JWTSignerError):
    """Exception raised when circuit breaker is open."""
    pass
