# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract base class for JWT signing operations."""

from abc import ABC, abstractmethod
from typing import Any


class JWTSigner(ABC):
    """Abstract base class for JWT signing operations.
    
    This interface defines the contract for JWT signing implementations,
    supporting both local file-based signing and cloud-based cryptographic
    operations (e.g., Azure Key Vault).
    
    Attributes:
        algorithm: JWT signing algorithm (e.g., "RS256", "ES256", "HS256")
        key_id: Key identifier for rotation support
    """
    
    def __init__(self, algorithm: str, key_id: str = "default"):
        """Initialize the JWT signer.
        
        Args:
            algorithm: JWT signing algorithm (e.g., "RS256", "ES256", "HS256")
            key_id: Key identifier for key rotation
        """
        self.algorithm = algorithm
        self.key_id = key_id
    
    @abstractmethod
    def sign(self, message: bytes) -> bytes:
        """Sign a message and return the signature.
        
        Args:
            message: Raw message bytes to sign (typically JWT header + payload)
        
        Returns:
            Signature bytes
        
        Raises:
            JWTSignerError: If signing fails
        """
        pass
    
    @abstractmethod
    def get_public_key_jwk(self) -> dict[str, Any]:
        """Get public key in JWK (JSON Web Key) format.
        
        Returns:
            JWK dictionary with public key parameters
            
        Raises:
            JWTSignerError: If public key retrieval fails
        """
        pass
    
    @abstractmethod
    def get_public_key_pem(self) -> str | None:
        """Get public key in PEM format.
        
        Returns:
            Public key in PEM format, or None if not available (e.g., HMAC)
            
        Raises:
            JWTSignerError: If public key retrieval fails
        """
        pass
    
    def health_check(self) -> bool:
        """Perform a health check by attempting a dummy sign operation.
        
        Returns:
            True if the signer is healthy, False otherwise
        """
        try:
            # Try to sign a test message
            test_message = b"health_check"
            signature = self.sign(test_message)
            return len(signature) > 0
        except Exception:
            return False
