# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for auth service configuration."""

import sys
from pathlib import Path

from copilot_config.generated.services.auth import ServiceConfig_Auth

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_auth_config


class TestAuthConfig:
    """Test auth configuration loading."""

    def test_auth_config_loads(self):
        """Test that auth config loads without errors."""
        config = load_auth_config()

        # Verify it's a typed ServiceConfig dataclass
        assert isinstance(config, ServiceConfig_Auth)

    def test_auth_config_has_required_fields(self):
        """Test that auth config has required fields."""
        config = load_auth_config()

        # Check that common auth fields are present
        assert hasattr(config, "service_settings")
        assert hasattr(config.service_settings, "issuer")

        # JWT config may be provided either via legacy service settings (jwt_*)
        # or via the newer jwt_signer adapter configuration.
        assert hasattr(config, "jwt_signer") or hasattr(config.service_settings, "jwt_algorithm")

    def test_jwt_signer_configured(self):
        """Test JWT signer adapter is configured."""
        config = load_auth_config()

        if hasattr(config, "jwt_signer"):
            assert hasattr(config.jwt_signer, "signer_type")
            assert config.jwt_signer.signer_type in ("local", "keyvault")
            assert hasattr(config.jwt_signer, "driver")
        else:
            # Legacy default should be RS256
            assert config.service_settings.jwt_algorithm == "RS256"

    def test_issuer_configured(self):
        """Test issuer URL is configured."""
        config = load_auth_config()

        # Should have an issuer set
        assert config.service_settings.issuer is not None
        assert isinstance(config.service_settings.issuer, str)

    def test_secrets_loaded_from_local_provider(self, tmp_path, monkeypatch):
        """Ensure JWT secrets are pulled from local provider via schema metadata."""
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()

        private_content = "PRIVATE_KEY_CONTENT"
        public_content = "PUBLIC_KEY_CONTENT"

        (secret_dir / "jwt_private_key").write_text(private_content)
        (secret_dir / "jwt_public_key").write_text(public_content)

        monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")
        monkeypatch.setenv("SECRETS_BASE_PATH", str(secret_dir))

        # Prefer local signer in tests when supported.
        monkeypatch.setenv("JWT_SIGNER_TYPE", "local")

        config = load_auth_config()

        if hasattr(config, "jwt_signer") and hasattr(config.jwt_signer, "driver"):
            # New shape: secrets are attached to the jwt_signer local driver.
            driver = config.jwt_signer.driver
            assert getattr(driver, "private_key", None) == private_content
            assert getattr(driver, "public_key", None) == public_content
        else:
            # Legacy shape: secrets are attached to service settings.
            assert config.service_settings.jwt_private_key == private_content
            assert config.service_settings.jwt_public_key == public_content
