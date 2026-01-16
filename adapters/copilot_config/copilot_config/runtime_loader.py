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
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

from .models import ServiceConfig
from .schema_validation import validate_config_against_schema_dict

T = TypeVar("T")


if TYPE_CHECKING:
    from .generated.services.auth import ServiceConfig_Auth
    from .generated.services.chunking import ServiceConfig_Chunking
    from .generated.services.embedding import ServiceConfig_Embedding
    from .generated.services.ingestion import ServiceConfig_Ingestion
    from .generated.services.orchestrator import ServiceConfig_Orchestrator
    from .generated.services.parsing import ServiceConfig_Parsing
    from .generated.services.reporting import ServiceConfig_Reporting
    from .generated.services.summarization import ServiceConfig_Summarization


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
    # Support discriminated oneOf schemas by selecting a concrete variant first.
    if "oneOf" in driver_schema:
        discriminant_info = driver_schema.get("discriminant", {})
        discriminant_field = discriminant_info.get("field")
        discriminant_env_var = discriminant_info.get("env_var")

        if not discriminant_field or not discriminant_env_var:
            raise ValueError(
                "Driver schema uses oneOf but is missing discriminant.field or discriminant.env_var"
            )

        selected_variant = os.environ.get(discriminant_env_var)
        if not selected_variant:
            is_required = discriminant_info.get("required", False)
            default_variant = discriminant_info.get("default")
            if is_required and not default_variant:
                raise ValueError(
                    f"Driver schema requires discriminant configuration: set environment variable {discriminant_env_var}"
                )
            selected_variant = default_variant

        one_of = driver_schema.get("oneOf")
        if not isinstance(one_of, list):
            raise ValueError("Driver schema oneOf must be a list")

        selected_schema: dict[str, Any] | None = None
        for candidate in one_of:
            if not isinstance(candidate, dict):
                continue
            candidate_props = candidate.get("properties", {})
            if not isinstance(candidate_props, dict):
                continue
            disc_prop = candidate_props.get(discriminant_field, {})
            if isinstance(disc_prop, dict) and disc_prop.get("const") == selected_variant:
                selected_schema = candidate
                break

        if selected_schema is None:
            raise ValueError(
                f"Driver schema discriminant '{discriminant_field}' has invalid value '{selected_variant}'"
            )

        return _load_and_populate_driver_config(selected_schema, common_properties, secret_provider)

    # Merge driver properties with common properties
    properties = driver_schema.get("properties", {})
    if common_properties:
        for key, value in common_properties.items():
            if key not in properties:
                properties[key] = value

    required_list = driver_schema.get("required", [])
    required_fields = set(required_list) if isinstance(required_list, list) else set()

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

    # Enforce schema-level required fields.
    missing_required = [name for name in required_fields if name not in config_dict]
    if missing_required:
        details: list[str] = []
        for field_name in sorted(missing_required):
            spec = properties.get(field_name, {})
            if not isinstance(spec, dict):
                details.append(field_name)
                continue

            if spec.get("source") == "env":
                env_var = spec.get("env_var")
                if isinstance(env_var, list):
                    env_var_str = " or ".join([str(v) for v in env_var if v])
                else:
                    env_var_str = str(env_var) if env_var else "<unknown>"
                details.append(f"{field_name} (set {env_var_str})")
            elif spec.get("source") == "secret":
                secret_name = spec.get("secret_name")
                details.append(f"{field_name} (secret {secret_name})")
            else:
                details.append(field_name)

        raise ValueError(
            "Missing required driver configuration: " + ", ".join(details)
        )

    validate_config_against_schema_dict(schema=driver_schema, config=config_dict)
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


@overload
def get_config(service_name: Literal["auth"], schema_dir: str | None = None) -> "ServiceConfig_Auth": ...


@overload
def get_config(service_name: Literal["chunking"], schema_dir: str | None = None) -> "ServiceConfig_Chunking": ...


@overload
def get_config(service_name: Literal["embedding"], schema_dir: str | None = None) -> "ServiceConfig_Embedding": ...


