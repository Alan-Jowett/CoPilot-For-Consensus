# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Configuration Adapter.

A shared library for configuration management across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .base import ConfigProvider
from .env_provider import EnvConfigProvider
from .static_provider import StaticConfigProvider
from .factory import create_config_provider
from .storage_provider import StorageConfigProvider
from .providers import (
    YamlConfigProvider,
    DocStoreConfigProvider,
)
from .schema_loader import (
    ConfigSchema,
    ConfigSchemaError,
    ConfigValidationError,
    FieldSpec,
    SchemaConfigLoader,
    load_config,
)
from .typed_config import (
    TypedConfig,
    load_typed_config,
)

__all__ = [
    # Version
    "__version__",
    # Configuration Providers
    "ConfigProvider",
    "EnvConfigProvider",
    "StaticConfigProvider",
    "StorageConfigProvider",
    "YamlConfigProvider",
    "DocStoreConfigProvider",
    "create_config_provider",
    # Schema-driven configuration
    "ConfigSchema",
    "ConfigSchemaError",
    "ConfigValidationError",
    "FieldSpec",
    "SchemaConfigLoader",
    "load_config",
    # Typed configuration
    "TypedConfig",
    "load_typed_config",
]
