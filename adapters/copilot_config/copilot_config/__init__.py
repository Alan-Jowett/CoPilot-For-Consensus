# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Configuration Adapter.

A shared library for loading hierarchical service configuration with adapters.
Services should call load_service_config(service_name) to get configuration.
"""

__version__ = "0.1.0"

from .models import (
    AdapterConfig,
    DriverConfig,
    ServiceConfig,
)
from .typed_config import load_driver_config, load_service_config

__all__ = [
    # Service configuration loaders
    "load_service_config",
    "load_driver_config",
    # Configuration data models
    "ServiceConfig",
    "AdapterConfig",
    "DriverConfig",
]
