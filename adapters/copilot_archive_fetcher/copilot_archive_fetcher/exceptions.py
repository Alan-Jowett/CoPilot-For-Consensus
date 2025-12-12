# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Exceptions for archive fetcher operations."""


class ArchiveFetcherError(Exception):
    """Base exception for archive fetcher errors."""
    pass


class UnsupportedSourceTypeError(ArchiveFetcherError):
    """Raised when an unsupported source type is encountered."""
    pass


class FetchError(ArchiveFetcherError):
    """Raised when a fetch operation fails."""
    pass


class ConfigurationError(ArchiveFetcherError):
    """Raised when there is a configuration error."""
    pass
