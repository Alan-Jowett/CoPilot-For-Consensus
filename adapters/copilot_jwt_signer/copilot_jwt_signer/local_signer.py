# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local file-based JWT signing implementation."""

import base64
import hashlib
import hmac
from pathlib import Path
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .exceptions import JWTSignerError
from .signer import JWTSigner


class LocalJWTSigner(JWTSigner):
    """Local file-based JWT signer for RSA and EC keys.

    This signer loads private keys from PEM files and performs signing
    operations locally. It supports:
    - RSA algorithms: RS256, RS384, RS512
    - EC algorithms: ES256, ES384, ES512
    - HMAC algorithms: HS256, HS384, HS512

    For production deployments, consider using KeyVaultJWTSigner to avoid
    storing private keys on disk.

    Attributes:
        algorithm: JWT signing algorithm
        key_id: Key identifier for rotation
        private_key: Private key object (RSA, EC, or HMAC secret)
        public_key: Public key object (RSA or EC only)
    """

    def __init__(
        self,
        algorithm: str,
        private_key_path: Path | str | None = None,
        public_key_path: Path | str | None = None,
        secret_key: str | None = None,
        key_id: str = "default",
    ):
        """Initialize local JWT signer.

        Args:
            algorithm: Signing algorithm (RS256, RS384, RS512, ES256, ES384, ES512, HS256, HS384, HS512)
            private_key_path: Path to RSA/EC private key (for asymmetric algorithms)
            public_key_path: Path to RSA/EC public key (for asymmetric algorithms)
            secret_key: HMAC secret (for symmetric algorithms)
            key_id: Key identifier for rotation

        Raises:
            JWTSignerError: If algorithm is unsupported or keys are missing
        """
        super().__init__(algorithm, key_id)

        if algorithm.startswith("RS") or algorithm.startswith("ES"):
            # Asymmetric algorithms require key files
            if not private_key_path or not public_key_path:
                raise JWTSignerError(
                    f"{algorithm} requires both private_key_path and public_key_path"
                )

            self._load_asymmetric_keys(private_key_path, public_key_path)

        elif algorithm.startswith("HS"):
            # Symmetric algorithms use HMAC secret
            if not secret_key:
                raise JWTSignerError(f"{algorithm} requires secret_key")

            self.private_key = secret_key
            self.public_key = secret_key

        else:
            raise JWTSignerError(
                f"Unsupported algorithm: {algorithm}. "
                f"Supported: RS256, RS384, RS512, ES256, ES384, ES512, HS256, HS384, HS512"
            )

    def _load_asymmetric_keys(self, private_key_path: Path | str, public_key_path: Path | str) -> None:
        """Load RSA or EC keys from PEM files.

        Args:
            private_key_path: Path to private key PEM file
            public_key_path: Path to public key PEM file

        Raises:
            JWTSignerError: If keys cannot be loaded
        """
        try:
            # Load private key
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )

            # Load public key
            with open(public_key_path, "rb") as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )

            # Validate key type matches algorithm
            if self.algorithm.startswith("RS"):
                if not isinstance(self.private_key, RSAPrivateKey):
                    raise JWTSignerError(f"Private key must be RSA for {self.algorithm}")
            elif self.algorithm.startswith("ES"):
                if not isinstance(self.private_key, EllipticCurvePrivateKey):
                    raise JWTSignerError(f"Private key must be EC for {self.algorithm}")

        except FileNotFoundError as e:
            raise JWTSignerError(f"Key file not found: {e}") from e
        except Exception as e:
            raise JWTSignerError(f"Failed to load keys: {e}") from e

    def sign(self, message: bytes) -> bytes:
        """Sign a message using the loaded private key.

        Args:
            message: Raw message bytes to sign

        Returns:
            Signature bytes

        Raises:
            JWTSignerError: If signing fails
        """
        try:
            if self.algorithm.startswith("RS"):
                return self._sign_rsa(message)
            if self.algorithm.startswith("ES"):
                return self._sign_ec(message)
            if self.algorithm.startswith("HS"):
                return self._sign_hmac(message)

            raise JWTSignerError(f"Unsupported algorithm: {self.algorithm}")

        except JWTSignerError:
            raise
        except Exception as e:
            raise JWTSignerError(f"Signing failed: {e}") from e

    def _sign_rsa(self, message: bytes) -> bytes:
        """Sign message using RSA algorithm.

        Args:
            message: Message bytes to sign

        Returns:
            RSA signature bytes
        """
        # Select hash algorithm based on variant
        if self.algorithm == "RS256":
            hash_algo = hashes.SHA256()
        elif self.algorithm == "RS384":
            hash_algo = hashes.SHA384()
        elif self.algorithm == "RS512":
            hash_algo = hashes.SHA512()
        else:
            raise JWTSignerError(f"Unsupported RSA algorithm: {self.algorithm}")

        return self.private_key.sign(
            message,
            padding.PKCS1v15(),
            hash_algo
        )

    def _sign_ec(self, message: bytes) -> bytes:
        """Sign message using EC algorithm.

        Args:
            message: Message bytes to sign

        Returns:
            EC signature bytes
        """
        # Select hash algorithm based on variant
        if self.algorithm == "ES256":
            hash_algo = hashes.SHA256()
        elif self.algorithm == "ES384":
            hash_algo = hashes.SHA384()
        elif self.algorithm == "ES512":
            hash_algo = hashes.SHA512()
        else:
            raise JWTSignerError(f"Unsupported EC algorithm: {self.algorithm}")

        return self.private_key.sign(
            message,
            ec.ECDSA(hash_algo)
        )

    def _sign_hmac(self, message: bytes) -> bytes:
        """Sign message using HMAC algorithm.

        Args:
            message: Message bytes to sign

        Returns:
            HMAC signature bytes
        """
        # Select hash algorithm based on variant
        if self.algorithm == "HS256":
            hash_func = hashlib.sha256
        elif self.algorithm == "HS384":
            hash_func = hashlib.sha384
        elif self.algorithm == "HS512":
            hash_func = hashlib.sha512
        else:
            raise JWTSignerError(f"Unsupported HMAC algorithm: {self.algorithm}")

        return hmac.new(
            self.private_key.encode("utf-8"),
            message,
            hash_func
        ).digest()

    def get_public_key_jwk(self) -> dict[str, Any]:
        """Get public key in JWK format.

        Returns:
            JWK dictionary with public key parameters

        Raises:
            JWTSignerError: If public key retrieval fails
        """
        if self.algorithm.startswith("HS"):
            # HMAC secrets should not be published
            return {}

        try:
            if self.algorithm.startswith("RS"):
                return self._get_rsa_jwk()
            if self.algorithm.startswith("ES"):
                return self._get_ec_jwk()

            raise JWTSignerError(f"Unsupported algorithm for JWK: {self.algorithm}")

        except JWTSignerError:
            raise
        except Exception as e:
            raise JWTSignerError(f"Failed to get public key JWK: {e}") from e

    def _get_rsa_jwk(self) -> dict[str, Any]:
        """Get RSA public key in JWK format."""
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

        if not isinstance(self.public_key, RSAPublicKey):
            raise JWTSignerError("Public key is not RSA")

        # Get public numbers
        public_numbers = self.public_key.public_numbers()

        return {
            "kty": "RSA",
            "use": "sig",
            "kid": self.key_id,
            "alg": self.algorithm,
            "n": self._int_to_base64url(public_numbers.n),
            "e": self._int_to_base64url(public_numbers.e),
        }

    def _get_ec_jwk(self) -> dict[str, Any]:
        """Get EC public key in JWK format."""
        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey

        if not isinstance(self.public_key, EllipticCurvePublicKey):
            raise JWTSignerError("Public key is not EC")

        # Get public numbers
        public_numbers = self.public_key.public_numbers()

        # Map curve to JWK curve name
        curve_name = public_numbers.curve.name
        if curve_name == "secp256r1":
            crv = "P-256"
        elif curve_name == "secp384r1":
            crv = "P-384"
        elif curve_name == "secp521r1":
            crv = "P-521"
        else:
            raise JWTSignerError(f"Unsupported EC curve: {curve_name}")

        return {
            "kty": "EC",
            "use": "sig",
            "kid": self.key_id,
            "alg": self.algorithm,
            "crv": crv,
            "x": self._int_to_base64url(public_numbers.x),
            "y": self._int_to_base64url(public_numbers.y),
        }

    @staticmethod
    def _int_to_base64url(value: int) -> str:
        """Convert integer to base64url-encoded string."""
        # Convert to bytes
        byte_length = (value.bit_length() + 7) // 8
        value_bytes = value.to_bytes(byte_length, byteorder='big')

        # Encode to base64url
        return base64.urlsafe_b64encode(value_bytes).decode('ascii').rstrip('=')

    def get_public_key_pem(self) -> str | None:
        """Get public key in PEM format.

        Returns:
            Public key in PEM format, or None if not available (HMAC)

        Raises:
            JWTSignerError: If public key retrieval fails
        """
        if self.algorithm.startswith("HS"):
            # HMAC secrets should not be published
            return None

        try:
            pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            return pem.decode('utf-8')

        except Exception as e:
            raise JWTSignerError(f"Failed to get public key PEM: {e}") from e
