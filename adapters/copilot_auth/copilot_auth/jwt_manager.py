# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""JWT token minting and validation for local authentication.

This module provides JWT token generation and validation functionality,
supporting both RSA and HMAC signing algorithms with key rotation.

Now supports pluggable signing backends via copilot_jwt_signer adapter,
enabling local file-based signing or Azure Key Vault cryptographic operations.
"""

import base64
import json
import secrets
import time
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from .models import User

# Type alias for keys that can be used with jwt.encode/decode
JWTKeyType = RSAPrivateKey | RSAPublicKey | str


class JWTManager:
    """Manages JWT token minting, validation, and key management.

    Supports pluggable signing backends via copilot_jwt_signer adapter:
    - Local file-based signing (RSA, EC, HMAC)
    - Azure Key Vault cryptographic operations (RSA, EC)

    Provides key rotation via key ID (kid) in JWT header.

    Attributes:
        issuer: Token issuer (auth service URL)
        algorithm: JWT signing algorithm
        signer: JWT signer instance (from copilot_jwt_signer)
        public_key: Public key for validation (for backward compatibility)
        key_id: Current key ID for rotation
        default_expiry: Default token lifetime in seconds
        use_signer: Whether to use the new signer interface (True) or legacy PyJWT (False)
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
        signer: "JWTSigner | None" = None,  # Optional: JWTSigner instance from copilot_jwt_signer
    ):
        """Initialize JWT manager.

        Args:
            issuer: Token issuer identifier
            algorithm: Signing algorithm ("RS256", "HS256", etc.)
            private_key_path: Path to RSA private key (for RS256, legacy mode)
            public_key_path: Path to RSA public key (for RS256, legacy mode)
            secret_key: HMAC secret (for HS256, legacy mode)
            key_id: Key identifier for rotation
            default_expiry: Default token lifetime in seconds
            signer: Optional JWTSigner instance (enables Key Vault signing)

        Raises:
            ValueError: If algorithm is unsupported or keys are missing
        """
        self.issuer = issuer
        self.algorithm = algorithm
        self.default_expiry = default_expiry
        self.key_id = key_id or "default"
        # Use signer if provided, otherwise fall back to legacy mode
        self.signer = signer
        self.use_signer = signer is not None

        self.private_key: JWTKeyType | None = None
        self.public_key: JWTKeyType | None = None

        if not self.use_signer:
            # Legacy mode: load keys directly
            # Keys can be either RSA objects or strings (for HS256)

            if algorithm == "RS256":
                if not private_key_path or not public_key_path:
                    raise ValueError("RS256 requires both private_key_path and public_key_path")

                # Load RSA keys
                with open(private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(  # type: ignore[assignment]
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )

                with open(public_key_path, "rb") as f:
                    self.public_key = serialization.load_pem_public_key(  # type: ignore[assignment]
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
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size, backend=default_backend())

        # Write private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        private_key_path.write_bytes(private_pem)

        # Write public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
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

        # Build JWT header
        headers = {"kid": self.key_id, "alg": self.algorithm, "typ": "JWT"}

        if self.use_signer:
            # New mode: use signer adapter to sign
            return self._mint_token_with_signer(headers, claims)

        if self.private_key is None:
            raise ValueError("Private key not configured")

        # Legacy mode: use PyJWT
        return jwt.encode(
            claims,
            self.private_key,  # type: ignore[arg-type]
            algorithm=self.algorithm,
            headers=headers,
        )

    def _mint_token_with_signer(self, headers: dict[str, Any], claims: dict[str, Any]) -> str:
        """Mint a JWT token using the signer adapter.
        
        Args:
            headers: JWT header dictionary
            claims: JWT claims dictionary
            
        Returns:
            Signed JWT token string
            
        Note:
            Uses json.dumps with compact separators (separators=(',', ':')) and
            base64url encoding to follow the JWT compact serialization defined in
            RFC 7519. This ensures interoperability with standard JWT libraries
            for token verification.
            
            Claims should contain only JSON-serializable primitive types (strings,
            numbers, booleans, lists, dicts, None). For timestamps, use integer 
            Unix timestamps (seconds since epoch) as per JWT standard. The current
            implementation uses standard claim types (int, str, list) which are
            fully compatible with PyJWT and other JWT libraries.
        """
        # Encode header and payload as base64url
        header_b64 = self._base64url_encode(json.dumps(headers, separators=(',', ':')).encode('utf-8'))
        payload_b64 = self._base64url_encode(json.dumps(claims, separators=(',', ':')).encode('utf-8'))
        
        # Create signing input (header.payload)
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        
        # Sign using the signer
        signature = self.signer.sign(signing_input)
        
        # Encode signature as base64url
        signature_b64 = self._base64url_encode(signature)
        
        # Assemble final JWT (header.payload.signature)
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        """Encode bytes as base64url without padding."""
        return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')

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
        if self.use_signer:
            # New mode: get public key from signer for validation
            # For signer mode, we still use PyJWT for validation but get the public key from signer
            public_key_pem = self.signer.get_public_key_pem()
            if public_key_pem:
                # Load public key for validation
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
            else:
                # HMAC or other symmetric algorithm - get from signer
                # For HMAC, the signer should provide the secret
                raise jwt.InvalidTokenError(
                    "Cannot validate tokens signed with symmetric algorithms in signer mode"
                )
            
            return jwt.decode(  # type: ignore[no-any-return]
                token,
                public_key,  # type: ignore[arg-type]
                algorithms=[self.algorithm],
                audience=audience,
                issuer=self.issuer,
                leeway=max_skew_seconds,
            )
        else:
            # Legacy mode: use stored public key
            return jwt.decode(  # type: ignore[no-any-return]
                token,
                self.public_key,  # type: ignore[arg-type]
                algorithms=[self.algorithm],
                audience=audience,
                issuer=self.issuer,
                leeway=max_skew_seconds,
            )

    def get_jwks(self) -> dict[str, Any]:
        """Get JSON Web Key Set (JWKS) for token validation.

        Returns RSA/EC public key in JWK format, or empty for HMAC
        (HMAC secrets should not be published).

        Returns:
            JWKS dictionary with public keys
        """
        if self.use_signer:
            # New mode: get JWKS from signer
            jwk = self.signer.get_public_key_jwk()
            if jwk:
                return {"keys": [jwk]}
            return {"keys": []}
        else:
            # Legacy mode: construct JWKS from stored public key
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

    def get_public_key_pem(self) -> str | None:
        """Get public key in PEM format for external services.
        
        Returns public key as PEM-encoded string for RS256/EC, or None for HS256
        (HMAC secrets should not be published).
        
        Returns:
            Public key in PEM format, or None if not available
        """
        if self.use_signer:
            # New mode: get PEM from signer
            return self.signer.get_public_key_pem()

        # Legacy mode: export from stored public key
        if self.algorithm != "RS256":
            return None

        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

        if not isinstance(self.public_key, RSAPublicKey):
            return None

        # Export public key to PEM format
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return pem.decode("utf-8")

    @staticmethod
    def _int_to_base64url(value: int) -> str:
        """Convert integer to base64url-encoded string."""
        import base64

        # Convert to bytes
        byte_length = (value.bit_length() + 7) // 8
        value_bytes = value.to_bytes(byte_length, byteorder="big")

        # Encode to base64url
        return base64.urlsafe_b64encode(value_bytes).decode("ascii").rstrip("=")
