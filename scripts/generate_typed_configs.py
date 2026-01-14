#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generate typed dataclass hierarchies from JSON schemas.

This script reads service configuration schemas and generates Python dataclasses
that represent the complete type hierarchy including service settings, adapters,
and driver-specific configurations.

Usage:
    python scripts/generate_typed_configs.py --all
    python scripts/generate_typed_configs.py --service ingestion
    python scripts/generate_typed_configs.py --service ingestion --output custom_dir
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def resolve_schema_directory() -> Path:
    """Resolve the schema directory path."""
    # Try from script location (works from any CWD)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    schema_dir = repo_root / "docs" / "schemas" / "configs"

    if schema_dir.exists():
        return schema_dir

    # Fallback to environment variable
    if "SCHEMA_DIR" in os.environ:
        return Path(os.environ["SCHEMA_DIR"])

    raise FileNotFoundError(f"Schema directory not found at {schema_dir}")


def to_python_class_name(name: str, prefix: str = "") -> str:
    """Convert a schema name to a Python class name.

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


def to_python_field_name(name: str) -> str:
    """Convert a schema field name to a Python field name.

    Args:
        name: Field name from schema

    Returns:
        snake_case field name
    """
    return name


def schema_type_to_python_type(schema_type: str, default_value: Any = None) -> str:
    """Convert schema type to Python type annotation.

    Args:
        schema_type: Schema type (e.g., "string", "int", "bool")
        default_value: Default value to help infer optional types

    Returns:
        Python type annotation string
    """
    type_mapping = {
        "string": "str",
        "int": "int",
        "integer": "int",
        "bool": "bool",
        "boolean": "bool",
        "float": "float",
        "number": "float",
        "object": "dict[str, Any]",
        "array": "list[Any]",
    }

    py_type = type_mapping.get(schema_type, "Any")

    # If there's a default or not marked as required, make it optional
    if default_value is not None:
        return py_type

    return py_type


def generate_driver_dataclass(
    adapter_name: str,
    driver_name: str,
    driver_schema: dict[str, Any],
    common_properties: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Generate a dataclass for a specific driver.

    Args:
        adapter_name: Name of the adapter (e.g., "metrics")
        driver_name: Name of the driver (e.g., "prometheus")
        driver_schema: The driver schema dictionary
        common_properties: Common properties from adapter schema

    Returns:
        Tuple of (class_name, class_code)
    """
    class_name = f"DriverConfig_{to_python_class_name(adapter_name)}_{to_python_class_name(driver_name)}"

    # Merge driver properties with common properties
    properties = driver_schema.get("properties", {})
    if common_properties:
        # Common properties should not override driver-specific ones
        for key, value in common_properties.items():
            if key not in properties:
                properties[key] = value

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Configuration for {adapter_name} adapter using {driver_name} driver."""',
    ]

    if not properties:
        lines.append("    pass")
    else:
        # Sort properties: required fields without defaults first, then all others
        # Within each group, sort alphabetically for stable output
        sorted_props = sorted(properties.items())

        # Separate into two groups
        required_no_default = []
        with_default_or_optional = []

        for prop_name, prop_spec in sorted_props:
            default = prop_spec.get("default")
            required = prop_spec.get("required", False)

            if required and default is None:
                required_no_default.append((prop_name, prop_spec))
            else:
                with_default_or_optional.append((prop_name, prop_spec))

        # Process all fields in correct order
        all_fields = required_no_default + with_default_or_optional

        for prop_name, prop_spec in all_fields:
            prop_type = prop_spec.get("type", "string")
            default = prop_spec.get("default")
            required = prop_spec.get("required", False)
            description = prop_spec.get("description", "")

            py_type = schema_type_to_python_type(prop_type, default)

            # Format the field
            field_name = to_python_field_name(prop_name)

            if required and default is None:
                # Required field with no default
                type_annotation = py_type
            else:
                # Optional field or has default
                type_annotation = f"{py_type} | None"

            # Generate field with default
            if default is not None:
                # Handle different default types
                if isinstance(default, str):
                    default_repr = repr(default)
                elif isinstance(default, bool):
                    default_repr = str(default)
                elif isinstance(default, (int, float)):
                    default_repr = str(default)
                else:
                    default_repr = repr(default)
                lines.append(f"    {field_name}: {type_annotation} = {default_repr}")
            elif not required:
                lines.append(f"    {field_name}: {type_annotation} = None")
            else:
                lines.append(f"    {field_name}: {type_annotation}")

            # Add docstring comment if description exists
            if description:
                # Escape any quotes in description
                desc_safe = description.replace('"', '\\"')
                lines.append(f'    """{desc_safe}"""' if len(lines) == 4 else f"    # {description}")

    return class_name, "\n".join(lines)


def generate_adapter_dataclass(
    adapter_name: str,
    adapter_schema: dict[str, Any],
    driver_classes: dict[str, str],
) -> tuple[str, str, list[str]]:
    """Generate a dataclass for an adapter with driver discrimination.

    Args:
        adapter_name: Name of the adapter
        adapter_schema: The adapter schema dictionary
        driver_classes: Dict mapping driver names to their class names

    Returns:
        Tuple of (class_name, class_code, required_imports)
    """
    class_name = f"AdapterConfig_{to_python_class_name(adapter_name)}"

    discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})
    discriminant_field = discriminant_info.get("field", "driver_name")
    discriminant_enum = discriminant_info.get("enum", [])

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Configuration for {adapter_name} adapter."""',
    ]

    # If discriminant exists, create a Literal type for it
    imports = ["from typing import Literal"]

    if discriminant_enum:
        literal_type = "Literal[" + ", ".join(f'"{v}"' for v in sorted(discriminant_enum)) + "]"
        lines.append(f"    {discriminant_field}: {literal_type}")

        # Add driver field as a Union of all possible driver configs
        driver_union_types = [driver_classes.get(driver, "Any") for driver in sorted(discriminant_enum)]
        driver_union = " | ".join(driver_union_types)

        # Check if the union line would be too long (> 120 chars)
        union_line = f"    driver: {driver_union}"
        if len(union_line) > 120:
            # Break across multiple lines
            lines.append("    driver: (")
            for i, driver_type in enumerate(driver_union_types):
                if i < len(driver_union_types) - 1:
                    lines.append(f"        {driver_type} |")
                else:
                    lines.append(f"        {driver_type}")
            lines.append("    )")
        else:
            lines.append(union_line)
    else:
        # No discriminant - could be composite adapter (like oidc_providers)
        lines.append("    config: dict[str, Any]")

    return class_name, "\n".join(lines), imports


