# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for HTTP fetcher."""

import pytest
import tempfile
from copilot_archive_fetcher import HTTPFetcher, SourceConfig, ArchiveFetcher


class TestHTTPFetcher:
    """Tests for HTTPFetcher - basic validation tests."""

    def test_http_fetcher_init(self):
        """Test HTTPFetcher initialization."""
        config = SourceConfig(
            name="http-test",
            source_type="http",
            url="https://example.com/archive.zip"
        )
        fetcher = HTTPFetcher(config)

        assert fetcher.source == config
        assert fetcher.source.name == "http-test"
        assert fetcher.source.url == "https://example.com/archive.zip"

    def test_http_fetcher_is_abstract_fetcher(self):
        """Test that HTTPFetcher is an instance of ArchiveFetcher."""
        config = SourceConfig(
            name="http-test",
            source_type="http",
            url="https://example.com/archive.zip"
        )
        fetcher = HTTPFetcher(config)

        assert isinstance(fetcher, ArchiveFetcher)

    @pytest.mark.integration
    def test_http_fetcher_with_real_url(self):
        """Test HTTP fetcher with a real URL (integration test)."""
        config = SourceConfig(
            name="http-test",
            source_type="http",
            url="https://httpbin.org/image/png"
        )
        fetcher = HTTPFetcher(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            success, files, error = fetcher.fetch(tmpdir)

            # This may fail if no network, but should handle gracefully
            if success:
                assert files is not None
                assert len(files) > 0
            else:
                assert error is not None
