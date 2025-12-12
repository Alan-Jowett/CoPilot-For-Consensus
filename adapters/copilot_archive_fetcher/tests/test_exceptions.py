# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for archive fetcher exceptions."""

import pytest
from copilot_archive_fetcher import (
    ArchiveFetcherError,
    UnsupportedSourceTypeError,
    FetchError,
    ConfigurationError,
)


class TestExceptions:
    """Tests for archive fetcher exceptions."""

    def test_archive_fetcher_error(self):
        """Test ArchiveFetcherError can be raised and caught."""
        with pytest.raises(ArchiveFetcherError):
            raise ArchiveFetcherError("Test error")

    def test_unsupported_source_type_error(self):
        """Test UnsupportedSourceTypeError is a subclass of ArchiveFetcherError."""
        with pytest.raises(ArchiveFetcherError):
            raise UnsupportedSourceTypeError("Unknown type")

    def test_fetch_error(self):
        """Test FetchError is a subclass of ArchiveFetcherError."""
        with pytest.raises(ArchiveFetcherError):
            raise FetchError("Fetch failed")

    def test_configuration_error(self):
        """Test ConfigurationError is a subclass of ArchiveFetcherError."""
        with pytest.raises(ArchiveFetcherError):
            raise ConfigurationError("Invalid config")

    def test_exception_inheritance(self):
        """Test exception inheritance chain."""
        assert issubclass(UnsupportedSourceTypeError, ArchiveFetcherError)
        assert issubclass(FetchError, ArchiveFetcherError)
        assert issubclass(ConfigurationError, ArchiveFetcherError)
