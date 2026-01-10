# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating draft diff providers (DriverConfig-based)."""

from typing import Any

from .datatracker_provider import DatatrackerDiffProvider
from .mock_provider import MockDiffProvider
from .provider import DraftDiffProvider


class DiffProviderFactory:
    """Factory for creating and managing draft diff providers.

    This factory supports creating providers based on configuration
    or environment variables, making it easy to switch between different
    backends (e.g., for testing vs production).
    """

    # Registry of available provider types
    _providers = {
        "datatracker": DatatrackerDiffProvider,
        "mock": MockDiffProvider,
    }

    @classmethod
    def create(cls, driver_name: str | None = None, driver_config: Any | None = None) -> DraftDiffProvider:
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

        provider_class = cls._providers[name]
        cfg = driver_config or {}

        # Create provider via from_config when available; fallback to kwargs
        from_cfg = getattr(provider_class, "from_config", None)
        if callable(from_cfg):
            return from_cfg(cfg)
        if isinstance(cfg, dict):
            return provider_class(**cfg)
        # No config mapping; instantiate with defaults
        return provider_class()

    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
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
                        driver_config: Any | None = None) -> DraftDiffProvider:
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
