# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for archive fetcher factory."""

import pytest
from copilot_archive_fetcher import (
    HTTPFetcher,
    IMAPFetcher,
    LocalFetcher,
    RsyncFetcher,
    SourceConfig,
    UnsupportedSourceTypeError,
    create_fetcher,
)


class TestFetcherFactory:
    """Tests for create_fetcher factory function."""

    def test_create_rsync_fetcher(self):
        """Test creating an RsyncFetcher."""
        config = SourceConfig(
            name="rsync-source",
            source_type="rsync",
            url="rsync://example.com/archive/"
        )
        fetcher = create_fetcher(config)
        assert isinstance(fetcher, RsyncFetcher)

    def test_create_http_fetcher(self):
        """Test creating an HTTPFetcher."""
        config = SourceConfig(
            name="http-source",
            source_type="http",
            url="https://example.com/archive.zip"
        )
        fetcher = create_fetcher(config)
        assert isinstance(fetcher, HTTPFetcher)

    def test_create_local_fetcher(self):
        """Test creating a LocalFetcher."""
        config = SourceConfig(
            name="local-source",
            source_type="local",
            url="/path/to/archive"
        )
        fetcher = create_fetcher(config)
        assert isinstance(fetcher, LocalFetcher)

    def test_create_imap_fetcher(self):
        """Test creating an IMAPFetcher."""
        config = SourceConfig(
            name="imap-source",
            source_type="imap",
            url="imap.example.com"
        )
        fetcher = create_fetcher(config)
        assert isinstance(fetcher, IMAPFetcher)

    def test_create_fetcher_case_insensitive(self):
        """Test that source type is case-insensitive."""
        config = SourceConfig(
            name="http-source",
            source_type="HTTP",
            url="https://example.com/archive.zip"
        )
        fetcher = create_fetcher(config)
        assert isinstance(fetcher, HTTPFetcher)

    def test_create_fetcher_unsupported_type(self):
        """Test that unsupported source type raises error."""
        config = SourceConfig(
            name="unknown-source",
            source_type="ftp",
            url="ftp://example.com/archive"
        )
        with pytest.raises(UnsupportedSourceTypeError) as exc_info:
            create_fetcher(config)
        assert "Unsupported source type" in str(exc_info.value)
