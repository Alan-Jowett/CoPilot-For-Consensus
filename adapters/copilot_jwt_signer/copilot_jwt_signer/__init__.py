# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""JWT signing adapter for Copilot-for-Consensus.

This adapter provides abstraction for JWT signing operations,
supporting both local signing (file-based keys) and Azure Key Vault
cryptographic operations.
"""

from .exceptions import JWTSignerError, KeyVaultSignerError
from .factory import create_jwt_signer
from .local_signer import LocalJWTSigner
from .signer import JWTSigner

__all__ = [
    "JWTSigner",
    "LocalJWTSigner",
    "create_jwt_signer",
    "JWTSignerError",
    "KeyVaultSignerError",
]

# Conditionally export Key Vault signer if Azure dependencies are available
try:
    from .keyvault_signer import KeyVaultJWTSigner
    __all__.append("KeyVaultJWTSigner")
except ImportError:
    # Azure dependencies not installed, KeyVaultJWTSigner not available
    pass
