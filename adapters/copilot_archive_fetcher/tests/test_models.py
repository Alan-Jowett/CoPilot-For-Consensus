# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for archive fetcher models."""

import pytest
from copilot_archive_fetcher import SourceConfig


class TestSourceConfig:
    """Tests for SourceConfig data class."""

    def test_source_config_creation(self):
        """Test creating a basic SourceConfig."""
        config = SourceConfig(name="test-source", source_type="http", url="https://example.com/archive.zip")

        assert config.name == "test-source"
        assert config.source_type == "http"
        assert config.url == "https://example.com/archive.zip"
        assert config.port is None
        assert config.username is None
        assert config.password is None
        assert config.folder is None
        assert config.enabled is True

    def test_source_config_with_all_fields(self):
        """Test creating SourceConfig with all optional fields."""
        config = SourceConfig(
            name="imap-source",
            source_type="imap",
            url="imap.example.com",
            port=993,
            username="user@example.com",
            password="secret",
            folder="INBOX",
        )

        assert config.name == "imap-source"
        assert config.source_type == "imap"
        assert config.url == "imap.example.com"
        assert config.port == 993
        assert config.username == "user@example.com"
        assert config.password == "secret"
        assert config.folder == "INBOX"

    def test_source_config_rsync(self):
        """Test creating a rsync SourceConfig."""
        config = SourceConfig(name="rsync-source", source_type="rsync", url="rsync://example.com/archive/")

        assert config.source_type == "rsync"
        assert config.url == "rsync://example.com/archive/"

    def test_source_config_local(self):
        """Test creating a local SourceConfig."""
        config = SourceConfig(name="local-source", source_type="local", url="/path/to/local/archive")

        assert config.source_type == "local"
        assert config.url == "/path/to/local/archive"

    def test_source_config_rejects_unknown_fields(self):
        """Test that from_mapping rejects unknown keys (schema coherence)."""
        with pytest.raises(ValueError, match="Unknown source fields"):
            SourceConfig.from_mapping(
                {
                    "name": "test-source",
                    "source_type": "http",
                    "url": "https://example.com/archive.zip",
                    "unexpected": "nope",
                }
            )