def generate_service_settings_dataclass(
    service_name: str,
    service_settings: dict[str, Any],
) -> tuple[str, str]:
    """Generate a dataclass for service settings.

    Args:
        service_name: Name of the service
        service_settings: The service_settings section from schema

    Returns:
        Tuple of (class_name, class_code)
    """
    class_name = f"ServiceSettings_{to_python_class_name(service_name)}"

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Service-specific settings for {service_name}."""',
    ]

    if not service_settings:
        lines.append("    pass")
    else:
        # Sort settings: required fields without defaults first, then all others
        sorted_settings = sorted(service_settings.items())

        # Separate into two groups
        required_no_default = []
        with_default_or_optional = []

        for setting_name, setting_spec in sorted_settings:
            default = setting_spec.get("default")
            required = setting_spec.get("required", False)

            if required and default is None:
                required_no_default.append((setting_name, setting_spec))
            else:
                with_default_or_optional.append((setting_name, setting_spec))

        # Process all fields in correct order
        all_settings = required_no_default + with_default_or_optional

        for setting_name, setting_spec in all_settings:
            setting_type = setting_spec.get("type", "string")
            default = setting_spec.get("default")
            required = setting_spec.get("required", False)

            py_type = schema_type_to_python_type(setting_type, default)
            field_name = to_python_field_name(setting_name)

            if required and default is None:
                type_annotation = py_type
            else:
                type_annotation = f"{py_type} | None"

            # Generate field with default
            if default is not None:
                if isinstance(default, str):
                    default_repr = repr(default)
                elif isinstance(default, bool):
                    default_repr = str(default)
                elif isinstance(default, (int, float)):
                    default_repr = str(default)
                else:
                    default_repr = repr(default)
                lines.append(f"    {field_name}: {type_annotation} = {default_repr}")
            elif not required:
                lines.append(f"    {field_name}: {type_annotation} = None")
            else:
                lines.append(f"    {field_name}: {type_annotation}")

    return class_name, "\n".join(lines)


def generate_service_config_dataclass(
    service_name: str,
    service_settings_class: str,
    adapter_classes: dict[str, str],
) -> tuple[str, str]:
    """Generate the top-level ServiceConfig dataclass.

    Args:
        service_name: Name of the service
        service_settings_class: Class name for service settings
        adapter_classes: Dict mapping adapter names to their class names

    Returns:
        Tuple of (class_name, class_code)
    """
    class_name = f"ServiceConfig_{to_python_class_name(service_name)}"

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Top-level configuration for {service_name} service."""',
        f"    service_settings: {service_settings_class}",
    ]

    # Add adapter fields (sorted for stability)
    if adapter_classes:
        for adapter_name in sorted(adapter_classes.keys()):
            adapter_class = adapter_classes[adapter_name]
            field_name = to_python_field_name(adapter_name)
            lines.append(f"    {field_name}: {adapter_class} | None = None")

    return class_name, "\n".join(lines)


