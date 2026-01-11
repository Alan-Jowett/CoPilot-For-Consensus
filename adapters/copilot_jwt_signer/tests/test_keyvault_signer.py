# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for KeyVaultJWTSigner with mocked Azure SDK."""

import pytest

from copilot_jwt_signer.exceptions import CircuitBreakerOpenError, KeyVaultSignerError


# Skip all tests if Azure SDK not installed
pytest.importorskip("azure.keyvault.keys")
pytest.importorskip("azure.identity")

from copilot_jwt_signer import KeyVaultJWTSigner


class TestKeyVaultJWTSignerInitialization:
    """Tests for KeyVaultJWTSigner initialization."""

    def test_unsupported_algorithm_raises_error(self):
        """Test that unsupported algorithm raises error."""
        with pytest.raises(KeyVaultSignerError, match="Unsupported algorithm"):
            KeyVaultJWTSigner(
                algorithm="HS256",  # HMAC not supported in Key Vault
                key_vault_url="https://test.vault.azure.net/",
                key_name="test-key"
            )

    def test_supported_rsa_algorithms(self):
        """Test that RSA algorithms are recognized."""
        for algo in ["RS256", "RS384", "RS512"]:
            try:
                # Will fail due to missing Azure credentials, but algorithm validation should pass
                KeyVaultJWTSigner(
                    algorithm=algo,
                    key_vault_url="https://test.vault.azure.net/",
                    key_name="test-key"
                )
            except KeyVaultSignerError as e:
                # Should fail on authentication, not algorithm validation
                assert "Unsupported algorithm" not in str(e)

    def test_supported_ec_algorithms(self):
        """Test that EC algorithms are recognized."""
        for algo in ["ES256", "ES384", "ES512"]:
            try:
                # Will fail due to missing Azure credentials, but algorithm validation should pass
                KeyVaultJWTSigner(
                    algorithm=algo,
                    key_vault_url="https://test.vault.azure.net/",
                    key_name="test-key"
                )
            except KeyVaultSignerError as e:
                # Should fail on authentication, not algorithm validation
                assert "Unsupported algorithm" not in str(e)


class TestKeyVaultJWTSignerWithMocks:
    """Tests for KeyVaultJWTSigner with mocked Azure SDK."""

    @pytest.fixture
    def mock_azure_clients(self, mocker):
        """Mock Azure SDK clients."""
        # Mock credential
        mock_credential = mocker.MagicMock()
        mocker.patch("azure.identity.DefaultAzureCredential", return_value=mock_credential)
        
        # Mock KeyClient
        mock_key_client = mocker.MagicMock()
        mock_key = mocker.MagicMock()
        mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
        mock_key.key_type.value = "RSA"
        mock_key.key.n = b"test_modulus"
        mock_key.key.e = b"test_exponent"
        mock_key_client.get_key.return_value = mock_key
        mocker.patch("azure.keyvault.keys.KeyClient", return_value=mock_key_client)
        
        # Mock CryptographyClient
        mock_crypto_client = mocker.MagicMock()
        mock_sign_result = mocker.MagicMock()
        mock_sign_result.signature = b"mock_signature"
        mock_crypto_client.sign.return_value = mock_sign_result
        mocker.patch("azure.keyvault.keys.crypto.CryptographyClient", return_value=mock_crypto_client)
        
        return {
            "credential": mock_credential,
            "key_client": mock_key_client,
            "crypto_client": mock_crypto_client,
            "key": mock_key
        }

    def test_sign_message_with_key_vault(self, mock_azure_clients):
        """Test signing a message using Key Vault."""
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            key_id="test-key-2024"
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert signature == b"mock_signature"
        assert mock_azure_clients["crypto_client"].sign.called

    def test_get_public_key_jwk_from_key_vault(self, mock_azure_clients):
        """Test getting public key JWK from Key Vault."""
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            key_id="test-key-2024"
        )
        
        jwk = signer.get_public_key_jwk()
        
        assert jwk["kty"] == "RSA"
        assert jwk["use"] == "sig"
        assert jwk["kid"] == "test-key-2024"
        assert jwk["alg"] == "RS256"
        assert "n" in jwk
        assert "e" in jwk
        assert mock_azure_clients["key_client"].get_key.called

    def test_health_check_succeeds(self, mock_azure_clients):
        """Test health check succeeds when signing works."""
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key"
        )
        
        assert signer.health_check() is True

    def test_retry_on_transient_error(self, mock_azure_clients, mocker):
        """Test that transient errors trigger retries."""
        from azure.core.exceptions import ServiceRequestError
        
        # First call fails, second succeeds
        mock_sign_result = mocker.MagicMock()
        mock_sign_result.signature = b"mock_signature"
        mock_azure_clients["crypto_client"].sign.side_effect = [
            ServiceRequestError("Network error"),
            mock_sign_result
        ]
        
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            max_retries=3,
            retry_delay=0.1  # Short delay for testing
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert signature == b"mock_signature"
        assert mock_azure_clients["crypto_client"].sign.call_count == 2

    def test_circuit_breaker_opens_after_threshold(self, mock_azure_clients, mocker):
        """Test that circuit breaker opens after failure threshold."""
        from azure.core.exceptions import ServiceRequestError
        
        # All calls fail
        mock_azure_clients["crypto_client"].sign.side_effect = ServiceRequestError("Network error")
        
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            max_retries=1,
            retry_delay=0.01,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )
        
        message = b"test message"
        
        # First few calls should retry and fail
        for _ in range(3):
            with pytest.raises(KeyVaultSignerError):
                signer.sign(message)
        
        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenError):
            signer.sign(message)

    def test_circuit_breaker_closes_after_timeout(self, mock_azure_clients, mocker):
        """Test that circuit breaker closes after timeout."""
        from azure.core.exceptions import ServiceRequestError
        
        # First calls fail, then succeed
        mock_sign_result = mocker.MagicMock()
        mock_sign_result.signature = b"mock_signature"
        
        failure_count = [0]
        def side_effect(*args, **kwargs):
            failure_count[0] += 1
            if failure_count[0] <= 3:
                raise ServiceRequestError("Network error")
            return mock_sign_result
        
        mock_azure_clients["crypto_client"].sign.side_effect = side_effect
        
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            max_retries=1,
            retry_delay=0.01,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=1  # 1 second timeout
        )
        
        message = b"test message"
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(KeyVaultSignerError):
                signer.sign(message)
        
        # Circuit should be open
        with pytest.raises(CircuitBreakerOpenError):
            signer.sign(message)
        
        # Wait for circuit breaker timeout
        import time
        time.sleep(1.5)
        
        # Circuit should now be in HALF_OPEN state and next call should succeed
        signature = signer.sign(message)
        assert signature == b"mock_signature"

    def test_specific_key_version(self, mock_azure_clients):
        """Test using a specific key version."""
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            key_version="version456"
        )
        
        message = b"test message"
        signer.sign(message)
        
        # Should have used the specific version
        mock_azure_clients["key_client"].get_key.assert_called_with("test-key", version="version456")


