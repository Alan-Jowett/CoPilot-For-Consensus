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

    Args:
        provider_type: Type of config provider (required).
                      Options: "env", "static", "storage"/"document_store"/"doc_store"
        **kwargs: Additional configuration for the provider (e.g., for storage provider)

    Returns:
        ConfigProvider instance

    Raises:
        ValueError: If provider_type is unknown or required parameters are missing

    Supported types:
    - "env": Environment variable configuration provider
    - "static": Static configuration provider
    - "storage"/"document_store"/"doc_store": Storage-backed configuration provider
    """
    if not provider_type:
        raise ValueError(
            "provider_type parameter is required. "
            "Must be one of: env, static, storage"
        )

    provider_type = provider_type.lower()

    if provider_type == "env":
        return EnvConfigProvider()
    if provider_type == "static":
        return StaticConfigProvider()
    if provider_type in ("storage", "document_store", "doc_store"):
        return StorageConfigProvider(**kwargs)
    
    raise ValueError(
        f"Unknown provider_type: {provider_type}. "
        f"Must be one of: env, static, storage"
    )