def generate_typed_config_for_service(
    service_name: str,
    schema_dir: Path,
    output_dir: Path,
) -> None:
    """Generate typed configuration module for a service.

    Args:
        service_name: Name of the service
        schema_dir: Path to schema directory
        output_dir: Path to output directory
    """
    # Load service schema
    service_schema_path = schema_dir / "services" / f"{service_name}.json"
    if not service_schema_path.exists():
        raise FileNotFoundError(f"Service schema not found: {service_schema_path}")

    with open(service_schema_path) as f:
        service_schema = json.load(f)

    # Collect all generated code
    imports = [
        "# SPDX-License-Identifier: MIT",
        "# Copyright (c) 2025 Copilot-for-Consensus contributors",
        "",
        f'"""Generated typed configuration for {service_name} service.',
        "",
        "DO NOT EDIT THIS FILE MANUALLY.",
        "This file is auto-generated from JSON schemas by scripts/generate_typed_configs.py.",
        '"""',
        "",
        "from dataclasses import dataclass",
        "from typing import Any, Literal",
        "",
    ]

    all_classes = []

    # Generate driver configs for each adapter
    adapters_schema = service_schema.get("adapters", {})
    adapter_classes = {}

    for adapter_name, adapter_ref in sorted(adapters_schema.items()):
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue

        # Load adapter schema
        adapter_schema_path = schema_dir / adapter_ref["$ref"].lstrip("../")
        if not adapter_schema_path.exists():
            print(f"Warning: Adapter schema not found: {adapter_schema_path}", file=sys.stderr)
            continue

        with open(adapter_schema_path) as f:
            adapter_schema = json.load(f)

        # Check for discriminant
        discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})

        if not discriminant_info:
            # Skip composite adapters for now (like oidc_providers)
            print(f"Skipping composite adapter: {adapter_name}", file=sys.stderr)
            continue

        # Generate driver configs
        drivers_data = adapter_schema.get("properties", {}).get("drivers", {}).get("properties", {})
        common_properties = adapter_schema.get("properties", {}).get("common", {}).get("properties", {})

        driver_classes = {}
        for driver_name, driver_info in sorted(drivers_data.items()):
            if "$ref" not in driver_info:
                continue

            # Load driver schema
            driver_schema_path = adapter_schema_path.parent / driver_info["$ref"].lstrip("./")
            if not driver_schema_path.exists():
                print(f"Warning: Driver schema not found: {driver_schema_path}", file=sys.stderr)
                continue

            with open(driver_schema_path) as f:
                driver_schema = json.load(f)

            # Generate driver dataclass
            driver_class_name, driver_class_code = generate_driver_dataclass(
                adapter_name,
                driver_name,
                driver_schema,
                common_properties,
            )
            driver_classes[driver_name] = driver_class_name
            all_classes.append(driver_class_code)

        # Generate adapter dataclass
        adapter_class_name, adapter_class_code, adapter_imports = generate_adapter_dataclass(
            adapter_name,
            adapter_schema,
            driver_classes,
        )
        adapter_classes[adapter_name] = adapter_class_name
        all_classes.append(adapter_class_code)

    # Generate service settings dataclass
    service_settings = service_schema.get("service_settings", {})
    service_settings_class, service_settings_code = generate_service_settings_dataclass(
        service_name,
        service_settings,
    )
    all_classes.append(service_settings_code)

    # Generate top-level ServiceConfig dataclass
    service_config_class, service_config_code = generate_service_config_dataclass(
        service_name,
        service_settings_class,
        adapter_classes,
    )
    all_classes.append(service_config_code)

    # Combine everything
    output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

    # Write to file
    output_path = output_dir / f"{service_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(output)

    print(f"Generated: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate typed configuration dataclasses from JSON schemas")
    parser.add_argument(
        "--service",
        help="Generate config for specific service",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate configs for all services",
    )
    parser.add_argument(
        "--output",
        help="Output directory (default: adapters/copilot_config/copilot_config/generated)",
    )

    args = parser.parse_args()

    if not args.service and not args.all:
        parser.error("Must specify either --service or --all")

    # Resolve paths
    try:
        schema_dir = resolve_schema_directory()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.output:
        output_dir = Path(args.output)
    else:
        # Default to generated directory in copilot_config
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        output_dir = repo_root / "adapters" / "copilot_config" / "copilot_config" / "generated"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py in generated directory
    init_file = output_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write("# SPDX-License-Identifier: MIT\n")
            f.write("# Copyright (c) 2025 Copilot-for-Consensus contributors\n")
            f.write("\n")
            f.write('"""Generated typed configuration modules."""\n')

    # Get list of services to generate
    if args.all:
        services_dir = schema_dir / "services"
        services = [p.stem for p in services_dir.glob("*.json") if p.stem not in ["__pycache__"]]
    else:
        services = [args.service]

    # Generate configs
    for service_name in sorted(services):
        try:
            generate_typed_config_for_service(service_name, schema_dir, output_dir)
        except Exception as e:
            print(f"Error generating config for {service_name}: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
