# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for JWT signing with Key Vault.

Notes:
- `copilot_jwt_signer` (and the Azure SDK extras it depends on) are optional.
- The auth service configuration schema may not expose a `jwt_signer` adapter,
  so these tests focus only on the signer package itself.
"""

from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.integration]


class TestJWTKeyVaultSigningIntegration:
    """Integration tests for Key Vault JWT signer adapter (optional dependency)."""

    def test_keyvault_signer_importable(self):
        """`copilot_jwt_signer` should be importable when installed."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")
        from copilot_jwt_signer import KeyVaultJWTSigner, create_jwt_signer

        assert KeyVaultJWTSigner is not None
        assert create_jwt_signer is not None

    def test_context_manager_support(self):
        """Test that `KeyVaultJWTSigner` supports the context manager protocol."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")

        pytest.importorskip("azure.identity", reason="Azure SDK not installed")
        pytest.importorskip("azure.keyvault.keys", reason="Azure Key Vault SDK not installed")
        pytest.importorskip(
            "azure.keyvault.keys.crypto",
            reason="Azure Key Vault cryptography SDK not installed",
        )

        with (
            patch("azure.identity.DefaultAzureCredential"),
            patch("azure.keyvault.keys.KeyClient") as mock_key_client,
            patch("azure.keyvault.keys.crypto.CryptographyClient"),
        ):
            mock_key = Mock()
            mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
            mock_key_client.return_value.get_key.return_value = mock_key

            from copilot_jwt_signer import KeyVaultJWTSigner

            with patch.object(KeyVaultJWTSigner, "close") as mock_close:
                with KeyVaultJWTSigner(
                    algorithm="RS256",
                    key_vault_url="https://test.vault.azure.net/",
                    key_name="test-key",
                ) as signer:
                    assert signer is not None
                    assert hasattr(signer, "sign")

                assert mock_close.called
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors
"""Integration tests for JWT signing with Key Vault.

Notes:
- `copilot_jwt_signer` (and the Azure SDK extras it depends on) are optional.
- The auth service configuration schema may not expose a `jwt_signer` adapter,
  so these tests focus only on the signer package itself.
"""

<<<<<<< HEAD
from __future__ import annotations

=======
>>>>>>> 9b86ffcd (Address code review: remove unused params, fix circuit breaker, clean up tests)
from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.integration]


class TestJWTKeyVaultSigningIntegration:
    """Integration tests for Key Vault JWT signer adapter (optional dependency)."""

    def test_keyvault_signer_importable(self):
        """`copilot_jwt_signer` should be importable when installed."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")
        from copilot_jwt_signer import KeyVaultJWTSigner, create_jwt_signer

