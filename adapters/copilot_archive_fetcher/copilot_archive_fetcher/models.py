# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for archive fetcher."""

from dataclasses import dataclass


@dataclass
class SourceConfig:
    """Configuration for an archive source."""

    name: str
    """Name identifier for the source."""

    source_type: str
    """Type of source: 'rsync', 'http', 'local', 'imap'."""

    url: str
    """URL or path for the source."""

    port: int | None = None
    """Port number (for IMAP and other services)."""

    username: str | None = None
    """Username for authentication."""

    password: str | None = None
    """Password for authentication."""

    folder: str | None = None
    """Folder or path specification (e.g., IMAP folder)."""
