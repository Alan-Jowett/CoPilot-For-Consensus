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
    DocStoreConfigProvider,
)
from .secret_provider import SecretConfigProvider
from .schema_loader import (
    ConfigSchema,
    ConfigSchemaError,
    ConfigValidationError,
    FieldSpec,
    SchemaConfigLoader,
)
from .typed_config import (
    TypedConfig,
    load_typed_config,  # The ONLY recommended way to load config
)
from .discovery import get_configuration_schema_response

__all__ = [
    # Version
    "__version__",
    # Configuration Providers
    "ConfigProvider",
    "EnvConfigProvider",
    "StaticConfigProvider",
    "StorageConfigProvider",
    "DocStoreConfigProvider",
    "SecretConfigProvider",
    "create_config_provider",
    # Schema-driven configuration
    "ConfigSchema",
    "ConfigSchemaError",
    "ConfigValidationError",
    "FieldSpec",
    "SchemaConfigLoader",
    # Typed configuration (RECOMMENDED WAY)
    "TypedConfig",
    "load_typed_config",  # Only public config loading function
    # Configuration discovery
    "get_configuration_schema_response",
]
