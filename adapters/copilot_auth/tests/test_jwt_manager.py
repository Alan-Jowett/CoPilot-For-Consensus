# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT token manager."""

import time

import jwt
import pytest
from copilot_auth import User
from copilot_auth.jwt_manager import JWTManager


class TestJWTManagerInitialization:
    """Tests for JWTManager initialization."""

    def test_initialization_with_rs256(self, tmp_path):
        """Test JWTManager initializes with RS256 algorithm."""
        # Generate test keys
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        # Initialize manager
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        assert manager.issuer == "https://auth.example.com"
        assert manager.algorithm == "RS256"
        assert manager.key_id == "default"
        assert manager.default_expiry == 1800
        assert manager.private_key is not None
        assert manager.public_key is not None

    def test_initialization_with_rs256_custom_key_id(self, tmp_path):
        """Test JWTManager initializes with custom key ID."""
        # Generate test keys
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        # Initialize manager with custom key_id
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            key_id="key-2025",
        )

        assert manager.key_id == "key-2025"

    def test_initialization_with_rs256_custom_expiry(self, tmp_path):
        """Test JWTManager initializes with custom default expiry."""
        # Generate test keys
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        # Initialize manager with custom expiry
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            default_expiry=3600,
        )

        assert manager.default_expiry == 3600

    def test_initialization_with_hs256(self):
        """Test JWTManager initializes with HS256 algorithm."""
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        assert manager.issuer == "https://auth.example.com"
        assert manager.algorithm == "HS256"
        assert manager.private_key == "test-secret-key-at-least-32-chars-long"
        assert manager.public_key == "test-secret-key-at-least-32-chars-long"

    def test_initialization_rs256_requires_private_key_path(self, tmp_path):
        """Test RS256 initialization fails without private key path."""
        public_key_path = tmp_path / "public.pem"

        with pytest.raises(ValueError, match="RS256 requires both private_key_path and public_key_path"):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="RS256",
                public_key_path=public_key_path,
            )

    def test_initialization_rs256_requires_public_key_path(self, tmp_path):
        """Test RS256 initialization fails without public key path."""
        private_key_path = tmp_path / "private.pem"

        with pytest.raises(ValueError, match="RS256 requires both private_key_path and public_key_path"):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="RS256",
                private_key_path=private_key_path,
            )

    def test_initialization_hs256_requires_secret_key(self):
        """Test HS256 initialization fails without secret key."""
        with pytest.raises(ValueError, match="HS256 requires secret_key"):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="HS256",
            )

    def test_initialization_unsupported_algorithm(self):
        """Test initialization fails with unsupported algorithm."""
        with pytest.raises(ValueError, match="Unsupported algorithm: ES256"):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="ES256",
                secret_key="test-secret",
            )

    def test_initialization_with_nonexistent_private_key(self, tmp_path):
        """Test RS256 initialization fails with nonexistent private key file."""
        public_key_path = tmp_path / "public.pem"
        private_key_path = tmp_path / "private.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        with pytest.raises(FileNotFoundError):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="RS256",
                private_key_path=tmp_path / "missing.pem",
                public_key_path=public_key_path,
            )

    def test_initialization_with_nonexistent_public_key(self, tmp_path):
        """Test RS256 initialization fails with nonexistent public key file."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        with pytest.raises(FileNotFoundError):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="RS256",
                private_key_path=private_key_path,
                public_key_path=tmp_path / "missing.pem",
            )

    def test_initialization_with_invalid_private_key_format(self, tmp_path):
        """Test RS256 initialization fails with corrupted private key file."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"

        # Create corrupted key files
        private_key_path.write_text("This is not a valid PEM key")
        JWTManager.generate_rsa_keys(tmp_path / "temp_private.pem", public_key_path)

        with pytest.raises(ValueError):
            JWTManager(
                issuer="https://auth.example.com",
                algorithm="RS256",
                private_key_path=private_key_path,
                public_key_path=public_key_path,
            )


