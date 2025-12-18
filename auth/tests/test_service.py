# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for auth service."""

import pytest
from pathlib import Path
from copilot_auth import User

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import AuthConfig, JWTConfig, OIDCProviderConfig, SecurityConfig
from app.service import AuthService


class TestAuthConfig:
    """Test auth configuration."""
    
    def test_jwt_config_defaults(self):
        """Test JWT config with defaults."""
        config = JWTConfig()
        assert config.algorithm == "RS256"
        assert config.key_id == "default"
        assert config.default_expiry == 1800
    
    def test_security_config_defaults(self):
        """Test security config with defaults."""
        config = SecurityConfig()
        assert config.require_pkce is True
        assert config.require_nonce is True
        assert config.max_skew_seconds == 90
        assert config.enable_dpop is False


class TestAuthService:
    """Test auth service."""
    
    @pytest.fixture
    def test_config(self, tmp_path):
        """Create test configuration."""
        # Generate test keys
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        private_path = tmp_path / "private.pem"
        public_path = tmp_path / "public.pem"
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_path.write_bytes(private_pem)
        
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_path.write_bytes(public_pem)
        
        # Create config
        jwt_config = JWTConfig(
            algorithm="RS256",
            private_key_path=private_path,
            public_key_path=public_path,
        )
        
        # Add mock provider
        providers = {
            "mock": OIDCProviderConfig(
                provider_type="mock",
                client_id="test",
                client_secret="test",
                redirect_uri="http://localhost:8090/callback",
            )
        }
        
        return AuthConfig(
            issuer="http://localhost:8090",
            audiences=["test-audience"],
            jwt=jwt_config,
            oidc_providers=providers,
        )
    
    def test_service_initialization(self, test_config):
        """Test service initializes correctly."""
        service = AuthService(config=test_config)
        
        assert service.is_ready() is True
        assert service.jwt_manager is not None
        assert len(service.providers) == 1
    
    def test_get_jwks(self, test_config):
        """Test JWKS endpoint."""
        service = AuthService(config=test_config)
        
        jwks = service.get_jwks()
        
        assert "keys" in jwks
        assert len(jwks["keys"]) == 1
        assert jwks["keys"][0]["kty"] == "RSA"
        assert jwks["keys"][0]["alg"] == "RS256"
    
    def test_get_stats(self, test_config):
        """Test statistics retrieval."""
        service = AuthService(config=test_config)
        
        stats = service.get_stats()
        
        assert "logins_total" in stats
        assert "tokens_minted" in stats
        assert "tokens_validated" in stats
        assert "validation_failures" in stats
        assert stats["logins_total"] == 0
