# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Configuration data models for hierarchical service configuration."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriverConfig:
    """Configuration for a specific driver within an adapter.

    Attributes:
        driver_name: Name of the driver (e.g., "rabbitmq", "openai", "mongodb")
        config: Dictionary of driver-specific configuration values
        allowed_keys: Set of schema-allowed configuration keys
    """
    driver_name: str
    config: dict[str, Any] = field(default_factory=dict)
    allowed_keys: set[str] = field(default_factory=set)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a driver config value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to driver config values.

        Returns the value if present in config, None if the key is schema-allowed
        but not provided, or raises AttributeError if the key is not in the schema.

        Args:
            name: Configuration key

        Returns:
            Configuration value or None when not provided

        Raises:
            AttributeError: If key is not in schema
        """
        if name in ('driver_name', 'config', 'allowed_keys'):
            return object.__getattribute__(self, name)

        # If the key is present in the config dict, always return it
        if name in self.config:
            return self.config[name]

        # If the key is defined in the driver schema, return None (optional)
        if name in self.allowed_keys:
            return None

        # Unknown keys (not in schema) raise AttributeError
        raise AttributeError(
            f"DriverConfig '{self.driver_name}' has no schema-defined key '{name}'. "
            f"Allowed keys: {sorted(self.allowed_keys)}"
        )

    def was_provided(self, key: str) -> bool:
        """Return True if the key was explicitly provided in the config.

        This distinguishes between "missing" and "present but None".

        Args:
            key: Configuration key to check

        Returns:
            True if key exists in the underlying config dict
        """
        return key in self.config

    def with_updates(self, **updates: Any) -> "DriverConfig":
        """Create a new DriverConfig with updated field values.

        This method creates a new DriverConfig instance with the same
        driver_name and allowed_keys, but with specified fields updated.
        Fields that are not in allowed_keys will raise AttributeError.

        Args:
            **updates: Field name and value pairs to update

        Returns:
            New DriverConfig instance with updates applied

        Raises:
            AttributeError: If any update key is not in allowed_keys
        """
        # Validate that all update keys are allowed
        for key in updates:
            if key not in self.allowed_keys:
                raise AttributeError(
                    f"Cannot update '{key}' on DriverConfig '{self.driver_name}'. "
                    f"Allowed keys: {sorted(self.allowed_keys)}"
                )

        # Create new config dict with updates
        new_config = {**self.config, **updates}

        return DriverConfig(
            driver_name=self.driver_name,
            config=new_config,
            allowed_keys=self.allowed_keys,
        )


@dataclass
class AdapterConfig:
    """Configuration for a single adapter instance.

    Attributes:
        adapter_type: Name of the adapter (e.g., "message_bus", "document_store")
        driver_name: Selected driver for this adapter (e.g., "rabbitmq", "mongodb")
        driver_config: DriverConfig object with driver-specific settings
    """
    adapter_type: str
    driver_name: str
    driver_config: DriverConfig

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to delegate to driver_config.

        Args:
            name: Configuration key

        Returns:
            Value from driver_config

        Raises:
            AttributeError: If key not found
        """
        if name in ('adapter_type', 'driver_name', 'driver_config'):
            return object.__getattribute__(self, name)

        # Delegate to driver_config
        return getattr(self.driver_config, name)

    def was_provided(self, key: str) -> bool:
        """Return True if the key was explicitly provided in the driver config.

        Args:
            key: Configuration key to check

        Returns:
            True if key exists in the underlying driver config dict
        """
        return self.driver_config.was_provided(key)


@dataclass
class ServiceConfig:
    """Top-level configuration for a microservice.

    Attributes:
        service_name: Name of the service
        service_settings: Dictionary of service-specific settings
        adapters: List of configured adapters
        schema_version: Schema version string (semver)
        min_service_version: Minimum service version required (semver)
    """
    service_name: str
    service_settings: dict[str, Any] = field(default_factory=dict)
    adapters: list[AdapterConfig] = field(default_factory=list)
    schema_version: str | None = None
    min_service_version: str | None = None
    allowed_service_settings: set[str] = field(default_factory=set)

    def get_adapter(self, adapter_type: str) -> AdapterConfig | None:
        """Get adapter configuration by type.

        Args:
            adapter_type: Adapter type name (e.g., "message_bus")

        Returns:
            AdapterConfig instance or None if not found
        """
        for adapter in self.adapters:
            if adapter.adapter_type == adapter_type:
                return adapter
        return None

    def get_service_setting(self, key: str, default: Any = None) -> Any:
        """Get a service setting value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return self.service_settings.get(key, default)

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to service settings.

        Args:
            name: Setting key

        Returns:
            Setting value

        Raises:
            AttributeError: If key not found
        """
        if name in ('service_name', 'service_settings', 'adapters', 'schema_version', 'min_service_version'):
            return object.__getattribute__(self, name)

        # If the key is defined in the service schema, return the value or None
        if name in self.allowed_service_settings:
            return self.service_settings.get(name, None)

        # Unknown keys (not in schema) raise AttributeError
        raise AttributeError(
            f"ServiceConfig has no schema-defined key '{name}'. "
            f"Allowed settings: {sorted(self.allowed_service_settings)}"
        )

    def was_provided(self, key: str) -> bool:
        """Return True if the service setting key was explicitly provided.

        Args:
            key: Setting key to check

        Returns:
            True if key exists in the underlying service_settings dict
        """
        return key in self.service_settings
