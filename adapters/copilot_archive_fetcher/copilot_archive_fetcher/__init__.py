# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Archive Fetcher Adapter.

A shared library for fetching archives from various sources (rsync, HTTP, local filesystem, IMAP)
in the Copilot-for-Consensus system. Supports multiple source types with a unified interface.
"""

__version__ = "0.1.0"

from .base import ArchiveFetcher, calculate_file_hash
from .exceptions import (
    ArchiveFetcherError,
    ConfigurationError,
    FetchError,
    UnsupportedSourceTypeError,
)
from .factory import create_fetcher
from .http_fetcher import HTTPFetcher
from .imap_fetcher import IMAPFetcher
from .local_fetcher import LocalFetcher
from .models import SourceConfig
from .rsync_fetcher import RsyncFetcher

__all__ = [
    # Version
    "__version__",
    # Base classes and utilities
    "ArchiveFetcher",
    "calculate_file_hash",
    # Models
    "SourceConfig",
    # Fetchers
    "RsyncFetcher",
    "HTTPFetcher",
    "LocalFetcher",
    "IMAPFetcher",
    # Factory
    "create_fetcher",
    # Exceptions
    "ArchiveFetcherError",
    "UnsupportedSourceTypeError",
    "FetchError",
    "ConfigurationError",
]