class TestGenerateRSAKeys:
    """Tests for RSA key generation."""

    def test_generate_rsa_keys_creates_files(self, tmp_path):
        """Test generate_rsa_keys creates both key files."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"

        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        assert private_key_path.exists()
        assert public_key_path.exists()
        assert private_key_path.stat().st_size > 0
        assert public_key_path.stat().st_size > 0

    def test_generate_rsa_keys_with_custom_size(self, tmp_path):
        """Test generate_rsa_keys with custom key size."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"

        JWTManager.generate_rsa_keys(private_key_path, public_key_path, key_size=4096)

        assert private_key_path.exists()
        assert public_key_path.exists()

    def test_generated_keys_are_valid_for_jwt(self, tmp_path):
        """Test generated keys can be used for JWT signing."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"

        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        # Verify keys work with JWT manager
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        assert manager.private_key is not None
        assert manager.public_key is not None


class TestMintToken:
    """Tests for JWT token minting."""

    def test_mint_token_with_required_fields(self, tmp_path):
        """Test minting token with required fields."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_mint_token_contains_standard_claims(self, tmp_path):
        """Test minted token contains standard JWT claims."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        # Decode without verification to check claims
        unverified = jwt.decode(token, options={"verify_signature": False})

        assert unverified["iss"] == "https://auth.example.com"
        assert unverified["sub"] == "github:12345"
        assert unverified["aud"] == "https://api.example.com"
        assert unverified["email"] == "test@example.com"
        assert unverified["name"] == "Test User"
        assert "exp" in unverified
        assert "iat" in unverified
        assert "nbf" in unverified
        assert "jti" in unverified

    def test_mint_token_with_roles(self, tmp_path):
        """Test minting token with roles."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
            roles=["contributor", "reviewer"],
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        unverified = jwt.decode(token, options={"verify_signature": False})
        assert unverified["roles"] == ["contributor", "reviewer"]

    def test_mint_token_with_affiliations(self, tmp_path):
        """Test minting token with affiliations."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
            affiliations=["IETF", "W3C"],
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        unverified = jwt.decode(token, options={"verify_signature": False})
        assert unverified["affiliations"] == ["IETF", "W3C"]

    def test_mint_token_with_custom_expiry(self, tmp_path):
        """Test minting token with custom expiry."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com", expires_in=3600)

        unverified = jwt.decode(token, options={"verify_signature": False})

        # Check expiry is approximately 3600 seconds after issuance
        assert abs(unverified["exp"] - unverified["iat"] - 3600) < 5

    def test_mint_token_with_additional_claims(self, tmp_path):
        """Test minting token with additional custom claims."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        additional_claims = {
            "custom_field": "custom_value",
            "scope": "read:drafts write:comments",
        }

        token = manager.mint_token(
            user,
            audience="https://api.example.com",
            additional_claims=additional_claims,
        )

        unverified = jwt.decode(token, options={"verify_signature": False})
        assert unverified["custom_field"] == "custom_value"
        assert unverified["scope"] == "read:drafts write:comments"

    def test_mint_token_includes_key_id_in_header(self, tmp_path):
        """Test minted token includes key ID in header."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            key_id="key-2025",
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        header = jwt.get_unverified_header(token)
        assert header["kid"] == "key-2025"

    def test_mint_token_with_hs256(self):
        """Test minting token with HS256 algorithm."""
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        assert isinstance(token, str)
        assert len(token) > 0


