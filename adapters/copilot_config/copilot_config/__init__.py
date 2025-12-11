# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Configuration Adapter.

A shared library for configuration management across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .config import (
    ConfigProvider,
    EnvConfigProvider,
    StaticConfigProvider,
    create_config_provider,
)

__all__ = [
    # Version
    "__version__",
    # Configuration
    "ConfigProvider",
    "EnvConfigProvider",
    "StaticConfigProvider",
    "create_config_provider",
]
