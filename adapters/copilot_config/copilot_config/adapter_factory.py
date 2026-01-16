# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generic helper for building adapter factories.

This module centralizes the common "switch on discriminant" pattern:
- accept a typed AdapterConfig_* object
- read its discriminant (e.g., embedding_backend_type)
- dispatch to the correct driver factory

Adapters can keep their public factory functions small and consistent.
"""

from __future__ import annotations

from typing import Callable, Mapping, TypeVar

from .schema_validation import validate_driver_config_against_schema


TConfig = TypeVar("TConfig")
TDriverConfig = TypeVar("TDriverConfig")
TAdapter = TypeVar("TAdapter")


def create_adapter(
    config: TConfig,
    *,
    adapter_name: str,
    get_driver_type: Callable[[TConfig], str],
    get_driver_config: Callable[[TConfig], TDriverConfig],
    drivers: Mapping[str, Callable[[TDriverConfig], TAdapter]],
    validate_schema: bool = True,
    schema_adapter: str | None = None,
) -> TAdapter:
    """Create an adapter instance from a typed adapter config.

    Args:
        config: Typed AdapterConfig_* instance.
        adapter_name: Human-friendly adapter name used in error messages.
        get_driver_type: Function that returns the discriminant string.
        get_driver_config: Function that returns the typed driver config.
        drivers: Mapping of normalized driver type -> factory callable.

    Returns:
        Adapter instance.

    Raises:
        ValueError: If config is missing or driver type is unknown.
    """
    if config is None:
        raise ValueError(f"{adapter_name} config is required")

    driver_type = str(get_driver_type(config)).lower()
    try:
        factory = drivers[driver_type]
    except KeyError as exc:
        supported = ", ".join(sorted(drivers.keys()))
        raise ValueError(
            f"Unknown {adapter_name} driver: {driver_type}. Supported drivers: {supported}"
        ) from exc

    driver_config = get_driver_config(config)
    if validate_schema:
        validate_driver_config_against_schema(
            adapter=schema_adapter or adapter_name,
            driver=driver_type,
            config=driver_config,
        )
    return factory(driver_config)
