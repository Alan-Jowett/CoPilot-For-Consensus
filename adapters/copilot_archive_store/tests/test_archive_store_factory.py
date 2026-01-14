# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for archive store factory with new config model."""

import pytest

from copilot_archive_store import create_archive_store
from copilot_archive_store.local_volume_archive_store import LocalVolumeArchiveStore
from copilot_config.generated.adapters.archive_store import (
    AdapterConfig_ArchiveStore,
    DriverConfig_ArchiveStore_Local,
)

class TestArchiveStoreFactory:
    """Test suite for create_archive_store factory with new config model."""

    def test_create_local_store_with_config(self, tmp_path):
        """Test factory call with DriverConfig object."""
        base_path = str(tmp_path / "archives")
        config = AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(archive_base_path=base_path),
        )

        store = create_archive_store(config)

        assert isinstance(store, LocalVolumeArchiveStore)
        assert str(store.base_path) == base_path

    def test_create_local_store_default_base_path(self):
        """Test local store with default base_path."""
        config = AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(),
        )
        store = create_archive_store(config)

        assert isinstance(store, LocalVolumeArchiveStore)
        # Path comparison - normalize for cross-platform compatibility
        assert str(store.base_path).replace("\\", "/") == "/data/raw_archives"

    def test_create_store_missing_config(self):
        """Test error when config is missing."""
        with pytest.raises(ValueError, match="archive_store config is required"):
            create_archive_store(None)

    def test_create_store_unknown_type(self):
        """Test error for unknown driver type."""
        with pytest.raises(ValueError, match="Unknown archive store driver"):
            create_archive_store(
                AdapterConfig_ArchiveStore(
                    archive_store_type="unknown",  # type: ignore[arg-type]
                    driver=DriverConfig_ArchiveStore_Local(),
                )
            )

    def test_factory_with_new_config_model_integration(self, tmp_path):
        """Integration test simulating load_service_config pattern."""
        base_path = str(tmp_path / "test_archives")
        config = AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(archive_base_path=base_path),
        )

        # Factory call using typed config model
        store = create_archive_store(config)

        assert isinstance(store, LocalVolumeArchiveStore)
        assert str(store.base_path) == base_path
