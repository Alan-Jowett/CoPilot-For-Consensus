# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for auth service configuration."""

import sys
import tempfile
from pathlib import Path

from copilot_config import TypedConfig

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_auth_config


class TestAuthConfig:
    """Test auth configuration loading."""

    def test_auth_config_loads(self):
        """Test that auth config loads without errors."""
        config = load_auth_config()

        # Verify it's a TypedConfig instance
        assert isinstance(config, TypedConfig)

    def test_auth_config_has_required_fields(self):
        """Test that auth config has required fields."""
        config = load_auth_config()

        # Check that common auth fields are present
        assert hasattr(config, 'jwt_algorithm')
        assert hasattr(config, 'issuer')

    def test_jwt_algorithm_default(self):
        """Test JWT algorithm defaults to RS256."""
        config = load_auth_config()

        # Default should be RS256
        assert config.jwt_algorithm == "RS256"

    def test_issuer_configured(self):
        """Test issuer URL is configured."""
        config = load_auth_config()

        # Should have an issuer set
        assert config.issuer is not None
        assert isinstance(config.issuer, str)

    def test_secrets_loaded_and_written_to_temp(self, tmp_path, monkeypatch):
        """Ensure JWT secrets are pulled from local provider and materialized to files."""
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()

        private_content = "PRIVATE_KEY_CONTENT"
        public_content = "PUBLIC_KEY_CONTENT"

        (secret_dir / "jwt_private_key").write_text(private_content)
        (secret_dir / "jwt_public_key").write_text(public_content)

        monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")
        monkeypatch.setenv("SECRETS_BASE_PATH", str(secret_dir))

        temp_root = tmp_path / "auth_temp"
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temp_root))

        config = load_auth_config()

        assert config.jwt_private_key == private_content
        assert config.jwt_public_key == public_content

        materialized_dir = temp_root / "auth_keys"
        assert (materialized_dir / "jwt_private.pem").read_text() == private_content
        assert (materialized_dir / "jwt_public.pem").read_text() == public_content
