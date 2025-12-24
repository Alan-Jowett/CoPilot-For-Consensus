# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for config registry."""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class ConfigDocument(BaseModel):
    """Configuration document model."""

    service_name: str = Field(..., description="Service name (e.g., 'parsing')")
    environment: str = Field(
        default="default", description="Environment (default, dev, staging, prod)"
    )
    version: int = Field(default=1, description="Configuration version")
    config_data: dict[str, Any] = Field(..., description="Configuration data")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system", description="User who created this config")
    comment: str = Field(default="", description="Change comment")


class ConfigUpdate(BaseModel):
    """Configuration update request."""

    config_data: dict[str, Any] = Field(..., description="Configuration data")
    comment: str = Field(default="", description="Change comment")
    created_by: str = Field(default="system", description="User making the change")


class ConfigDiff(BaseModel):
    """Configuration diff result."""

    service_name: str
    environment: str
    old_version: int
    new_version: int
    added: dict[str, Any] = Field(default_factory=dict)
    removed: dict[str, Any] = Field(default_factory=dict)
    changed: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ConfigNotification(BaseModel):
    """Configuration change notification."""

    service_name: str
    environment: str
    version: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    change_type: str = Field(..., description="Type of change: created, updated, deleted")
    comment: str = Field(default="")
