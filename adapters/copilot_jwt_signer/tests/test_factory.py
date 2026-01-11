# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT signer factory."""

import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from copilot_jwt_signer import LocalJWTSigner, create_jwt_signer
from copilot_jwt_signer.exceptions import JWTSignerError


class TestCreateJWTSigner:
    """Tests for create_jwt_signer factory function."""

    @pytest.fixture
    def rsa_key_files(self):
        """Create temporary RSA key files for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            f.write(private_pem)
            private_path = f.name
        
        public_key = private_key.public_key()
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            f.write(public_pem)
            public_path = f.name
        
        yield private_path, public_path
        
        Path(private_path).unlink(missing_ok=True)
        Path(public_path).unlink(missing_ok=True)

    def test_create_local_rsa_signer(self, rsa_key_files):
        """Test creating a local RSA signer."""
        private_path, public_path = rsa_key_files
        
        signer = create_jwt_signer(
            signer_type="local",
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path,
            key_id="test-key"
        )
        
        assert isinstance(signer, LocalJWTSigner)
        assert signer.algorithm == "RS256"
        assert signer.key_id == "test-key"

    def test_create_local_hmac_signer(self):
        """Test creating a local HMAC signer."""
        signer = create_jwt_signer(
            signer_type="local",
            algorithm="HS256",
            secret_key="my-secret-key",
            key_id="hmac-key"
        )
        
        assert isinstance(signer, LocalJWTSigner)
        assert signer.algorithm == "HS256"
        assert signer.key_id == "hmac-key"

    def test_create_keyvault_signer_requires_azure_sdk(self):
        """Test that creating Key Vault signer without Azure SDK raises error."""
        try:
            import azure.keyvault.keys
            pytest.skip("Azure SDK is installed, cannot test import error")
        except ImportError:
            # Azure SDK is not installed; proceed to verify that the factory
            # raises JWTSignerError due to the missing dependency.
            pass
        
        with pytest.raises(JWTSignerError, match="Azure SDK"):
            create_jwt_signer(
                signer_type="keyvault",
                algorithm="RS256",
                key_vault_url="https://test.vault.azure.net/",
                key_name="test-key"
            )

    def test_unknown_signer_type_raises_error(self):
        """Test that unknown signer type raises error."""
        with pytest.raises(JWTSignerError, match="Unknown signer type"):
            create_jwt_signer(
                signer_type="unknown",
                algorithm="RS256"
            )

    def test_local_rsa_missing_private_key_raises_error(self, rsa_key_files):
        """Test that missing private key parameter raises error."""
        _, public_path = rsa_key_files
        
        with pytest.raises(JWTSignerError, match="requires private_key_path"):
            create_jwt_signer(
                signer_type="local",
                algorithm="RS256",
                public_key_path=public_path
            )

    def test_local_rsa_missing_public_key_raises_error(self, rsa_key_files):
        """Test that missing public key parameter raises error."""
        private_path, _ = rsa_key_files
        
        with pytest.raises(JWTSignerError, match="requires public_key_path"):
            create_jwt_signer(
                signer_type="local",
                algorithm="RS256",
                private_key_path=private_path
            )

    def test_local_hmac_missing_secret_raises_error(self):
        """Test that missing secret key parameter raises error."""
        with pytest.raises(JWTSignerError, match="requires secret_key"):
            create_jwt_signer(
                signer_type="local",
                algorithm="HS256"
            )

    def test_keyvault_missing_url_raises_error(self):
        """Test that missing Key Vault URL raises error."""
        try:
            import azure.keyvault.keys
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        with pytest.raises(JWTSignerError, match="requires key_vault_url"):
            create_jwt_signer(
                signer_type="keyvault",
                algorithm="RS256",
                key_name="test-key"
            )

    def test_keyvault_missing_key_name_raises_error(self):
        """Test that missing key name raises error."""
        try:
            import azure.keyvault.keys
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        with pytest.raises(JWTSignerError, match="requires key_name"):
            create_jwt_signer(
                signer_type="keyvault",
                algorithm="RS256",
                key_vault_url="https://test.vault.azure.net/"
            )
