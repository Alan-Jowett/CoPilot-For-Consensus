# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""JWT token minting and validation for local authentication.

This module provides JWT token generation and validation functionality,
supporting both RSA and HMAC signing algorithms with key rotation.
"""

import secrets
import time
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .models import User


class JWTManager:
    """Manages JWT token minting, validation, and key management.

    Supports RSA256 (recommended) and HS256 (dev only) algorithms.
    Provides key rotation via key ID (kid) in JWT header.

    Attributes:
        issuer: Token issuer (auth service URL)
        algorithm: JWT signing algorithm ("RS256" or "HS256")
        private_key: Private key for signing (RSA or HMAC secret)
        public_key: Public key for validation (RSA only)
        key_id: Current key ID for rotation
        default_expiry: Default token lifetime in seconds
    """

    def __init__(
        self,
        issuer: str,
        algorithm: str = "RS256",
        private_key_path: Path | None = None,
        public_key_path: Path | None = None,
        secret_key: str | None = None,
        key_id: str | None = None,
        default_expiry: int = 1800,  # 30 minutes
    ):
        """Initialize JWT manager.

        Args:
            issuer: Token issuer identifier
            algorithm: Signing algorithm ("RS256" or "HS256")
            private_key_path: Path to RSA private key (for RS256)
            public_key_path: Path to RSA public key (for RS256)
            secret_key: HMAC secret (for HS256)
            key_id: Key identifier for rotation
            default_expiry: Default token lifetime in seconds

        Raises:
            ValueError: If algorithm is unsupported or keys are missing
        """
        self.issuer = issuer
        self.algorithm = algorithm
        self.default_expiry = default_expiry
        self.key_id = key_id or "default"

        if algorithm == "RS256":
            if not private_key_path or not public_key_path:
                raise ValueError("RS256 requires both private_key_path and public_key_path")

            # Load RSA keys
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )

            with open(public_key_path, "rb") as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )

        elif algorithm == "HS256":
            if not secret_key:
                raise ValueError("HS256 requires secret_key")

            self.private_key = secret_key
            self.public_key = secret_key

        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Use 'RS256' or 'HS256'")

    @staticmethod
    def generate_rsa_keys(
        private_key_path: Path,
        public_key_path: Path,
        key_size: int = 2048,
    ) -> None:
        """Generate RSA key pair for JWT signing.

        Args:
            private_key_path: Output path for private key
            public_key_path: Output path for public key
            key_size: RSA key size in bits (default: 2048)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )

        # Write private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_key_path.write_bytes(private_pem)

        # Write public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_key_path.write_bytes(public_pem)

    def mint_token(
        self,
        user: User,
        audience: str,
        expires_in: int | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Mint a JWT token for a user.

        Args:
            user: User to issue token for
            audience: Token audience (target service)
            expires_in: Token lifetime in seconds (default: self.default_expiry)
            additional_claims: Additional claims to include

        Returns:
            Signed JWT token string
        """
        now = int(time.time())
        expiry = expires_in or self.default_expiry

        # Build standard claims
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "sub": user.id,  # User ID already has provider prefix (e.g., "github:12345")
            "aud": audience,
            "exp": now + expiry,
            "iat": now,
            "nbf": now,
            "jti": secrets.token_urlsafe(16),
        }

        # Add identity claims
        claims["email"] = user.email
        claims["name"] = user.name

        # Add roles and affiliations
        if user.roles:
            claims["roles"] = user.roles

        if user.affiliations:
            claims["affiliations"] = user.affiliations

        # Add additional claims
        if additional_claims:
            claims.update(additional_claims)

        # Encode JWT with key ID in header
        headers = {"kid": self.key_id}

        return jwt.encode(
            claims,
            self.private_key,
            algorithm=self.algorithm,
            headers=headers
        )

    def validate_token(
        self,
        token: str,
        audience: str,
        max_skew_seconds: int = 90,
    ) -> dict[str, Any]:
        """Validate and decode a JWT token.

        Args:
            token: JWT token string
            audience: Expected audience
            max_skew_seconds: Clock skew tolerance in seconds

        Returns:
            Decoded token claims

        Raises:
            jwt.InvalidTokenError: If token is invalid, expired, or has wrong audience
        """
        return jwt.decode(
            token,
            self.public_key,
            algorithms=[self.algorithm],
            audience=audience,
            issuer=self.issuer,
            leeway=max_skew_seconds,
        )

    def get_jwks(self) -> dict[str, Any]:
        """Get JSON Web Key Set (JWKS) for token validation.

        Returns RSA public key in JWK format for RS256, or empty for HS256
        (HMAC secrets should not be published).

        Returns:
            JWKS dictionary with public keys
        """
        if self.algorithm != "RS256":
            return {"keys": []}

        # Export public key to JWK format
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

        if not isinstance(self.public_key, RSAPublicKey):
            return {"keys": []}

        # Get public numbers
        public_numbers = self.public_key.public_numbers()

        # Convert to JWK
        jwk = {
            "kty": "RSA",
            "use": "sig",
            "kid": self.key_id,
            "alg": self.algorithm,
            "n": self._int_to_base64url(public_numbers.n),
            "e": self._int_to_base64url(public_numbers.e),
        }

        return {"keys": [jwk]}

    @staticmethod
    def _int_to_base64url(value: int) -> str:
        """Convert integer to base64url-encoded string."""
        import base64

        # Convert to bytes
        byte_length = (value.bit_length() + 7) // 8
        value_bytes = value.to_bytes(byte_length, byteorder='big')

        # Encode to base64url
        return base64.urlsafe_b64encode(value_bytes).decode('ascii').rstrip('=')