@overload
def get_config(service_name: Literal["ingestion"], schema_dir: str | None = None) -> "ServiceConfig_Ingestion": ...


@overload
def get_config(service_name: Literal["orchestrator"], schema_dir: str | None = None) -> "ServiceConfig_Orchestrator": ...


@overload
def get_config(service_name: Literal["parsing"], schema_dir: str | None = None) -> "ServiceConfig_Parsing": ...


@overload
def get_config(service_name: Literal["reporting"], schema_dir: str | None = None) -> "ServiceConfig_Reporting": ...


@overload
def get_config(service_name: Literal["summarization"], schema_dir: str | None = None) -> "ServiceConfig_Summarization": ...


@overload
def get_config(service_name: str, schema_dir: str | None = None) -> Any: ...


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
    secret_provider_env = os.environ.get("SECRET_PROVIDER_TYPE")

    class _LocalFileSecretProvider:
        def __init__(self, base_path: str):
            self._base_path = Path(base_path)

        def _path_for(self, key: str) -> Path:
            return self._base_path / key

        def get_secret(self, key: str) -> str:
            return self._path_for(key).read_text(encoding="utf-8")

        def get_secret_bytes(self, key: str) -> bytes:
            return self._path_for(key).read_bytes()

        def secret_exists(self, key: str) -> bool:
            return self._path_for(key).exists()

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
                    secret_driver_name, secret_config_dict = secret_result
                    try:
                        from copilot_secrets import create_secret_provider as create_secrets_provider

                        from copilot_config.generated.adapters.secret_provider import (
                            AdapterConfig_SecretProvider,
                            DriverConfig_SecretProvider_AzureKeyVault,
                            DriverConfig_SecretProvider_Local,
                        )

                        from .secret_provider import SecretConfigProvider

                        if secret_driver_name == "local":
                            driver_config = DriverConfig_SecretProvider_Local(**secret_config_dict)
                        elif secret_driver_name == "azure_key_vault":
                            driver_config = DriverConfig_SecretProvider_AzureKeyVault(**secret_config_dict)
                        else:
                            raise ValueError(
                                f"Unknown secret_provider driver: {secret_driver_name}. "
                                "Supported drivers: local, azure_key_vault"
                            )

                        secret_provider_instance = create_secrets_provider(
                            AdapterConfig_SecretProvider(
                                secret_provider_type=secret_driver_name,
                                driver=driver_config,
                            )
                        )
                        secret_provider = SecretConfigProvider(secret_provider=secret_provider_instance)
                    except ImportError:
                        # For unit tests and minimal deployments, allow local-file secrets without
                        # requiring the copilot_secrets package.
                        if secret_driver_name == "local":
                            from .secret_provider import SecretConfigProvider

                            base_path = str(secret_config_dict.get("base_path") or "/run/secrets")
                            secret_provider = SecretConfigProvider(
                                secret_provider=_LocalFileSecretProvider(base_path=base_path)
                            )
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

    # Optional: apply repository schema extensions (x-*) to service settings.
    # Service schemas use a custom format (service_settings dict rather than JSON Schema properties),
    # so we construct a minimal schema dict that our validator understands.
    service_settings_validation_keys = (
        "x-conditional_required",
        "x-required_one_of",
        "x-dependent_required",
    )
    service_settings_validation_extensions: dict[str, Any] = {}
    for key in service_settings_validation_keys:
        value = service_schema.get(key)
        if isinstance(value, list) and value:
            service_settings_validation_extensions[key] = value

    if service_settings_validation_extensions:
        service_settings_validation_schema: dict[str, Any] = {
            "type": "object",
            "properties": service_settings_schema,
            **service_settings_validation_extensions,
        }
        validate_config_against_schema_dict(schema=service_settings_validation_schema, config=service_settings)

    # Phase 3: Load adapter configs
    adapters_dict = {}
    adapters_schema = service_schema.get("adapters", {})

    for adapter_name, adapter_ref in adapters_schema.items():
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue

        adapter_required = adapter_ref.get("required") is True

        # Load adapter schema
        adapter_schema_path = schema_dir_path / adapter_ref["$ref"].lstrip("../")
        if not adapter_schema_path.exists():
            continue

        with open(adapter_schema_path) as f:
            adapter_schema = json.load(f)

        # Composite (non-discriminant) adapters: support multiple child configs.
        # Currently used for oidc_providers, which can configure multiple providers at once.
        discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})
        discriminant_env_var = discriminant_info.get("env_var") if isinstance(discriminant_info, dict) else None

        if not discriminant_env_var:
            # Attempt composite adapter loading.
            try:
                adapter_module = importlib.import_module(
                    f".generated.adapters.{adapter_name}", package="copilot_config"
                )
            except ImportError:
                adapter_module = module

            adapter_class_name = _to_python_class_name(adapter_name, "AdapterConfig")
            adapter_class = getattr(adapter_module, adapter_class_name, None) or getattr(module, adapter_class_name, None)

            composite_class_name = _to_python_class_name(adapter_name, "CompositeConfig")
            composite_class = getattr(adapter_module, composite_class_name, None) or getattr(module, composite_class_name, None)

            composite_root = adapter_schema.get("properties", {}).get(adapter_name)
            composite_properties = (composite_root or {}).get("properties", {})

            if adapter_class and composite_class and isinstance(composite_properties, dict) and composite_properties:
                composite_kwargs: dict[str, Any] = {}

                for child_name, child_info in composite_properties.items():
                    child_ref = child_info.get("$ref") if isinstance(child_info, dict) else None
                    if not child_ref:
                        continue

                    child_schema_path = (adapter_schema_path.parent / child_ref.lstrip("./")).resolve()
                    if not child_schema_path.exists():
                        continue

                    with open(child_schema_path) as child_file:
                        child_schema = json.load(child_file)

                    child_config_dict = _load_and_populate_driver_config(
                        child_schema,
                        common_properties=None,
                        secret_provider=secret_provider,
                    )

                    # Only include provider entries that are actually configured.
                    # For known OIDC providers, require both client_id and client_secret.
                    if adapter_name == "oidc_providers":
                        client_id_key = f"{child_name}_client_id"
                        client_secret_key = f"{child_name}_client_secret"
                        if not child_config_dict.get(client_id_key) or not child_config_dict.get(client_secret_key):
                            continue

                    driver_class_name = (
                        f"DriverConfig_{_to_python_class_name(adapter_name)}_{_to_python_class_name(child_name)}"
                    )
                    driver_class = getattr(adapter_module, driver_class_name, None) or getattr(module, driver_class_name, None)
                    if driver_class is None:
                        continue

                    composite_kwargs[child_name] = driver_class(**child_config_dict)

                if composite_kwargs:
                    composite_config = composite_class(**composite_kwargs)
                    adapters_dict[adapter_name] = adapter_class(**{adapter_name: composite_config})
                elif adapter_required and adapter_class is not None:
                    # Service schema requires this adapter block, but no child configs are present.
                    # Emit an empty adapter config rather than omitting the field entirely.
                    adapters_dict[adapter_name] = adapter_class()
            continue

        # Load adapter config
        adapter_result = _load_adapter_config(
            adapter_name,
            adapter_schema,
            schema_dir_path,
            secret_provider,
        )

        if not adapter_result:
            if adapter_required:
                discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})
                discriminant_env_var = (
                    discriminant_info.get("env_var") if isinstance(discriminant_info, dict) else None
                )
                if discriminant_env_var:
                    raise ValueError(
                        f"Adapter {adapter_name} is required: set environment variable {discriminant_env_var}"
                    )
                raise ValueError(f"Adapter {adapter_name} is required but not configured")
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

        # Fail fast on misconfiguration using schema-driven validation.
        # This keeps adapters simple by centralizing validation in copilot_config.
        from .schema_validation import validate_driver_config_against_schema

        validate_driver_config_against_schema(
            adapter=adapter_name,
            driver=driver_name,
            config=driver_config,
            schema_dir=str(schema_dir_path),
        )

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
