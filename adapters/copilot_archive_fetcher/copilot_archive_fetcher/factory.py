# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating archive fetchers."""

from .base import ArchiveFetcher
from .exceptions import UnsupportedSourceTypeError
from .http_fetcher import HTTPFetcher
from .imap_fetcher import IMAPFetcher
from .local_fetcher import LocalFetcher
from .models import SourceConfig
from .rsync_fetcher import RsyncFetcher


def create_fetcher(source: SourceConfig | dict) -> ArchiveFetcher:
    """Factory function to create an archive fetcher.

    Args:
        source: Source configuration

    Returns:
        ArchiveFetcher instance

    Raises:
        UnsupportedSourceTypeError: If source type is not supported
    """
    source_obj = source if isinstance(source, SourceConfig) else SourceConfig(**source)
    source_type = source_obj.source_type.lower()

    if source_type == "rsync":
        return RsyncFetcher.from_config(source_obj)
    elif source_type == "http":
        return HTTPFetcher.from_config(source_obj)
    elif source_type == "local":
        return LocalFetcher.from_config(source_obj)
    elif source_type == "imap":
        return IMAPFetcher.from_config(source_obj)
    else:
        raise UnsupportedSourceTypeError(f"Unsupported source type: {source_type}")
