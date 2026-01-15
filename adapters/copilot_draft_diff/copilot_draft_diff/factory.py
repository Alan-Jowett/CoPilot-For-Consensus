# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating draft diff providers (DriverConfig-based)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.draft_diff_provider import (
    AdapterConfig_DraftDiffProvider,
    DriverConfig_DraftDiffProvider_Datatracker,
    DriverConfig_DraftDiffProvider_Mock,
)

from .datatracker_provider import DatatrackerDiffProvider
from .mock_provider import MockDiffProvider
from .provider import DraftDiffProvider


DraftDiffProviderDriverConfig: TypeAlias = (
    DriverConfig_DraftDiffProvider_Datatracker | DriverConfig_DraftDiffProvider_Mock
)
DraftDiffProviderDriverConfigLike: TypeAlias = DraftDiffProviderDriverConfig | Mapping[str, Any] | None


def create_draft_diff_provider(config: AdapterConfig_DraftDiffProvider) -> DraftDiffProvider:
    """Create a draft diff provider from typed configuration."""

    return create_adapter(
        config,
        adapter_name="draft_diff_provider",
        schema_adapter="draft_diff_provider",
        get_driver_type=lambda c: c.draft_diff_provider_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "datatracker": DatatrackerDiffProvider.from_config,
            "mock": MockDiffProvider.from_config,
        },
    )


def _coerce_driver_config(
    driver_name: str,
    driver_config: DraftDiffProviderDriverConfigLike,
) -> DraftDiffProviderDriverConfig:
    name = str(driver_name).lower()

    if name == "datatracker":
        if driver_config is None:
            return DriverConfig_DraftDiffProvider_Datatracker()
        if isinstance(driver_config, DriverConfig_DraftDiffProvider_Datatracker):
            return driver_config
        if isinstance(driver_config, Mapping):
            return DriverConfig_DraftDiffProvider_Datatracker(**dict(driver_config))
        raise TypeError(
            "driver_config must be a mapping or DriverConfig_DraftDiffProvider_Datatracker for 'datatracker'"
        )

    if name == "mock":
        if driver_config is None:
            return DriverConfig_DraftDiffProvider_Mock()
        if isinstance(driver_config, DriverConfig_DraftDiffProvider_Mock):
            return driver_config
        if isinstance(driver_config, Mapping):
            return DriverConfig_DraftDiffProvider_Mock(**dict(driver_config))
        raise TypeError("driver_config must be a mapping or DriverConfig_DraftDiffProvider_Mock for 'mock'")

    raise ValueError(f"Unknown provider driver: {driver_name}.")


class DiffProviderFactory:
    """Factory for creating and managing draft diff providers.

    This factory supports creating providers based on configuration
    or environment variables, making it easy to switch between different
    backends (e.g., for testing vs production).
    """

    # Registry of available provider types
    _providers: dict[str, type[DraftDiffProvider]] = {
        "datatracker": DatatrackerDiffProvider,
        "mock": MockDiffProvider,
    }

    @classmethod
    def create(
        cls,
        driver_name: str | None = None,
        driver_config: DraftDiffProviderDriverConfigLike = None,
    ) -> DraftDiffProvider:
        """Create a draft diff provider instance from DriverConfig.

        Args:
            driver_name: Provider driver (required). Options: "datatracker", "mock"
            driver_config: DriverConfig-like object; supports `.get()` or `dict`

        Returns:
            Instance of the requested DraftDiffProvider

        Raises:
            ValueError: If driver_name is not supported or missing
        """
        if not driver_name:
            raise ValueError(
                "driver_name parameter is required. "
                f"Available providers: {', '.join(cls._providers.keys())}"
            )

        name = str(driver_name).lower()
        if name not in cls._providers:
            raise ValueError(
                f"Unknown provider driver: {driver_name}. "
                f"Available providers: {', '.join(cls._providers.keys())}"
            )

        # Built-in drivers use schema-generated typed configs.
        if name in ("datatracker", "mock"):
            typed_driver_config = _coerce_driver_config(name, driver_config)
            typed_config = AdapterConfig_DraftDiffProvider(
                draft_diff_provider_type=name,  # type: ignore[arg-type]
                driver=typed_driver_config,
            )
            return create_draft_diff_provider(typed_config)

        # Custom providers (out of schema) remain supported via registration.
        provider_class = cls._providers[name]
        if isinstance(driver_config, Mapping):
            return provider_class(**dict(driver_config))
        return provider_class()

    @classmethod
    def register_provider(cls, name: str, provider_class: type[DraftDiffProvider]) -> None:
        """Register a new provider type.

        This allows external code to register custom provider implementations.

        Args:
            name: Name for the provider type
            provider_class: Class that implements DraftDiffProvider

        Raises:
            TypeError: If provider_class doesn't inherit from DraftDiffProvider
        """
        if not issubclass(provider_class, DraftDiffProvider):
            raise TypeError(
                f"Provider class must inherit from DraftDiffProvider, "
                f"got {provider_class.__name__}"
            )

        cls._providers[name] = provider_class


def create_diff_provider(driver_name: str | None = None,
                        driver_config: DraftDiffProviderDriverConfigLike = None) -> DraftDiffProvider:
    """Convenience function to create a draft diff provider (DriverConfig-based).

    Args:
        driver_name: Provider driver (required). Options: "datatracker", "mock"
        driver_config: Optional DriverConfig-like object

    Returns:
        Configured DraftDiffProvider instance

    Raises:
        ValueError: If driver_name is not supported or missing
    """
    return DiffProviderFactory.create(driver_name, driver_config)
