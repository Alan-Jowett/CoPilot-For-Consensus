# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating archive fetchers."""

from .base import ArchiveFetcher
from .models import SourceConfig
from .rsync_fetcher import RsyncFetcher
from .http_fetcher import HTTPFetcher
from .local_fetcher import LocalFetcher
from .imap_fetcher import IMAPFetcher
from .exceptions import UnsupportedSourceTypeError


def create_fetcher(source: SourceConfig) -> ArchiveFetcher:
    """Factory function to create an archive fetcher.

    Args:
        source: Source configuration

    Returns:
        ArchiveFetcher instance

    Raises:
        UnsupportedSourceTypeError: If source type is not supported
    """
    source_type = source.source_type.lower()

    if source_type == "rsync":
        return RsyncFetcher(source)
    elif source_type == "http":
        return HTTPFetcher(source)
    elif source_type == "local":
        return LocalFetcher(source)
    elif source_type == "imap":
        return IMAPFetcher(source)
    else:
        raise UnsupportedSourceTypeError(f"Unsupported source type: {source_type}")
