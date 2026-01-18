# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for archive fetcher.

This adapter intentionally uses a strict, schema-aligned source model.
See docs/schemas/documents/sources.schema.json.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

_ALLOWED_SOURCE_TYPES = {"local", "http", "rsync", "imap"}

SourceType = Literal["local", "http", "rsync", "imap"]


@dataclass
class SourceConfig:
    """Configuration for an archive ingestion source.

    This model matches the persisted source documents and is intentionally strict:
    - `source_type` must be one of: local/http/rsync/imap (case-insensitive input)
    - Unknown fields are rejected by `from_mapping()`
    """

    _id: str | None = None
    name: str = ""
    source_type: str = ""
    url: str = ""

    port: int | None = None
    username: str | None = None
    password: str | None = None
    folder: str | None = None

    enabled: bool = True
    schedule: str | None = None

    created_at: str | None = None
    updated_at: str | None = None
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_error: str | None = None
    next_run_at: str | None = None

    files_processed: int = 0
    files_skipped: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("SourceConfig.name must be a non-empty string")

        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("SourceConfig.url must be a non-empty string")

        if not isinstance(self.source_type, str) or not self.source_type.strip():
            raise ValueError("SourceConfig.source_type must be a non-empty string")

        self.source_type = self.source_type.lower()
        if self.source_type not in _ALLOWED_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported source_type '{self.source_type}'. " f"Allowed: {sorted(_ALLOWED_SOURCE_TYPES)}"
            )

    @property
    def source_type_normalized(self) -> SourceType:
        """Return the validated, normalized source type.

        `__post_init__` guarantees the stored value is one of the allowed
        source types.
        """

        return cast(SourceType, self.source_type)

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> SourceConfig:
        """Create a SourceConfig from a raw mapping.

        Rejects unknown keys to keep source documents schema-coherent.
        """
        if not source:
            raise ValueError("Source configuration is empty")

        allowed_keys = {
            "_id",
            "name",
            "source_type",
            "url",
            "port",
            "username",
            "password",
            "folder",
            "enabled",
            "schedule",
            "created_at",
            "updated_at",
            "last_run_at",
            "last_run_status",
            "last_error",
            "next_run_at",
            "files_processed",
            "files_skipped",
        }

        unknown = set(source.keys()) - allowed_keys
        if unknown:
            raise ValueError(f"Unknown source fields: {sorted(unknown)}")

        required = {"name", "source_type", "url"}
        missing = required - set(source.keys())
        if missing:
            raise ValueError(f"Source configuration missing required fields: {sorted(missing)}")

        return cls(**dict(source))
