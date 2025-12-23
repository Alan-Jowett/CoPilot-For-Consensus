# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for archive fetcher."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceConfig:
    """Configuration for an archive source."""

    name: str
    """Name identifier for the source."""

    source_type: str
    """Type of source: 'rsync', 'http', 'local', 'imap'."""

    url: str
    """URL or path for the source."""

    port: Optional[int] = None
    """Port number (for IMAP and other services)."""

    username: Optional[str] = None
    """Username for authentication."""

    password: Optional[str] = None
    """Password for authentication."""

    folder: Optional[str] = None
    """Folder or path specification (e.g., IMAP folder)."""
