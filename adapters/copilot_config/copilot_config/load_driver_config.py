# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Utility function to load DriverConfig for testing scenarios."""

import json
import os
from typing import Any

from .models import DriverConfig
from .schema_loader import _resolve_schema_directory


def _get_service_schema(service: str, schema_dir: str | None = None) -> tuple[dict[str, Any], str]:
    """Load service schema and return (schema_dict, schema_path)."""
    schema_dir_path = _resolve_schema_directory(schema_dir)
    service_schema_path = os.path.join(schema_dir_path, "services", f"{service}.json")
    
    if not os.path.exists(service_schema_path):
        raise FileNotFoundError(f"Service schema not found: {service_schema_path}")
    
    with open(service_schema_path) as f:
        service_schema = json.load(f)
    
    return service_schema, service_schema_path


def _get_adapter_schema(
    service: str | None,
    adapter: str,
    schema_dir: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Load adapter schema by following reference from service schema.
    
    Returns (adapter_schema_dict, adapter_schema_path).
    If service is None, loads adapter schema directly from adapters/ directory.
    Otherwise validates that the service declares this adapter.
    """
    schema_dir_path = _resolve_schema_directory(schema_dir)
    
    # If no service specified, load adapter schema directly
    if service is None:
        adapter_schema_path = os.path.join(schema_dir_path, "adapters", f"{adapter}.json")
        if not os.path.exists(adapter_schema_path):
            raise FileNotFoundError(f"Adapter schema not found: {adapter_schema_path}")
        
        with open(adapter_schema_path) as f:
            adapter_schema = json.load(f)
        
        return adapter_schema, adapter_schema_path
    
    # Otherwise validate via service schema
    service_schema, _ = _get_service_schema(service, schema_dir)

    # Service schemas in this repo are not pure JSON Schema; many declare adapters
    # as a top-level mapping: {"adapters": {"message_bus": {"$ref": ...}, ...}}.
    # Some schemas may also use a JSON-Schema-like structure under properties.
    service_adapters: dict[str, Any] = (
        service_schema.get("properties", {}).get("adapters", {}).get("properties", {})
    )
    if not service_adapters and isinstance(service_schema.get("adapters"), dict):
        service_adapters = service_schema["adapters"]

    if adapter not in service_adapters:
        raise ValueError(
            f"Service '{service}' does not declare adapter '{adapter}'. "
            f"Available adapters: {sorted(service_adapters.keys())}"
        )
    
    adapter_ref = service_adapters[adapter].get("$ref")
    if not adapter_ref:
        raise ValueError(f"Adapter '{adapter}' has no schema reference in service schema")
    
    adapter_schema_path = os.path.join(schema_dir_path, adapter_ref.lstrip("../"))
    if not os.path.exists(adapter_schema_path):
        raise FileNotFoundError(f"Adapter schema not found: {adapter_schema_path}")
    
    with open(adapter_schema_path) as f:
        adapter_schema = json.load(f)
    
    return adapter_schema, adapter_schema_path


def _get_driver_schema(
    service: str | None,
    adapter: str,
    driver: str,
    schema_dir: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Load driver schema by following references from service -> adapter -> driver.
    
    Returns (driver_schema_dict, driver_schema_path).
    If service is None, skips service validation.
    Validates that the adapter supports this driver.
    """
    adapter_schema, adapter_schema_path = _get_adapter_schema(service, adapter, schema_dir)
    
    drivers_section = adapter_schema.get("properties", {}).get("drivers", {}).get("properties", {})
    if driver not in drivers_section:
        raise ValueError(
            f"Adapter '{adapter}' does not support driver '{driver}'. "
            f"Supported drivers: {sorted(drivers_section.keys())}"
        )
    
    driver_ref = drivers_section[driver].get("$ref")
    if not driver_ref:
        raise ValueError(f"Driver '{driver}' has no schema reference in adapter schema")
    
    driver_schema_path = os.path.join(
        os.path.dirname(adapter_schema_path),
        driver_ref.lstrip("./"),
    )
    if not os.path.exists(driver_schema_path):
        raise FileNotFoundError(f"Driver schema not found: {driver_schema_path}")
    
    with open(driver_schema_path) as f:
        driver_schema = json.load(f)
    
    return driver_schema, driver_schema_path


def load_driver_config(
    service: str | None,
    adapter: str,
    driver: str,
    fields: dict[str, Any] | None = None,
    schema_dir: str | None = None,
) -> DriverConfig:
    """Load a DriverConfig object for testing with validation against schemas.

    This function is designed for test scenarios where a complete ServiceConfig is not
    available. It validates the driver configuration against the schema hierarchy:
    1. If service is provided: Confirms the service schema includes the specified adapter
    2. Confirms the adapter schema supports the specified driver
    3. Loads the driver schema to validate field names
    4. Creates a DriverConfig with schema-validated allowed_keys

    Args:
        service: Optional service name (e.g., "chunking", "embedding"). 
                If None, skips service schema validation and loads adapter directly.
        adapter: Adapter type (e.g., "message_bus", "document_store", "logger")
        driver: Driver name (e.g., "rabbitmq", "mongodb", "stdout")
        fields: Dictionary of field values to populate in the config.
               Each field is validated against the driver schema.
        schema_dir: Directory containing schema files. If None, will search relative to this module.

    Returns:
        DriverConfig object with:
        - driver_name set to the specified driver
        - config populated with validated field values
        - allowed_keys set from the driver schema

    Raises:
        FileNotFoundError: If required schema files are not found
        ValueError: If service doesn't declare the adapter (when service is provided),
                   adapter doesn't support the driver, or a field is not defined in the driver schema
        AttributeError: If a provided field name is not in the driver schema
    """
    if fields is None:
        fields = {}

    # Load driver schema (also validates service/adapter/driver exist)
    driver_schema, _ = _get_driver_schema(service, adapter, driver, schema_dir)
    
    # Also load adapter schema to get common properties
    adapter_schema, _ = _get_adapter_schema(service, adapter, schema_dir)

    # Extract allowed keys from driver schema
    schema_properties: dict[str, Any] = driver_schema.get("properties") or {}
    allowed_keys = set(schema_properties.keys())
    
    # Merge in common properties from adapter schema if they exist
    common_properties: dict[str, Any] = adapter_schema.get("properties", {}).get("common", {}).get("properties", {})
    schema_properties.update(common_properties)
    allowed_keys.update(common_properties.keys())

    # Validate provided fields against schema
    config_dict: dict[str, Any] = {}
    for field_name, field_value in fields.items():
        if field_name not in allowed_keys:
            raise AttributeError(
                f"Field '{field_name}' is not defined in {adapter}/{driver} schema. "
                f"Allowed fields: {sorted(allowed_keys)}"
            )
        config_dict[field_name] = field_value

    # Apply schema defaults for fields not explicitly provided
    for field_name, field_spec in schema_properties.items():
        if field_name in config_dict:
            continue

        if isinstance(field_spec, dict) and "default" in field_spec:
            config_dict[field_name] = field_spec.get("default")
            continue

        if isinstance(field_spec, dict) and field_spec.get("required") is True:
            raise ValueError(
                f"Missing required field '{field_name}' for {adapter}/{driver} driver config"
            )

    # Create and return DriverConfig
    return DriverConfig(
        driver_name=driver,
        config=config_dict,
        allowed_keys=allowed_keys,
    )

