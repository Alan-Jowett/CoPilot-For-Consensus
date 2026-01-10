# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for archive store factory with new config model."""

import pytest
from unittest.mock import MagicMock

from copilot_archive_store import create_archive_store
from copilot_archive_store.local_volume_archive_store import LocalVolumeArchiveStore


class MockDriverConfig:
    """Mock DriverConfig for testing."""
    
    def __init__(self, driver_name: str, config: dict):
        self.driver_name = driver_name
        self._config = config
    
    def __getattr__(self, name: str):
        """Support attribute access to config values."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self._config.get(name)
    
    def get(self, key, default=None):
        return self._config.get(key, default)


class TestArchiveStoreFactory:
    """Test suite for create_archive_store factory with new config model."""

    def test_create_local_store_with_config(self, tmp_path):
        """Test factory call with DriverConfig object."""
        base_path = str(tmp_path / "archives")
        driver_config = MockDriverConfig("local", {"base_path": base_path})
        
        store = create_archive_store("local", driver_config)
        
        assert isinstance(store, LocalVolumeArchiveStore)
        assert str(store.base_path) == base_path

    def test_create_local_store_default_base_path(self):
        """Test local store with default base_path."""
        driver_config = MockDriverConfig("local", {})
        store = create_archive_store("local", driver_config)
        
        assert isinstance(store, LocalVolumeArchiveStore)
        # Path comparison - normalize for cross-platform compatibility
        assert str(store.base_path).replace("\\", "/") == "/data/raw_archives"

    def test_create_store_missing_driver_name(self):
        """Test error when driver_name is missing."""
        driver_config = MockDriverConfig("local", {})
        with pytest.raises(ValueError, match="driver_name is required"):
            create_archive_store(None, driver_config)

    def test_create_store_empty_driver_name(self):
        """Test error when driver_name is empty string."""
        driver_config = MockDriverConfig("", {})
        with pytest.raises(ValueError, match="driver_name is required"):
            create_archive_store("", driver_config)

    def test_create_store_unknown_type(self):
        """Test error for unknown driver type."""
        driver_config = MockDriverConfig("unknown", {})
        with pytest.raises(ValueError, match="Unknown archive store driver"):
            create_archive_store("unknown", driver_config)

    def test_factory_with_new_config_model_integration(self, tmp_path):
        """Integration test simulating load_service_config pattern."""
        # Simulate what services do:
        # config = load_service_config("parsing")
        # archive_adapter = config.get_adapter("archive_store")
        # store = create_archive_store(archive_adapter.driver_name, archive_adapter.driver_config)
        
        base_path = str(tmp_path / "test_archives")
        driver_config = MockDriverConfig(
            "local",
            {
                "base_path": base_path,
            }
        )
        
        # Factory call using new config model
        store = create_archive_store(driver_config.driver_name, driver_config)
        
        assert isinstance(store, LocalVolumeArchiveStore)
        assert str(store.base_path) == base_path
