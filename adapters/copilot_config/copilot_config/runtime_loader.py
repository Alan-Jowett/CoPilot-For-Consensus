# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Runtime loader for typed configuration dataclasses.

This module provides the get_config() function that returns strongly-typed
configuration objects generated from JSON schemas.
"""

import importlib
import json
import os
from pathlib import Path
from typing import Any, TypeVar

from .models import ServiceConfig

T = TypeVar("T")


def _to_python_class_name(name: str, prefix: str = "") -> str:
    """Convert a schema name to a Python class name (must match generator logic).

    Args:
        name: The schema name (e.g., "ingestion", "message_bus")
        prefix: Optional prefix (e.g., "ServiceConfig", "AdapterConfig")

    Returns:
        PascalCase class name
    """
    # Convert snake_case to PascalCase
    parts = name.split("_")
    pascal_name = "".join(p.capitalize() for p in parts)
    if prefix:
        return f"{prefix}_{pascal_name}"
    return pascal_name


def _resolve_schema_directory() -> Path:
    """Resolve the schema directory path."""
    # Try environment variable first
    if "SCHEMA_DIR" in os.environ:
        return Path(os.environ["SCHEMA_DIR"])

    # Try common locations
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "schemas" / "configs"
        if candidate.exists():
            return candidate

    # Fallback to default
    return Path.cwd() / "docs" / "schemas" / "configs"


def _load_and_populate_driver_config(
    driver_schema: dict[str, Any],
    common_properties: dict[str, Any] | None,
    secret_provider: Any | None,
) -> Any:
    """Load and populate a driver configuration.

    Args:
        driver_schema: The driver schema dictionary
        common_properties: Common properties from adapter schema
        secret_provider: Optional secret provider

    Returns:
        Dictionary of config values that can be used to construct a driver dataclass instance.
    """
    # Merge driver properties with common properties
    properties = driver_schema.get("properties", {})
    if common_properties:
        for key, value in common_properties.items():
            if key not in properties:
                properties[key] = value

    # Extract config values from environment/secrets
    config_dict = {}

    for prop_name, prop_spec in properties.items():
        value = None

        if prop_spec.get("source") == "env":
            env_var = prop_spec.get("env_var")
            env_vars = env_var if isinstance(env_var, list) else [env_var]

            for candidate in env_vars:
                if not candidate:
                    continue
                candidate_value = os.environ.get(candidate)
                if candidate_value is not None:
                    value = candidate_value
                    break

            if value is not None:
                # Type conversion
                if prop_spec.get("type") in ("int", "integer"):
                    try:
                        value = int(value)
                    except ValueError:
                        # Ignore conversion errors and keep the original string value.
                        pass
                elif prop_spec.get("type") in ("bool", "boolean"):
                    value = value.lower() in ("true", "1", "yes")
            elif prop_spec.get("default") is not None:
                value = prop_spec.get("default")

        elif prop_spec.get("source") == "secret" and secret_provider:
            secret_name = prop_spec.get("secret_name")
            secret_names = secret_name if isinstance(secret_name, list) else [secret_name]

            for candidate in secret_names:
                if not candidate:
                    continue
                try:
                    secret_value = secret_provider.get(candidate)
                    if secret_value is not None:
                        value = secret_value
                        break
                except Exception:
                    # Secret providers may throw for missing/denied secrets; ignore and try next.
                    continue

        else:
            # Field has no source - apply default if present
            if prop_spec.get("default") is not None:
                value = prop_spec.get("default")

        if value is not None:
            config_dict[prop_name] = value

    return config_dict


def _load_adapter_config(
    adapter_name: str,
    adapter_schema: dict[str, Any],
    schema_dir: Path,
    secret_provider: Any | None,
) -> tuple[str, dict[str, Any]] | None:
    """Load adapter configuration.

    Args:
        adapter_name: Name of the adapter
        adapter_schema: Adapter schema dictionary
        schema_dir: Path to schema directory
        secret_provider: Optional secret provider

    Returns:
        Tuple of (driver_name, driver_config_dict) or None if adapter not configured
    """
    discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})

    if not discriminant_info:
        # Skip composite adapters for now
        return None

    discriminant_env_var = discriminant_info.get("env_var")
    selected_driver = os.environ.get(discriminant_env_var) if discriminant_env_var else None

    if not selected_driver:
        is_required = discriminant_info.get("required", False)
        default_driver = discriminant_info.get("default")

        if is_required and not default_driver:
            raise ValueError(
                f"Adapter {adapter_name} requires discriminant configuration: "
                f"set environment variable {discriminant_env_var}"
            )

        if default_driver:
            selected_driver = default_driver
        else:
            # Optional adapter with no default - skip it
            return None

    # Find driver schema
    drivers_data = adapter_schema.get("properties", {}).get("drivers", {}).get("properties", {})
    driver_schema_ref = None

    for driver_name, driver_info in drivers_data.items():
        if driver_name == selected_driver and "$ref" in driver_info:
            driver_schema_ref = driver_info["$ref"]
            break

    if not driver_schema_ref:
        raise ValueError(f"Adapter {adapter_name} has no schema reference for driver {selected_driver}")

    # Load driver schema
    driver_schema_path = schema_dir / "adapters" / driver_schema_ref.lstrip("./")
    if not driver_schema_path.exists():
        raise FileNotFoundError(f"Driver schema file not found: {driver_schema_path}")

    with open(driver_schema_path) as f:
        driver_schema = json.load(f)

    # Extract common properties
    common_properties = adapter_schema.get("properties", {}).get("common", {}).get("properties", {})

    # Load driver config
    driver_config_dict = _load_and_populate_driver_config(
        driver_schema,
        common_properties,
        secret_provider,
    )

    return selected_driver, driver_config_dict


def get_config(service_name: str, schema_dir: str | None = None) -> Any:
    """Get strongly-typed configuration for a service.

    This is the main entry point for loading typed configuration.
    It returns a generated dataclass instance with full type safety.

    Example:
        >>> config = get_config("ingestion")
        >>> print(config.service_settings.batch_size)
        100
        >>> print(config.metrics.driver.gateway)
        'pushgateway:9091'

    Args:
        service_name: Name of the service (e.g., "ingestion")
        schema_dir: Optional schema directory path

    Returns:
        Typed ServiceConfig dataclass instance for the service

    Raises:
        ImportError: If generated module not found
        ValueError: If configuration is invalid
    """
    # Import the generated service module dynamically
    try:
        module = importlib.import_module(f".generated.services.{service_name}", package="copilot_config")
    except ImportError as e:
        raise ImportError(
            f"Generated configuration module not found for service '{service_name}'. "
            f"Run: python scripts/generate_typed_configs.py --service {service_name}"
        ) from e

    # Get the main ServiceConfig class
    service_config_class_name = _to_python_class_name(service_name, "ServiceConfig")
    service_config_class = getattr(module, service_config_class_name, None)

    if service_config_class is None:
        raise ValueError(f"ServiceConfig class not found in generated module: {service_config_class_name}")

    # Resolve schema directory
    schema_dir_path = Path(schema_dir) if schema_dir else _resolve_schema_directory()

    # Load service schema
    service_schema_path = schema_dir_path / "services" / f"{service_name}.json"
    if not service_schema_path.exists():
        raise FileNotFoundError(f"Service schema not found: {service_schema_path}")

    with open(service_schema_path) as f:
        service_schema = json.load(f)

    # Phase 1: Initialize secret provider if available
    secret_provider = None
    try:
        from copilot_secrets import create_secret_provider as create_secrets_provider

        from .secret_provider import SecretConfigProvider

        # Check if secret provider is configured
        secret_provider_env = os.environ.get("SECRET_PROVIDER_TYPE")
        if secret_provider_env:
            # Load secret provider adapter config
            adapters_schema = service_schema.get("adapters", {})
            if "secret_provider" in adapters_schema:
                secret_adapter_ref = adapters_schema["secret_provider"]["$ref"]
                secret_adapter_schema_path = schema_dir_path / secret_adapter_ref.lstrip("../")

                if secret_adapter_schema_path.exists():
                    with open(secret_adapter_schema_path) as f:
                        secret_adapter_schema = json.load(f)

                    secret_result = _load_adapter_config(
                        "secret_provider",
                        secret_adapter_schema,
                        schema_dir_path,
                        None,
                    )

                    if secret_result:
                        from .models import DriverConfig

                        secret_driver_name, secret_config_dict = secret_result
                        secret_driver_config = DriverConfig(
                            driver_name=secret_driver_name,
                            config=secret_config_dict,
                            allowed_keys=set(secret_config_dict.keys()),
                        )
                        secret_provider_instance = create_secrets_provider(
                            secret_driver_name,
                            secret_driver_config,
                        )
                        secret_provider = SecretConfigProvider(secret_provider=secret_provider_instance)
    except Exception:
        # Typed config is usable without secrets support; treat secrets as optional.
        pass

    # Phase 2: Load service settings
    service_settings_data = {}
    service_settings_schema = service_schema.get("service_settings", {})

    for setting_name, setting_spec in service_settings_schema.items():
        value = None

        if setting_spec.get("source") == "env":
            env_var = setting_spec.get("env_var")
            env_vars = env_var if isinstance(env_var, list) else [env_var]

            for candidate in env_vars:
                if not candidate:
                    continue
                candidate_value = os.environ.get(candidate)
                if candidate_value is not None:
                    value = candidate_value
                    break

            if value is not None:
                # Type conversion
                if setting_spec.get("type") in ("int", "integer"):
                    try:
                        value = int(value)
                    except ValueError:
                        # Ignore conversion errors and keep the original string value.
                        pass
                elif setting_spec.get("type") in ("bool", "boolean"):
                    value = value.lower() in ("true", "1", "yes")
            elif setting_spec.get("default") is not None:
                value = setting_spec.get("default")

        elif setting_spec.get("source") == "secret" and secret_provider:
            secret_name = setting_spec.get("secret_name")
            if secret_name:
                try:
                    value = secret_provider.get(secret_name)
                except Exception:
                    # Secrets are optional and may be unavailable at runtime.
                    pass

        else:
            if setting_spec.get("default") is not None:
                value = setting_spec.get("default")

        if value is not None:
            service_settings_data[setting_name] = value

    # Create ServiceSettings instance
    service_settings_class_name = _to_python_class_name(service_name, "ServiceSettings")
    service_settings_class = getattr(module, service_settings_class_name)
    service_settings = service_settings_class(**service_settings_data)

    # Phase 3: Load adapter configs
    adapters_dict = {}
    adapters_schema = service_schema.get("adapters", {})

    for adapter_name, adapter_ref in adapters_schema.items():
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue

        # Load adapter schema
        adapter_schema_path = schema_dir_path / adapter_ref["$ref"].lstrip("../")
        if not adapter_schema_path.exists():
            continue

        with open(adapter_schema_path) as f:
            adapter_schema = json.load(f)

        # Load adapter config
        adapter_result = _load_adapter_config(
            adapter_name,
            adapter_schema,
            schema_dir_path,
            secret_provider,
        )

        if not adapter_result:
            continue

        driver_name, driver_config_dict = adapter_result

        # Get the adapter and driver classes from the adapter module
        try:
            adapter_module = importlib.import_module(
                f".generated.adapters.{adapter_name}", package="copilot_config"
            )
        except ImportError:
            # Fallback: try to get from service module (backward compatibility)
            adapter_module = module

        adapter_class_name = _to_python_class_name(adapter_name, "AdapterConfig")
        adapter_class = getattr(adapter_module, adapter_class_name, None)

        if adapter_class is None:
            # Try service module if not found in adapter module
            adapter_class = getattr(module, adapter_class_name, None)

        if adapter_class is None:
            continue

        driver_class_name = f"DriverConfig_{_to_python_class_name(adapter_name)}_{_to_python_class_name(driver_name)}"
        driver_class = getattr(adapter_module, driver_class_name, None)

        if driver_class is None:
            # Try service module if not found in adapter module
            driver_class = getattr(module, driver_class_name, None)

        if driver_class is None:
            continue

        # Create driver config instance
        driver_config = driver_class(**driver_config_dict)

        # Get discriminant field name
        discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})
        discriminant_field = discriminant_info.get("field", "driver_name")

        # Create adapter config instance
        adapter_config = adapter_class(
            **{
                discriminant_field: driver_name,
                "driver": driver_config,
            }
        )

        adapters_dict[adapter_name] = adapter_config

    # Create and return ServiceConfig instance
    service_config = service_config_class(
        service_settings=service_settings,
        **adapters_dict,
    )

    return service_config


# Backward compatibility: provide load_service_config as alias
def load_typed_config(service_name: str, schema_dir: str | None = None) -> ServiceConfig:
    """Load typed configuration (backward compatibility wrapper).

    This is an alias for get_config() that provides backward compatibility
    with the existing load_service_config() API.

    Args:
        service_name: Name of the service
        schema_dir: Optional schema directory path

    Returns:
        Typed ServiceConfig instance
    """
    return get_config(service_name, schema_dir)