class TestKeyVaultJWTSignerEC:
    """Tests for KeyVaultJWTSigner with EC keys."""

    @pytest.fixture
    def mock_azure_clients_ec(self, mocker):
        """Mock Azure SDK clients for EC keys."""
        # Mock credential
        mock_credential = mocker.MagicMock()
        mocker.patch("azure.identity.DefaultAzureCredential", return_value=mock_credential)
        
        # Mock KeyClient with EC key
        mock_key_client = mocker.MagicMock()
        mock_key = mocker.MagicMock()
        mock_key.id = "https://test.vault.azure.net/keys/test-ec-key/version123"
        mock_key.key_type.value = "EC"
        mock_key.key.crv.value = "P-256"
        mock_key.key.x = b"test_x_coord"
        mock_key.key.y = b"test_y_coord"
        mock_key_client.get_key.return_value = mock_key
        mocker.patch("azure.keyvault.keys.KeyClient", return_value=mock_key_client)
        
        # Mock CryptographyClient
        mock_crypto_client = mocker.MagicMock()
        mock_sign_result = mocker.MagicMock()
        mock_sign_result.signature = b"mock_ec_signature"
        mock_crypto_client.sign.return_value = mock_sign_result
        mocker.patch("azure.keyvault.keys.crypto.CryptographyClient", return_value=mock_crypto_client)
        
        return {
            "credential": mock_credential,
            "key_client": mock_key_client,
            "crypto_client": mock_crypto_client,
            "key": mock_key
        }

    def test_sign_with_ec_key(self, mock_azure_clients_ec):
        """Test signing with an EC key."""
        signer = KeyVaultJWTSigner(
            algorithm="ES256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-ec-key"
        )
        
        message = b"test message"
        signature = signer.sign(message)
        
        assert signature == b"mock_ec_signature"

    def test_get_public_key_jwk_ec(self, mock_azure_clients_ec):
        """Test getting EC public key JWK."""
        signer = KeyVaultJWTSigner(
            algorithm="ES256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-ec-key",
            key_id="test-ec-key-2024"
        )
        
        jwk = signer.get_public_key_jwk()
        
        assert jwk["kty"] == "EC"
        assert jwk["use"] == "sig"
        assert jwk["kid"] == "test-ec-key-2024"
        assert jwk["alg"] == "ES256"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk

    def test_health_check_failure(self, mock_azure_clients):
        """Test health_check returns False when signer is in unhealthy state."""
        mock_azure_clients["crypto_client"].sign.side_effect = ServiceRequestError("Network error")
        
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key"
        )
        
        # Health check should return False when sign fails
        result = signer.health_check()
        assert result is False

    def test_health_check_with_circuit_breaker_open(self, mock_azure_clients):
        """Test health_check returns False when circuit breaker is open."""
        mock_azure_clients["crypto_client"].sign.side_effect = ServiceRequestError("Network error")
        
        signer = KeyVaultJWTSigner(
            algorithm="RS256",
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            max_retries=1,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=60
        )
        
        # Fail sign operations to open circuit breaker
        for _ in range(2):
            try:
                signer.sign(b"test")
            except KeyVaultSignerError:
                pass
        
        # Health check should return False when circuit is open
        result = signer.health_check()
        assert result is False