class TestValidateToken:
    """Tests for JWT token validation."""

    def test_validate_token_with_valid_token(self, tmp_path):
        """Test validating a valid token."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")
        claims = manager.validate_token(token, audience="https://api.example.com")

        assert claims["sub"] == "github:12345"
        assert claims["email"] == "test@example.com"
        assert claims["name"] == "Test User"

    def test_validate_token_with_roles_and_affiliations(self, tmp_path):
        """Test validating token preserves roles and affiliations."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
            roles=["contributor"],
            affiliations=["IETF"],
        )

        token = manager.mint_token(user, audience="https://api.example.com")
        claims = manager.validate_token(token, audience="https://api.example.com")

        assert claims["roles"] == ["contributor"]
        assert claims["affiliations"] == ["IETF"]

    def test_validate_token_with_wrong_audience(self, tmp_path):
        """Test validation fails with wrong audience."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        with pytest.raises(jwt.InvalidTokenError):
            manager.validate_token(token, audience="https://wrong-audience.example.com")

    def test_validate_token_with_expired_token(self, tmp_path):
        """Test validation fails with expired token."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        # Create token that expires in 1 second
        token = manager.mint_token(user, audience="https://api.example.com", expires_in=1)

        # Wait for token to expire beyond the skew tolerance
        time.sleep(2)

        # Use a smaller clock skew to ensure token is rejected
        with pytest.raises(jwt.ExpiredSignatureError):
            manager.validate_token(token, audience="https://api.example.com", max_skew_seconds=0)

    def test_validate_token_with_wrong_issuer(self, tmp_path):
        """Test validation fails with wrong issuer."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager1 = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        manager2 = JWTManager(
            issuer="https://different-issuer.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager1.mint_token(user, audience="https://api.example.com")

        with pytest.raises(jwt.InvalidTokenError):
            manager2.validate_token(token, audience="https://api.example.com")

    def test_validate_token_with_tampered_signature(self, tmp_path):
        """Test validation fails with tampered signature."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")

        # Tamper with the token
        tampered_token = token[:-10] + "tamperedxx"

        with pytest.raises(jwt.InvalidTokenError):
            manager.validate_token(tampered_token, audience="https://api.example.com")

    def test_validate_token_with_empty_string(self, tmp_path):
        """Test validation fails with empty string token."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        with pytest.raises(jwt.InvalidTokenError):
            manager.validate_token("", audience="https://api.example.com")

    def test_validate_token_with_malformed_segments(self, tmp_path):
        """Test validation fails with malformed token (wrong number of segments)."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        with pytest.raises(jwt.InvalidTokenError):
            manager.validate_token("not.a.jwt", audience="https://api.example.com")

    def test_validate_token_with_invalid_base64(self, tmp_path):
        """Test validation fails with invalid base64 encoding."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        with pytest.raises(jwt.InvalidTokenError):
            manager.validate_token("!!!.!!!.!!!", audience="https://api.example.com")

    def test_validate_token_with_different_rsa_keys(self, tmp_path):
        """Test validation fails when token signed with different RSA key pair."""
        # Create two different key pairs
        private_key_path1 = tmp_path / "private1.pem"
        public_key_path1 = tmp_path / "public1.pem"
        private_key_path2 = tmp_path / "private2.pem"
        public_key_path2 = tmp_path / "public2.pem"

        JWTManager.generate_rsa_keys(private_key_path1, public_key_path1)
        JWTManager.generate_rsa_keys(private_key_path2, public_key_path2)

        # Create two managers with different keys but same issuer
        manager1 = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path1,
            public_key_path=public_key_path1,
        )

        manager2 = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path2,
            public_key_path=public_key_path2,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        # Token from manager1 should be rejected by manager2 due to signature mismatch
        token = manager1.mint_token(user, audience="https://api.example.com")

        with pytest.raises(jwt.InvalidSignatureError):
            manager2.validate_token(token, audience="https://api.example.com")

    def test_validate_token_with_clock_skew(self, tmp_path):
        """Test validation respects clock skew tolerance."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        # Create a token that expires in 1 second
        token = manager.mint_token(user, audience="https://api.example.com", expires_in=1)

        # Wait 1.5 seconds - token should be expired but within 90 second skew
        time.sleep(1.5)

        # Should succeed with default skew (90 seconds)
        claims = manager.validate_token(token, audience="https://api.example.com", max_skew_seconds=90)
        assert claims["sub"] == "github:12345"

    def test_validate_token_with_hs256(self):
        """Test validating token with HS256 algorithm."""
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        user = User(
            id="github:12345",
            email="test@example.com",
            name="Test User",
        )

        token = manager.mint_token(user, audience="https://api.example.com")
        claims = manager.validate_token(token, audience="https://api.example.com")

        assert claims["sub"] == "github:12345"
        assert claims["email"] == "test@example.com"


class TestGetJWKS:
    """Tests for JWKS generation."""

    def test_get_jwks_with_rs256(self, tmp_path):
        """Test get_jwks returns JWKS for RS256."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            key_id="key-2025",
        )

        jwks = manager.get_jwks()

        assert "keys" in jwks
        assert len(jwks["keys"]) == 1

        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["use"] == "sig"
        assert key["kid"] == "key-2025"
        assert key["alg"] == "RS256"
        assert "n" in key  # RSA modulus
        assert "e" in key  # RSA exponent

    def test_get_jwks_with_hs256(self):
        """Test get_jwks returns empty keys for HS256."""
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        jwks = manager.get_jwks()

        assert jwks == {"keys": []}


class TestGetPublicKeyPEM:
    """Tests for public key PEM export."""

    def test_get_public_key_pem_with_rs256(self, tmp_path):
        """Test get_public_key_pem returns PEM for RS256."""
        private_key_path = tmp_path / "private.pem"
        public_key_path = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(private_key_path, public_key_path)

        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )

        pem = manager.get_public_key_pem()

        assert pem is not None
        assert isinstance(pem, str)
        assert pem.startswith("-----BEGIN PUBLIC KEY-----")
        assert pem.endswith("-----END PUBLIC KEY-----\n")

    def test_get_public_key_pem_with_hs256(self):
        """Test get_public_key_pem returns None for HS256."""
        manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        pem = manager.get_public_key_pem()

        assert pem is None


class TestIntToBase64URL:
    """Tests for _int_to_base64url helper method."""

    def test_int_to_base64url_small_value(self):
        """Test _int_to_base64url with small value."""
        result = JWTManager._int_to_base64url(65537)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_int_to_base64url_large_value(self):
        """Test _int_to_base64url with large RSA modulus."""
        # Typical RSA modulus size (2048 bits)
        large_value = 2**2048 - 1
        result = JWTManager._int_to_base64url(large_value)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_int_to_base64url_zero(self):
        """Test _int_to_base64url with zero.

        Zero has bit_length of 0, so byte_length is 0, resulting in empty bytes.
        Base64url encoding of empty bytes produces an empty string.
        """
        result = JWTManager._int_to_base64url(0)

        assert isinstance(result, str)
        # Zero with 0 byte_length produces empty bytes -> empty base64url string
        assert result == ""
