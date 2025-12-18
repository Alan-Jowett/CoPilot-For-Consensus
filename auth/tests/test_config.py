# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for auth service configuration."""

from pathlib import Path
import sys

import pytest
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
