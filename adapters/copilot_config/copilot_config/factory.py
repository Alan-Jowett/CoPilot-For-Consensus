# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory helpers for configuration providers."""

import os
from typing import Optional

from .base import ConfigProvider
from .env_provider import EnvConfigProvider
from .static_provider import StaticConfigProvider
from .storage_provider import StorageConfigProvider


def create_config_provider(provider_type: Optional[str] = None, **kwargs) -> ConfigProvider:
    """Create a configuration provider by type.

    Supported types:
    - "env" (default)
    - "static"
    - "storage" / "document_store"
    """
    if provider_type is None:
        provider_type = os.environ.get("CONFIG_PROVIDER_TYPE", "env")

    provider_type = provider_type.lower()

    if provider_type == "env":
        return EnvConfigProvider()
    if provider_type == "static":
        return StaticConfigProvider()
    if provider_type in ("storage", "document_store", "doc_store"):
        return StorageConfigProvider(**kwargs)
    return EnvConfigProvider()
