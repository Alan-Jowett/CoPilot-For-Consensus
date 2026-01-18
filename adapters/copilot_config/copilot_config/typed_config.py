# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Service configuration loader with hierarchical adapter structure."""

import json
import os
from typing import Any

from .load_driver_config import load_driver_config  # noqa: F401
from .models import AdapterConfig, DriverConfig, ServiceConfig
from .schema_validation import validate_config_against_schema_dict


def load_service_config(service_name: str, schema_dir: str | None = None, **kwargs) -> ServiceConfig:
    """Load and validate service configuration with hierarchical adapters.

    This is the RECOMMENDED way to load configuration in services going forward.
    Returns a ServiceConfig object with:
    - service_settings: Dictionary of service-specific configuration
    - adapters: Array of configured adapters with driver names and driver configs
    - schema_version and min_service_version metadata

    Services should then iterate over adapters and call adapter factory methods:
        config = load_service_config("summarization")
        llm_adapter = config.get_adapter("llm_backend")
        llm = create_llm_backend(llm_adapter.driver_name, llm_adapter.driver_config)

    Args:
        service_name: Name of the service
        schema_dir: Directory containing schema files
        **kwargs: Additional arguments to pass to internal loader

    Returns:
        ServiceConfig instance with hierarchical structure

    Raises:
        ConfigSchemaError: If schema is missing or invalid
        ConfigValidationError: If configuration validation fails
    """
    from .schema_loader import ConfigSchema, _load_config, _resolve_schema_directory

    # Try to import secrets support (optional)
    try:
        import copilot_secrets  # noqa: F401

        secrets_available = True
    except ImportError:
        secrets_available = False

    # Resolve schema directory
    schema_dir_path = _resolve_schema_directory(schema_dir)

    # Load the main service schema
    service_schema_path = os.path.join(schema_dir_path, "services", f"{service_name}.json")
    service_schema = ConfigSchema.from_json_file(service_schema_path)

    def _extract_config_from_driver_schema(
        driver_schema_data: dict[str, Any],
        secret_provider: Any | None,
    ) -> dict[str, Any]:
        """Extract configuration values from a driver schema."""
        if "oneOf" in driver_schema_data:
            discriminant_info = driver_schema_data.get("discriminant", {})
            discriminant_field = discriminant_info.get("field")
            discriminant_env_var = discriminant_info.get("env_var")

            if not discriminant_field or not discriminant_env_var:
                raise ValueError("Driver schema uses oneOf but is missing discriminant.field or discriminant.env_var")

            selected_variant = os.environ.get(discriminant_env_var)
            if not selected_variant:
                is_required = discriminant_info.get("required", False)
                default_variant = discriminant_info.get("default")
                if is_required and not default_variant:
                    raise ValueError(
                        "Driver schema requires discriminant configuration: set environment variable "
                        f"{discriminant_env_var}"
                    )
                selected_variant = default_variant

            one_of = driver_schema_data.get("oneOf")
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

            return _extract_config_from_driver_schema(selected_schema, secret_provider)

        driver_config_dict: dict[str, Any] = {}
        driver_properties = driver_schema_data.get("properties", {})
        required_list = driver_schema_data.get("required", [])
        required_fields = set(required_list) if isinstance(required_list, list) else set()

        for prop_name, prop_spec in driver_properties.items():
            if prop_spec.get("source") == "env":
                env_var = prop_spec.get("env_var")
                env_vars = env_var if isinstance(env_var, list) else [env_var]
                value = None
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
                            driver_config_dict[prop_name] = int(value)
                        except ValueError:
                            driver_config_dict[prop_name] = value
                    elif prop_spec.get("type") in ("bool", "boolean"):
                        driver_config_dict[prop_name] = value.lower() in ("true", "1", "yes")
                    else:
                        driver_config_dict[prop_name] = value
                elif prop_spec.get("default") is not None:
                    driver_config_dict[prop_name] = prop_spec.get("default")
            elif prop_spec.get("source") == "secret" and secret_provider:
                secret_name = prop_spec.get("secret_name")
                secret_names = secret_name if isinstance(secret_name, list) else [secret_name]
                for candidate in secret_names:
                    if not candidate:
                        continue
                    try:
                        value = secret_provider.get(candidate)
                        if value is not None:
                            driver_config_dict[prop_name] = value
                            break
                    except Exception:
                        import logging

                        logger = logging.getLogger("copilot_config")
                        logger.debug("Failed to load secret")
                        continue
            else:
                # Field has no source (not env or secret) - apply default if present
                if prop_spec.get("default") is not None:
                    driver_config_dict[prop_name] = prop_spec.get("default")

        missing_required = [name for name in required_fields if name not in driver_config_dict]
        if missing_required:
            details: list[str] = []
            for field_name in sorted(missing_required):
                spec = driver_properties.get(field_name, {})
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

            raise ValueError("Missing required driver configuration: " + ", ".join(details))

        validate_config_against_schema_dict(schema=driver_schema_data, config=driver_config_dict)
        return driver_config_dict

    def _append_adapter_configs_from_schema(
        *,
        adapter_configs: list[AdapterConfig],
        adapter_name: str,
        adapter_schema_path: str,
        adapter_schema_data: dict[str, Any],
        secret_provider: Any | None,
    ) -> None:
        """Append one or more AdapterConfig entries for a single adapter schema."""
        discriminant_info = adapter_schema_data.get("properties", {}).get("discriminant", {})
        discriminant_env_var = discriminant_info.get("env_var")

        if not discriminant_env_var:
            # Special case: composite adapters that are not discriminant-based.
            # Currently used for oidc_providers which supports multiple concurrent providers.
            composite_root = adapter_schema_data.get("properties", {}).get(adapter_name)
            composite_properties = (composite_root or {}).get("properties", {})

            if not composite_properties:
                raise ValueError(
                    f"Adapter {adapter_name} has no discriminant and no composite properties defined in schema"
                )

            composite_config: dict[str, Any] = {}
            for child_name, child_info in composite_properties.items():
                child_ref = child_info.get("$ref") if isinstance(child_info, dict) else None
                if not child_ref:
                    continue

                child_schema_path = os.path.join(
                    os.path.dirname(adapter_schema_path),
                    child_ref.lstrip("./"),
                )
                if not os.path.exists(child_schema_path):
                    continue

                with open(child_schema_path) as f:
                    child_schema_data = json.load(f)

                child_config = _extract_config_from_driver_schema(child_schema_data, secret_provider)

                # Only include provider entries that are actually configured.
                # For known OIDC providers, require both client_id and client_secret.
                if adapter_name == "oidc_providers":
                    client_id_key = f"{child_name}_client_id"
                    client_secret_key = f"{child_name}_client_secret"
                    if not child_config.get(client_id_key) or not child_config.get(client_secret_key):
                        continue

                composite_config[child_name] = child_config

            if composite_config:
                adapter_configs.append(
                    AdapterConfig(
                        adapter_type=adapter_name,
                        driver_name="multi",
                        driver_config=DriverConfig(
                            driver_name="multi",
                            config=composite_config,
                            allowed_keys=set(composite_config.keys()),
                        ),
                    )
                )
            return

        selected_driver = os.environ.get(discriminant_env_var)
        if not selected_driver:
            discriminant_info = adapter_schema_data.get("properties", {}).get("discriminant", {})
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
                return

        drivers_data = adapter_schema_data.get("properties", {}).get("drivers", {}).get("properties", {})
        driver_schema_ref = None

        for driver_name, driver_info in drivers_data.items():
            if driver_name == selected_driver and "$ref" in driver_info:
                driver_schema_ref = driver_info["$ref"]
                break

        if not driver_schema_ref:
            raise ValueError(f"Adapter {adapter_name} has no schema reference for driver {selected_driver}")

        driver_schema_path = os.path.join(
            os.path.dirname(adapter_schema_path),
            driver_schema_ref.lstrip("./"),
        )

        if not os.path.exists(driver_schema_path):
            raise FileNotFoundError(f"Driver schema file not found: {driver_schema_path}")

        with open(driver_schema_path) as f:
            driver_schema_data = json.load(f)

        # Extract config from driver schema
        driver_config_dict = _extract_config_from_driver_schema(driver_schema_data, secret_provider)

        # Also extract config from common properties in the adapter schema
        common_properties = adapter_schema_data.get("properties", {}).get("common", {}).get("properties", {})
        if common_properties:
            # Create a temporary schema with just common properties to reuse extraction logic
            common_schema = {"properties": common_properties}
            common_config = _extract_config_from_driver_schema(common_schema, secret_provider)
            # Common properties should not override driver-specific ones
            for key, value in common_config.items():
                if key not in driver_config_dict:
                    driver_config_dict[key] = value

        # Extract allowed keys from driver schema
        allowed_keys = set((driver_schema_data.get("properties") or {}).keys())

        if not allowed_keys and "oneOf" in driver_schema_data:
            # For discriminated oneOf driver schemas, select the active variant and use its properties.
            discriminant_info = driver_schema_data.get("discriminant", {})
            discriminant_field = discriminant_info.get("field")
            discriminant_env_var = discriminant_info.get("env_var")
            selected_variant = os.environ.get(discriminant_env_var) if discriminant_env_var else None
            if not selected_variant:
                selected_variant = discriminant_info.get("default")

            for candidate in driver_schema_data.get("oneOf", []):
                if not isinstance(candidate, dict):
                    continue
                candidate_props = candidate.get("properties", {})
                if not isinstance(candidate_props, dict):
                    continue
                disc_prop = candidate_props.get(discriminant_field, {}) if discriminant_field else {}
                if isinstance(disc_prop, dict) and disc_prop.get("const") == selected_variant:
                    allowed_keys = set(candidate_props.keys())
                    break

        # Merge in common properties from adapter schema if they exist
        allowed_keys.update(common_properties.keys())

        driver_config = DriverConfig(
            driver_name=selected_driver,
            config=driver_config_dict,
            allowed_keys=allowed_keys,
        )
        adapter_configs.append(
            AdapterConfig(
                adapter_type=adapter_name,
                driver_name=selected_driver,
                driver_config=driver_config,
            )
        )

    def _build_adapter_configs(*, secret_provider: Any | None) -> list[AdapterConfig]:
        adapter_configs: list[AdapterConfig] = []

        for adapter_name, adapter_schema_ref in service_schema.adapters_schema.items():
            adapter_schema_path = os.path.join(schema_dir_path, adapter_schema_ref.lstrip("../"))

            if not os.path.exists(adapter_schema_path):
                raise FileNotFoundError(f"Adapter schema file not found: {adapter_schema_path}")

            with open(adapter_schema_path) as f:
                adapter_schema_data = json.load(f)

            _append_adapter_configs_from_schema(
                adapter_configs=adapter_configs,
                adapter_name=adapter_name,
                adapter_schema_path=adapter_schema_path,
                adapter_schema_data=adapter_schema_data,
                secret_provider=secret_provider,
            )

        # Back-compat: allow secret provider configuration via env even if the
        # service schema has not yet been updated to declare a secret_provider adapter.
        if "secret_provider" not in service_schema.adapters_schema and os.environ.get("SECRET_PROVIDER_TYPE"):
            secret_adapter_schema_path = os.path.join(schema_dir_path, "adapters", "secret_provider.json")
            if os.path.exists(secret_adapter_schema_path):
                with open(secret_adapter_schema_path) as f:
                    secret_adapter_schema_data = json.load(f)

                _append_adapter_configs_from_schema(
                    adapter_configs=adapter_configs,
                    adapter_name="secret_provider",
                    adapter_schema_path=secret_adapter_schema_path,
                    adapter_schema_data=secret_adapter_schema_data,
                    secret_provider=secret_provider,
                )

        return adapter_configs

    # Phase 1: load non-secret adapter configs (including secret_provider)
    adapter_configs_phase1 = _build_adapter_configs(secret_provider=None)

    # Phase 2: instantiate the secrets adapter via the standard factory API
    secret_provider = None
    if secrets_available:
        try:
            from copilot_secrets import create_secret_provider as create_secrets_provider

            from copilot_config.generated.adapters.secret_provider import (
                AdapterConfig_SecretProvider,
                DriverConfig_SecretProvider_AzureKeyVault,
                DriverConfig_SecretProvider_Local,
            )

            from .secret_provider import SecretConfigProvider

            secret_adapter = next(
                (a for a in adapter_configs_phase1 if a.adapter_type == "secret_provider"),
                None,
            )

            if secret_adapter is not None:
                secret_driver_name = secret_adapter.driver_name
                secret_config_dict = getattr(secret_adapter.driver_config, "config", {})

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
        except Exception as e:
            import logging

            logger = logging.getLogger("copilot_config")
            logger.warning(f"Failed to initialize secret_provider: {e}. Secrets will not be available.", exc_info=True)
            secret_provider = None

    # Phase 3: load full service settings and rebuild adapter configs with secrets resolved
    config_dict = _load_config(
        service_name,
        schema_dir=schema_dir,
        schema=service_schema,
        secret_provider=secret_provider,
        **kwargs,
    )

    adapter_configs = _build_adapter_configs(secret_provider=secret_provider)

    # Return hierarchical ServiceConfig
    return ServiceConfig(
        service_name=service_name,
        service_settings=config_dict,
        adapters=adapter_configs,
        schema_version=service_schema.schema_version,
        min_service_version=service_schema.min_service_version,
        allowed_service_settings=set(service_schema.service_settings.keys()),
    )
