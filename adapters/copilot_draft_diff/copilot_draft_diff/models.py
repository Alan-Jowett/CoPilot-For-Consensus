# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for draft diffs."""

from dataclasses import dataclass
from typing import Any


@dataclass
class DraftDiff:
    """Represents a diff between two versions of a draft.

    Attributes:
        draft_name: Name of the draft (e.g., "draft-ietf-quic-transport")
        version_a: Version A identifier (e.g., "01", "02")
        version_b: Version B identifier (e.g., "02", "03")
        format: Format of the diff content (e.g., "html", "markdown", "text")
        content: The diff content in the specified format
        source: Source of the diff (e.g., "datatracker", "github", "local")
        url: Optional URL where the diff can be viewed
        metadata: Optional additional metadata as a dictionary
    """
    draft_name: str
    version_a: str
    version_b: str
    format: str
    content: str
    source: str
    url: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of the draft diff
        """
        return {
            "draft_name": self.draft_name,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "format": self.format,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "metadata": self.metadata,
        }
