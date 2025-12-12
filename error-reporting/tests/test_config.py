# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for error-reporting service configuration loading."""

from copilot_config import load_typed_config
from app.error_store import ErrorStore


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_typed_config_succeeds(self):
        """Test that load_typed_config successfully loads error-reporting config."""
        config = load_typed_config("error-reporting")
        
        # Verify config has required attributes
        assert hasattr(config, "max_errors")
        assert hasattr(config, "http_port")
        assert isinstance(config.max_errors, int)
        assert isinstance(config.http_port, int)
        assert config.max_errors > 0
        assert config.http_port > 0

    def test_error_store_initialization(self):
        """Test that ErrorStore initializes correctly with config values."""
        config = load_typed_config("error-reporting")
        error_store = ErrorStore(max_errors=config.max_errors)
        
        # Verify error store is initialized
        assert error_store is not None
        assert hasattr(error_store, "errors")
        assert isinstance(error_store.errors, list)

    def test_config_attributes_are_valid(self):
        """Test that loaded config has valid attribute values."""
        config = load_typed_config("error-reporting")
        
        # Verify max_errors is a reasonable value
        assert config.max_errors >= 100
        assert config.max_errors <= 100000
        
        # Verify http_port is in valid range
        assert config.http_port > 1024
        assert config.http_port < 65535

    # Default value specifics are validated via schema; ensure ranges only
