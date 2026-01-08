# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for LocalJWTSigner."""

import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from copilot_jwt_signer import LocalJWTSigner
from copilot_jwt_signer.exceptions import JWTSignerError


class TestLocalJWTSignerRSA:
    """Tests for LocalJWTSigner with RSA keys."""

    @pytest.fixture
    def rsa_key_pair(self):
        """Generate an RSA key pair for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Write to temp files
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            f.write(private_pem)
            private_path = f.name
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            f.write(public_pem)
            public_path = f.name
        
        yield private_path, public_path
        
        # Cleanup
        Path(private_path).unlink(missing_ok=True)
        Path(public_path).unlink(missing_ok=True)

    def test_initialize_rs256_signer(self, rsa_key_pair):
        """Test initializing LocalJWTSigner with RS256."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path,
            key_id="test-key"
        )
        
        assert signer.algorithm == "RS256"
        assert signer.key_id == "test-key"
        assert signer.private_key is not None
        assert signer.public_key is not None

    def test_sign_message_rs256(self, rsa_key_pair):
        """Test signing a message with RS256."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_sign_different_messages_produces_different_signatures(self, rsa_key_pair):
        """Test that different messages produce different signatures."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path
        )
        
        sig1 = signer.sign(b"message 1")
        sig2 = signer.sign(b"message 2")
        
        assert sig1 != sig2

    def test_get_public_key_jwk_rs256(self, rsa_key_pair):
        """Test getting public key in JWK format for RS256."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path,
            key_id="test-key-123"
        )
        
        jwk = signer.get_public_key_jwk()
        
        assert jwk["kty"] == "RSA"
        assert jwk["use"] == "sig"
        assert jwk["kid"] == "test-key-123"
        assert jwk["alg"] == "RS256"
        assert "n" in jwk
        assert "e" in jwk

    def test_get_public_key_pem_rs256(self, rsa_key_pair):
        """Test getting public key in PEM format for RS256."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path
        )
        
        pem = signer.get_public_key_pem()
        
        assert pem is not None
        assert "-----BEGIN PUBLIC KEY-----" in pem
        assert "-----END PUBLIC KEY-----" in pem

    def test_health_check_succeeds(self, rsa_key_pair):
        """Test health check succeeds for working signer."""
        private_path, public_path = rsa_key_pair
        
        signer = LocalJWTSigner(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path
        )
        
        assert signer.health_check() is True

    def test_missing_private_key_raises_error(self, rsa_key_pair):
        """Test that missing private key raises error."""
        _, public_path = rsa_key_pair
        
        with pytest.raises(JWTSignerError, match="requires both"):
            LocalJWTSigner(
                algorithm="RS256",
                private_key_path=None,
                public_key_path=public_path
            )

    def test_missing_public_key_raises_error(self, rsa_key_pair):
        """Test that missing public key raises error."""
        private_path, _ = rsa_key_pair
        
        with pytest.raises(JWTSignerError, match="requires both"):
            LocalJWTSigner(
                algorithm="RS256",
                private_key_path=private_path,
                public_key_path=None
            )


class TestLocalJWTSignerEC:
    """Tests for LocalJWTSigner with EC keys."""

    @pytest.fixture
    def ec_key_pair(self):
        """Generate an EC key pair for testing."""
        private_key = ec.generate_private_key(
            ec.SECP256R1(),
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Write to temp files
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            f.write(private_pem)
            private_path = f.name
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            f.write(public_pem)
            public_path = f.name
        
        yield private_path, public_path
        
        # Cleanup
        Path(private_path).unlink(missing_ok=True)
        Path(public_path).unlink(missing_ok=True)

    def test_initialize_es256_signer(self, ec_key_pair):
        """Test initializing LocalJWTSigner with ES256."""
        private_path, public_path = ec_key_pair
        
        signer = LocalJWTSigner(
            algorithm="ES256",
            private_key_path=private_path,
            public_key_path=public_path,
            key_id="test-ec-key"
        )
        
        assert signer.algorithm == "ES256"
        assert signer.key_id == "test-ec-key"

    def test_sign_message_es256(self, ec_key_pair):
        """Test signing a message with ES256."""
        private_path, public_path = ec_key_pair
        
        signer = LocalJWTSigner(
            algorithm="ES256",
            private_key_path=private_path,
            public_key_path=public_path
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_get_public_key_jwk_es256(self, ec_key_pair):
        """Test getting public key in JWK format for ES256."""
        private_path, public_path = ec_key_pair
        
        signer = LocalJWTSigner(
            algorithm="ES256",
            private_key_path=private_path,
            public_key_path=public_path,
            key_id="test-ec-key"
        )
        
        jwk = signer.get_public_key_jwk()
        
        assert jwk["kty"] == "EC"
        assert jwk["use"] == "sig"
        assert jwk["kid"] == "test-ec-key"
        assert jwk["alg"] == "ES256"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk


class TestLocalJWTSignerHMAC:
    """Tests for LocalJWTSigner with HMAC."""

    def test_initialize_hs256_signer(self):
        """Test initializing LocalJWTSigner with HS256."""
        signer = LocalJWTSigner(
            algorithm="HS256",
            secret_key="my-secret-key",
            key_id="test-hmac-key"
        )
        
        assert signer.algorithm == "HS256"
        assert signer.key_id == "test-hmac-key"

    def test_sign_message_hs256(self):
        """Test signing a message with HS256."""
        signer = LocalJWTSigner(
            algorithm="HS256",
            secret_key="my-secret-key"
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_same_message_same_signature_hs256(self):
        """Test that same message produces same signature (HMAC is deterministic)."""
        signer = LocalJWTSigner(
            algorithm="HS256",
            secret_key="my-secret-key"
        )
        
        message = b"test message"
        sig1 = signer.sign(message)
        sig2 = signer.sign(message)
        
        assert sig1 == sig2

    def test_get_public_key_jwk_hs256_returns_empty(self):
        """Test that HMAC returns empty JWK (secrets should not be published)."""
        signer = LocalJWTSigner(
            algorithm="HS256",
            secret_key="my-secret-key"
        )
        
        jwk = signer.get_public_key_jwk()
        
        assert jwk == {}

    def test_get_public_key_pem_hs256_returns_none(self):
        """Test that HMAC returns None for PEM (secrets should not be published)."""
        signer = LocalJWTSigner(
            algorithm="HS256",
            secret_key="my-secret-key"
        )
        
        pem = signer.get_public_key_pem()
        
        assert pem is None

    def test_missing_secret_key_raises_error(self):
        """Test that missing secret key raises error."""
        with pytest.raises(JWTSignerError, match="requires secret_key"):
            LocalJWTSigner(
                algorithm="HS256",
                secret_key=None
            )


class TestLocalJWTSignerErrors:
    """Tests for error handling in LocalJWTSigner."""

    def test_unsupported_algorithm_raises_error(self):
        """Test that unsupported algorithm raises error."""
        with pytest.raises(JWTSignerError, match="Unsupported algorithm"):
            LocalJWTSigner(
                algorithm="PS256",  # Not supported
                secret_key="test"
            )

    def test_nonexistent_key_file_raises_error(self):
        """Test that nonexistent key file raises error."""
        with pytest.raises(JWTSignerError, match="Key file not found"):
            LocalJWTSigner(
                algorithm="RS256",
                private_key_path="/nonexistent/private.pem",
                public_key_path="/nonexistent/public.pem"
            )
