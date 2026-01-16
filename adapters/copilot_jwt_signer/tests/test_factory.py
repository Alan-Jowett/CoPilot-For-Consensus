# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT signer factory."""

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from copilot_config.generated.adapters.jwt_signer import (
    AdapterConfig_JwtSigner,
    DriverConfig_JwtSigner_Keyvault,
    DriverConfig_JwtSigner_Local,
)

from copilot_jwt_signer import LocalJWTSigner, create_jwt_signer
from copilot_jwt_signer.exceptions import JWTSignerError


class TestCreateJWTSigner:
    """Tests for create_jwt_signer factory function."""

    @pytest.fixture
    def rsa_key_pems(self):
        """Create RSA key PEM content for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return private_pem.decode("utf-8"), public_pem.decode("utf-8")

    def test_create_local_rsa_signer(self, rsa_key_pems):
        """Test creating a local RSA signer."""
        private_pem, public_pem = rsa_key_pems

        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="RS256",
                key_id="test-key",
                private_key=private_pem,
                public_key=public_pem,
            ),
        )
        signer = create_jwt_signer(config)

        assert isinstance(signer, LocalJWTSigner)
        assert signer.algorithm == "RS256"
        assert signer.key_id == "test-key"

    def test_create_local_hmac_signer(self):
        """Test creating a local HMAC signer."""
        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="HS256",
                key_id="hmac-key",
                secret_key="my-secret-key",
            ),
        )
        signer = create_jwt_signer(config)

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
        
        config = AdapterConfig_JwtSigner(
            signer_type="keyvault",
            driver=DriverConfig_JwtSigner_Keyvault(
                algorithm="RS256",
                key_id="test-key",
                key_vault_url="https://test.vault.azure.net/",
                key_name="test-key",
            ),
        )
        with pytest.raises(JWTSignerError, match="Azure SDK"):
            create_jwt_signer(config)

    def test_unknown_signer_type_raises_error(self):
        """Test that unknown signer type raises error."""
        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(algorithm="RS256"),
        )
        # Mutate to an invalid discriminant to ensure the factory errors.
        config.signer_type = "unknown"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unknown jwt_signer driver"):
            create_jwt_signer(config)

    def test_local_rsa_missing_private_key_raises_error(self, rsa_key_pems):
        """Test that missing private key parameter raises error."""
        _, public_pem = rsa_key_pems

        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="RS256",
                key_id="test-key",
                public_key=public_pem,
            ),
        )
        with pytest.raises(ValueError, match="private_key"):
            create_jwt_signer(config)

    def test_local_rsa_missing_public_key_raises_error(self, rsa_key_pems):
        """Test that missing public key parameter raises error."""
        private_pem, _ = rsa_key_pems

        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="RS256",
                key_id="test-key",
                private_key=private_pem,
            ),
        )
        with pytest.raises(ValueError, match="public_key"):
            create_jwt_signer(config)

    def test_local_hmac_missing_secret_raises_error(self):
        """Test that missing secret key parameter raises error."""
        config = AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="HS256",
                key_id="test-key",
            ),
        )
        with pytest.raises(ValueError, match="secret_key"):
            create_jwt_signer(config)

    def test_keyvault_missing_url_raises_error(self):
        """Test that missing Key Vault URL raises error."""
        try:
            import azure.keyvault.keys
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        with pytest.raises(TypeError):
            # key_vault_url is a required typed field; constructing the dataclass without it should fail.
            DriverConfig_JwtSigner_Keyvault(
                algorithm="RS256",
                key_id="test-key",
                key_name="test-key",
                # missing key_vault_url
            )

    def test_keyvault_missing_key_name_raises_error(self):
        """Test that missing key name raises error."""
        try:
            import azure.keyvault.keys
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        with pytest.raises(TypeError):
            # key_name is a required typed field; constructing the dataclass without it should fail.
            DriverConfig_JwtSigner_Keyvault(
                algorithm="RS256",
                key_id="test-key",
                key_vault_url="https://test.vault.azure.net/",
                # missing key_name
            )