<<<<<<< HEAD
        assert KeyVaultJWTSigner is not None
        assert create_jwt_signer is not None

    def test_context_manager_support(self):
        """Test that `KeyVaultJWTSigner` supports the context manager protocol."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")

        pytest.importorskip("azure.identity", reason="Azure SDK not installed")
        pytest.importorskip("azure.keyvault.keys", reason="Azure Key Vault SDK not installed")
        pytest.importorskip(
            "azure.keyvault.keys.crypto",
            reason="Azure Key Vault cryptography SDK not installed",
        )

        with (
            patch("azure.identity.DefaultAzureCredential"),
            patch("azure.keyvault.keys.KeyClient") as mock_key_client,
            patch("azure.keyvault.keys.crypto.CryptographyClient"),
        ):
            mock_key = Mock()
            mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
            mock_key_client.return_value.get_key.return_value = mock_key

            from copilot_jwt_signer import KeyVaultJWTSigner

            with patch.object(KeyVaultJWTSigner, "close") as mock_close:
                with KeyVaultJWTSigner(
                    algorithm="RS256",
                    key_vault_url="https://test.vault.azure.net/",
                    key_name="test-key",
                ) as signer:
                    assert signer is not None
                    assert hasattr(signer, "sign")

=======
    def test_auth_service_initialization_with_keyvault_signer_missing_adapter(self):
        """Test that auth service fails gracefully when JWT signer adapter is not installed."""
        # Mock configuration for Key Vault signing
        config = Mock()
        config.issuer = "http://localhost:8090"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "test-key"
        config.jwt_default_expiry = 1800
        config.jwt_signer_type = "keyvault"
        config.jwt_key_vault_url = "https://test.vault.azure.net/"
        config.jwt_key_vault_key_name = "test-key"
        
        # Mock the import to fail
        with patch('builtins.__import__', side_effect=ImportError("No module named 'copilot_jwt_signer'")):
            from app.service import AuthService
            
            # Should raise ValueError about missing adapter
            with pytest.raises(ValueError, match="copilot_jwt_signer adapter"):
                AuthService(config)

    def test_auth_service_initialization_with_keyvault_missing_config(self):
        """Test that auth service fails gracefully when Key Vault config is missing."""
        # Only run if copilot_jwt_signer is available
        try:
            from copilot_jwt_signer import KeyVaultJWTSigner  # noqa: F401
        except ImportError:
            pytest.skip("copilot_jwt_signer not installed")
        
        from app.service import AuthService
        
        # Mock configuration with missing Key Vault URL
        config = Mock()
        config.issuer = "http://localhost:8090"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "test-key"
        config.jwt_default_expiry = 1800
        config.jwt_signer_type = "keyvault"
        config.jwt_key_vault_url = None  # Missing!
        config.jwt_key_vault_key_name = "test-key"
        
        # Should raise ValueError about missing URL
        with pytest.raises(ValueError, match="JWT_KEY_VAULT_URL is required"):
            AuthService(config)

    @patch('azure.identity.DefaultAzureCredential')
    @patch('azure.keyvault.keys.KeyClient')
    @patch('azure.keyvault.keys.crypto.CryptographyClient')
    def test_auth_service_initialization_with_keyvault_signer(
        self, mock_crypto_client, mock_key_client, mock_credential
    ):
        """Test that auth service correctly initializes with Key Vault signing mode.
        
        This test uses mocked Azure SDK to verify the initialization flow.
        """
        # Only run if copilot_jwt_signer is available
        try:
            from copilot_jwt_signer import KeyVaultJWTSigner  # noqa: F401
        except ImportError:
            pytest.skip("copilot_jwt_signer not installed")
        
        from app.service import AuthService
        
        # Mock Azure SDK clients
        mock_key = Mock()
        mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
        mock_key.key_type.value = "RSA"
        mock_key.key.n = b"test_modulus"
        mock_key.key.e = b"test_exponent"
        
        mock_key_client_instance = Mock()
        mock_key_client_instance.get_key.return_value = mock_key
        mock_key_client.return_value = mock_key_client_instance
        
        mock_crypto_client_instance = Mock()
        mock_crypto_client.return_value = mock_crypto_client_instance
        
        mock_credential_instance = Mock()
        mock_credential.return_value = mock_credential_instance
        
        # Mock configuration for Key Vault signing
        config = Mock()
        config.issuer = "http://localhost:8090"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "test-key"
        config.jwt_default_expiry = 1800
        config.jwt_signer_type = "keyvault"
        config.jwt_key_vault_url = "https://test.vault.azure.net/"
        config.jwt_key_vault_key_name = "test-key"
        config.jwt_key_vault_key_version = None
        
        # Add role store config
        config.role_store_type = "mongodb"
        config.role_store_host = "localhost"
        config.role_store_port = 27017
        config.role_store_database = "auth"
        config.role_store_collection = "user_roles"
        
        # Mock role store to avoid MongoDB dependency
        with patch('app.service.RoleStore'):
            # Initialize auth service
            service = AuthService(config)
            
            # Verify JWT manager was initialized
            assert service.jwt_manager is not None
            assert service.jwt_manager.algorithm == "RS256"
            assert service.jwt_manager.use_signer is True

    @patch('azure.identity.DefaultAzureCredential')
    @patch('azure.keyvault.keys.KeyClient')
    @patch('azure.keyvault.keys.crypto.CryptographyClient')
    def test_auth_service_token_minting_with_keyvault_signer(
        self, mock_crypto_client, mock_key_client, mock_credential
    ):
        """Test that auth service can mint tokens using Key Vault signer."""
        # Only run if copilot_jwt_signer is available
        try:
            from copilot_jwt_signer import KeyVaultJWTSigner  # noqa: F401
        except ImportError:
            pytest.skip("copilot_jwt_signer not installed")
        
        from app.service import AuthService
        from copilot_auth import User
        
        # Mock Azure SDK clients
        mock_key = Mock()
        mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
        mock_key.key_type.value = "RSA"
        mock_key.key.n = b"test_modulus"
        mock_key.key.e = b"test_exponent"
        
        mock_key_client_instance = Mock()
        mock_key_client_instance.get_key.return_value = mock_key
        mock_key_client.return_value = mock_key_client_instance
        
        # Mock sign operation
        mock_sign_result = Mock()
        mock_sign_result.signature = b"mock_signature_bytes"
        mock_crypto_client_instance = Mock()
        mock_crypto_client_instance.sign.return_value = mock_sign_result
        mock_crypto_client.return_value = mock_crypto_client_instance
        
        mock_credential_instance = Mock()
        mock_credential.return_value = mock_credential_instance
        
        # Mock configuration
        config = Mock()
        config.issuer = "http://localhost:8090"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "test-key"
        config.jwt_default_expiry = 1800
        config.jwt_signer_type = "keyvault"
        config.jwt_key_vault_url = "https://test.vault.azure.net/"
        config.jwt_key_vault_key_name = "test-key"
        config.jwt_key_vault_key_version = None
        
        # Add role store config
        config.role_store_type = "mongodb"
        config.role_store_host = "localhost"
        config.role_store_port = 27017
        config.role_store_database = "auth"
        config.role_store_collection = "user_roles"
        
        # Mock role store
        with patch('app.service.RoleStore'):
            # Initialize auth service
            service = AuthService(config)
            
            # Create a test user
            user = User(
                id="github:12345",
                email="test@example.com",
                name="Test User",
                roles=["user"]
            )
            
            # Mint a token
            token = service.jwt_manager.mint_token(
                user=user,
                audience="test-audience"
            )
            
            # Verify token was minted (should be a string)
            assert isinstance(token, str)
            assert len(token) > 0
            
            # Verify sign was called
            assert mock_crypto_client_instance.sign.called

    @patch('azure.identity.DefaultAzureCredential')
    @patch('azure.keyvault.keys.KeyClient')
    @patch('azure.keyvault.keys.crypto.CryptographyClient')
    def test_auth_service_jwks_endpoint_with_keyvault_signer(
        self, mock_crypto_client, mock_key_client, mock_credential
    ):
        """Test that JWKS endpoint returns correct public keys from Key Vault."""
        # Only run if copilot_jwt_signer is available
        try:
            from copilot_jwt_signer import KeyVaultJWTSigner  # noqa: F401
        except ImportError:
            pytest.skip("copilot_jwt_signer not installed")
        
        from app.service import AuthService
        
        # Mock Azure SDK clients
        mock_key = Mock()
        mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
        mock_key.key_type.value = "RSA"
        mock_key.key.n = b"test_modulus_bytes"
        mock_key.key.e = b"\x01\x00\x01"  # 65537 in bytes
        mock_key.key.crv = None
        
        mock_key_client_instance = Mock()
        mock_key_client_instance.get_key.return_value = mock_key
        mock_key_client.return_value = mock_key_client_instance
        
        mock_crypto_client_instance = Mock()
        mock_crypto_client.return_value = mock_crypto_client_instance
        
        mock_credential_instance = Mock()
        mock_credential.return_value = mock_credential_instance
        
        # Mock configuration
        config = Mock()
        config.issuer = "http://localhost:8090"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "test-key"
        config.jwt_default_expiry = 1800
        config.jwt_signer_type = "keyvault"
        config.jwt_key_vault_url = "https://test.vault.azure.net/"
        config.jwt_key_vault_key_name = "test-key"
        config.jwt_key_vault_key_version = None
        
        # Add role store config
        config.role_store_type = "mongodb"
        config.role_store_host = "localhost"
        config.role_store_port = 27017
        config.role_store_database = "auth"
        config.role_store_collection = "user_roles"
        
        # Mock role store
        with patch('app.service.RoleStore'):
            # Initialize auth service
            service = AuthService(config)
            
            # Get JWKS
            jwks = service.jwt_manager.get_jwks()
            
            # Verify JWKS structure
            assert "keys" in jwks
            assert len(jwks["keys"]) > 0
            
            # Verify first key has required fields
            key = jwks["keys"][0]
            assert key["kty"] == "RSA"
            assert key["use"] == "sig"
            assert key["kid"] == "test-key"
            assert key["alg"] == "RS256"
            assert "n" in key
            assert "e" in key
            
            # Verify Key Vault was queried
            assert mock_key_client_instance.get_key.called

    def test_context_manager_support(self):
        """Test that KeyVaultJWTSigner supports context manager protocol."""
        # Only run if copilot_jwt_signer and Azure SDK are available
        try:
            from copilot_jwt_signer import KeyVaultJWTSigner  # noqa: F401
        except ImportError:
            pytest.skip("copilot_jwt_signer not installed")
        
        try:
            import azure.identity  # noqa: F401
            import azure.keyvault.keys  # noqa: F401
            import azure.keyvault.keys.crypto  # noqa: F401
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        # Mock Azure SDK to avoid actual Key Vault calls
        with patch('azure.identity.DefaultAzureCredential'), \
             patch('azure.keyvault.keys.KeyClient') as mock_key_client, \
             patch('azure.keyvault.keys.crypto.CryptographyClient'):
            
            # Mock key retrieval
            mock_key = Mock()
            mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
            mock_key_client.return_value.get_key.return_value = mock_key
            
            # Test context manager - patch close to verify it's called
            from copilot_jwt_signer import KeyVaultJWTSigner
            with patch.object(KeyVaultJWTSigner, 'close') as mock_close:
                with KeyVaultJWTSigner(
                    algorithm="RS256",
                    key_vault_url="https://test.vault.azure.net/",
                    key_name="test-key"
                ) as signer:
                    assert signer is not None
                    assert hasattr(signer, 'sign')
                
                # Verify close was called when exiting context
>>>>>>> 9b86ffcd (Address code review: remove unused params, fix circuit breaker, clean up tests)
                assert mock_close.called
