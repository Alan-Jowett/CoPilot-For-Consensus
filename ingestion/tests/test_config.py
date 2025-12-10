# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for configuration module."""

import os
import tempfile
from app.config import SourceConfig, IngestionConfig


class TestSourceConfig:
    """Tests for SourceConfig class."""

    def test_source_config_from_dict_basic(self):
        """Test creating SourceConfig from basic dictionary."""
        config_dict = {
            "name": "test-source",
            "source_type": "rsync",
            "url": "rsync.example.com::archive/",
        }
        config = SourceConfig.from_dict(config_dict)

        assert config.name == "test-source"
        assert config.source_type == "rsync"
        assert config.url == "rsync.example.com::archive/"
        assert config.enabled is True

    def test_source_config_from_dict_with_env_vars(self):
        """Test environment variable expansion in SourceConfig."""
        os.environ["TEST_PASSWORD"] = "secret123"

        config_dict = {
            "name": "test-imap",
            "source_type": "imap",
            "url": "imap.example.com",
            "username": "user@example.com",
            "password": "${TEST_PASSWORD}",
        }
        config = SourceConfig.from_dict(config_dict)

        assert config.password == "secret123"

    def test_source_config_disabled(self):
        """Test disabled source."""
        config_dict = {
            "name": "disabled-source",
            "source_type": "http",
            "url": "http://example.com/archive.mbox",
            "enabled": False,
        }
        config = SourceConfig.from_dict(config_dict)

        assert config.enabled is False

    def test_source_config_extra_fields(self):
        """Test extra fields in SourceConfig."""
        config_dict = {
            "name": "test-source",
            "source_type": "rsync",
            "url": "rsync.example.com::archive/",
            "custom_field": "custom_value",
        }
        config = SourceConfig.from_dict(config_dict)

        assert config.extra["custom_field"] == "custom_value"


class TestIngestionConfig:
    """Tests for IngestionConfig class."""

    def test_ingestion_config_from_env(self):
        """Test loading IngestionConfig from environment variables."""
        os.environ["STORAGE_PATH"] = "/custom/storage"
        os.environ["MESSAGE_BUS_HOST"] = "custom-host"
        os.environ["LOG_LEVEL"] = "DEBUG"

        config = IngestionConfig.from_env()

        assert config.storage_path == "/custom/storage"
        assert config.message_bus_host == "custom-host"
        assert config.log_level == "DEBUG"

    def test_ingestion_config_defaults(self):
        """Test IngestionConfig defaults."""
        # Clear environment variables
        for key in [
            "STORAGE_PATH",
            "MESSAGE_BUS_HOST",
            "MESSAGE_BUS_PORT",
            "RETRY_MAX_ATTEMPTS",
        ]:
            os.environ.pop(key, None)

        config = IngestionConfig.from_env()

        assert config.storage_path == "/data/raw_archives"
        assert config.message_bus_host == "messagebus"
        assert config.message_bus_port == 5672
        assert config.retry_max_attempts == 3

    def test_ingestion_config_ensure_storage_path(self):
        """Test storage path creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "new_storage", "path")

            config = IngestionConfig(storage_path=storage_path)
            config.ensure_storage_path()

            assert os.path.exists(storage_path)
            assert os.path.exists(os.path.join(storage_path, "metadata"))

    def test_get_enabled_sources(self):
        """Test getting enabled sources."""
        sources = [
            SourceConfig(name="enabled1", source_type="rsync", url="url1", enabled=True),
            SourceConfig(name="disabled", source_type="rsync", url="url2", enabled=False),
            SourceConfig(name="enabled2", source_type="http", url="url3", enabled=True),
        ]

        config = IngestionConfig(sources=sources)
        enabled = config.get_enabled_sources()

        assert len(enabled) == 2
        assert enabled[0].name == "enabled1"
        assert enabled[1].name == "enabled2"
