#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generate typed dataclass hierarchies from JSON schemas with 1:1 schema-to-module mapping.

This script reads service/adapter/driver configuration schemas and generates Python dataclasses
with a structure that mirrors the schema file organization:
- docs/schemas/configs/services/X.json → generated/services/X.py
- docs/schemas/configs/adapters/Y.json → generated/adapters/Y.py

This allows each component (service, adapter, driver) to import only what it needs.

Usage:
    python scripts/generate_typed_configs.py --all
    python scripts/generate_typed_configs.py --service ingestion
    python scripts/generate_typed_configs.py --adapter metrics
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def resolve_schema_directory() -> Path:
    """Resolve the schema directory path."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    schema_dir = repo_root / "docs" / "schemas" / "configs"

    if schema_dir.exists():
        return schema_dir

    if "SCHEMA_DIR" in os.environ:
        return Path(os.environ["SCHEMA_DIR"])

    raise FileNotFoundError(f"Schema directory not found at {schema_dir}")


def to_python_class_name(name: str, prefix: str = "") -> str:
    """Convert a schema name to a Python class name."""
    parts = name.split("_")
    pascal_name = "".join(p.capitalize() for p in parts)
    if prefix:
        return f"{prefix}_{pascal_name}"
    return pascal_name


def to_python_field_name(name: str) -> str:
    """Convert a schema field name to a Python field name."""
    return name


def schema_type_to_python_type(schema_type: str, default_value: Any = None) -> str:
    """Convert schema type to Python type annotation.
    
    Uses MyPy-style type hints with typing module (Dict, List, Optional, Union)
    for better compatibility and stricter type checking.
    """
    type_mapping = {
        "string": "str",
        "int": "int",
        "integer": "int",
        "bool": "bool",
        "boolean": "bool",
        "float": "float",
        "number": "float",
        "object": "Dict[str, Any]",
        "array": "List[Any]",
    }

    py_type = type_mapping.get(schema_type, "Any")
    if default_value is not None:
        return py_type

    return py_type


def generate_driver_dataclass(
    adapter_name: str,
    driver_name: str,
    driver_schema: dict[str, Any],
    common_properties: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Generate a dataclass for a specific driver."""
    class_name = f"DriverConfig_{to_python_class_name(adapter_name)}_{to_python_class_name(driver_name)}"

    # Merge driver properties with common properties
    properties = driver_schema.get("properties", {})
    if common_properties:
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
        # Sort properties: required fields without defaults first
        sorted_props = sorted(properties.items())

        required_no_default = []
        with_default_or_optional = []

        for prop_name, prop_spec in sorted_props:
            default = prop_spec.get("default")
            required = prop_spec.get("required", False)

            if required and default is None:
                required_no_default.append((prop_name, prop_spec))
            else:
                with_default_or_optional.append((prop_name, prop_spec))

        all_fields = required_no_default + with_default_or_optional

        for prop_name, prop_spec in all_fields:
            prop_type = prop_spec.get("type", "string")
            default = prop_spec.get("default")
            required = prop_spec.get("required", False)
            description = prop_spec.get("description", "")

            py_type = schema_type_to_python_type(prop_type, default)
            field_name = to_python_field_name(prop_name)

            if required and default is None:
                type_annotation = py_type
            else:
                type_annotation = f"Optional[{py_type}]"

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

            if description:
                desc_safe = description.replace("\n", " ").strip()
                lines.append(f"    # {desc_safe}")

    return class_name, "\n".join(lines)


def generate_adapter_dataclass(
    adapter_name: str,
    adapter_schema: dict[str, Any],
    driver_classes: dict[str, str],
) -> tuple[str, str]:
    """Generate a dataclass for an adapter with driver discrimination."""
    class_name = f"AdapterConfig_{to_python_class_name(adapter_name)}"

    discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})
    discriminant_field = discriminant_info.get("field", "driver_name")
    discriminant_enum = discriminant_info.get("enum", [])

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Configuration for {adapter_name} adapter."""',
    ]

    if discriminant_enum:
        literal_type = "Literal[" + ", ".join(f'"{v}"' for v in sorted(discriminant_enum)) + "]"
        lines.append(f"    {discriminant_field}: {literal_type}")

        driver_union_types = [driver_classes.get(driver, "Any") for driver in sorted(discriminant_enum)]
        driver_union = ", ".join(driver_union_types)

        union_line = f"    driver: Union[{driver_union}]"
        if len(union_line) > 120:
            lines.append("    driver: Union[")
            for i, driver_type in enumerate(driver_union_types):
                if i < len(driver_union_types) - 1:
                    lines.append(f"        {driver_type},")
                else:
                    lines.append(f"        {driver_type}")
            lines.append("    ]")
        else:
            lines.append(union_line)
    else:
        lines.append("    config: Dict[str, Any]")

    return class_name, "\n".join(lines)


def generate_adapter_module(
    adapter_name: str,
    schema_dir: Path,
    output_dir: Path,
) -> str:
    """Generate a module for a specific adapter (1:1 mapping with adapter schema).

    Returns:
        The adapter class name
    """
    adapter_schema_path = schema_dir / "adapters" / f"{adapter_name}.json"
    if not adapter_schema_path.exists():
        raise FileNotFoundError(f"Adapter schema not found: {adapter_schema_path}")

    with open(adapter_schema_path) as f:
        adapter_schema = json.load(f)

    discriminant_info = adapter_schema.get("properties", {}).get("discriminant", {})

    if not discriminant_info:
        print(f"Skipping composite adapter: {adapter_name}", file=sys.stderr)
        return ""

    imports = [
        "# SPDX-License-Identifier: MIT",
        "# Copyright (c) 2025 Copilot-for-Consensus contributors",
        "",
        f'"""Generated typed configuration for {adapter_name} adapter.',
        "",
        "DO NOT EDIT THIS FILE MANUALLY.",
        "This file is auto-generated from JSON schemas by scripts/generate_typed_configs.py.",
        '"""',
        "",
        "from dataclasses import dataclass",
        "from typing import Any, Dict, List, Literal, Optional, Union",
        "",
    ]

    all_classes = []

    # Generate driver configs
    drivers_data = adapter_schema.get("properties", {}).get("drivers", {}).get("properties", {})
    common_properties = adapter_schema.get("properties", {}).get("common", {}).get("properties", {})

    driver_classes = {}
    for driver_name, driver_info in sorted(drivers_data.items()):
        if "$ref" not in driver_info:
            continue

        driver_schema_path = adapter_schema_path.parent / driver_info["$ref"].lstrip("./")
        if not driver_schema_path.exists():
            print(f"Warning: Driver schema not found: {driver_schema_path}", file=sys.stderr)
            continue

        with open(driver_schema_path) as f:
            driver_schema = json.load(f)

        driver_class_name, driver_class_code = generate_driver_dataclass(
            adapter_name,
            driver_name,
            driver_schema,
            common_properties,
        )
        driver_classes[driver_name] = driver_class_name
        all_classes.append(driver_class_code)

    # Generate adapter dataclass
    adapter_class_name, adapter_class_code = generate_adapter_dataclass(
        adapter_name,
        adapter_schema,
        driver_classes,
    )
    all_classes.append(adapter_class_code)

    output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

    output_path = output_dir / "adapters" / f"{adapter_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(output)

    print(f"Generated: {output_path}")
    return adapter_class_name


def generate_service_settings_dataclass(
    service_name: str,
    service_settings: dict[str, Any],
) -> tuple[str, str]:
    """Generate a dataclass for service settings."""
    class_name = f"ServiceSettings_{to_python_class_name(service_name)}"

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Service-specific settings for {service_name}."""',
    ]

    if not service_settings:
        lines.append("    pass")
    else:
        sorted_settings = sorted(service_settings.items())

        required_no_default = []
        with_default_or_optional = []

        for setting_name, setting_spec in sorted_settings:
            default = setting_spec.get("default")
            required = setting_spec.get("required", False)

            if required and default is None:
                required_no_default.append((setting_name, setting_spec))
            else:
                with_default_or_optional.append((setting_name, setting_spec))

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
                type_annotation = f"Optional[{py_type}]"

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
    """Generate the top-level ServiceConfig dataclass."""
    class_name = f"ServiceConfig_{to_python_class_name(service_name)}"

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Top-level configuration for {service_name} service."""',
        f"    service_settings: {service_settings_class}",
    ]

    if adapter_classes:
        for adapter_name in sorted(adapter_classes.keys()):
            adapter_class = adapter_classes[adapter_name]
            field_name = to_python_field_name(adapter_name)
            lines.append(f"    {field_name}: Optional[{adapter_class}] = None")

    return class_name, "\n".join(lines)


def generate_service_module(
    service_name: str,
    schema_dir: Path,
    output_dir: Path,
) -> None:
    """Generate a module for a specific service (1:1 mapping with service schema)."""
    service_schema_path = schema_dir / "services" / f"{service_name}.json"
    if not service_schema_path.exists():
        raise FileNotFoundError(f"Service schema not found: {service_schema_path}")

    with open(service_schema_path) as f:
        service_schema = json.load(f)

    # Determine which adapters this service uses
    adapters_schema = service_schema.get("adapters", {})
    adapter_imports = {}

    for adapter_name, adapter_ref in sorted(adapters_schema.items()):
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue

        # Each adapter has its own module
        adapter_class_name = f"AdapterConfig_{to_python_class_name(adapter_name)}"
        adapter_imports[adapter_name] = adapter_class_name

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
        "from typing import Optional",
        "",
    ]

    # Import adapter classes from their respective modules
    if adapter_imports:
        for adapter_name in sorted(adapter_imports.keys()):
            adapter_class = adapter_imports[adapter_name]
            imports.append(f"from ..adapters.{adapter_name} import {adapter_class}")
        imports.append("")

    all_classes = []

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
        adapter_imports,
    )
    all_classes.append(service_config_code)

    output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

    output_path = output_dir / "services" / f"{service_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(output)

    print(f"Generated: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate typed configuration dataclasses from JSON schemas with 1:1 mapping"
    )
    parser.add_argument("--service", help="Generate config for specific service")
    parser.add_argument("--adapter", help="Generate config for specific adapter")
    parser.add_argument("--all", action="store_true", help="Generate configs for all services and adapters")
    parser.add_argument(
        "--output",
        help="Output directory (default: adapters/copilot_config/copilot_config/generated)",
    )

    args = parser.parse_args()

    if not args.service and not args.adapter and not args.all:
        parser.error("Must specify --service, --adapter, or --all")

    try:
        schema_dir = resolve_schema_directory()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.output:
        output_dir = Path(args.output)
    else:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        output_dir = repo_root / "adapters" / "copilot_config" / "copilot_config" / "generated"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py files
    for subdir in ["adapters", "services"]:
        init_file = output_dir / subdir / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)
        if not init_file.exists():
            with open(init_file, "w") as f:
                f.write("# SPDX-License-Identifier: MIT\n")
                f.write("# Copyright (c) 2025 Copilot-for-Consensus contributors\n")
                f.write("\n")
                f.write(f'"""Generated typed configuration {subdir}."""\n')

    # Update main __init__.py
    main_init = output_dir / "__init__.py"
    if not main_init.exists():
        with open(main_init, "w") as f:
            f.write("# SPDX-License-Identifier: MIT\n")
            f.write("# Copyright (c) 2025 Copilot-for-Consensus contributors\n")
            f.write("\n")
            f.write('"""Generated typed configuration modules."""\n')

    # Generate adapters first (services depend on them)
    if args.all or args.adapter:
        adapters_to_generate = []
        if args.all:
            adapters_dir = schema_dir / "adapters"
            adapters_to_generate = [
                p.stem
                for p in adapters_dir.glob("*.json")
                if p.stem not in ["__pycache__", "oidc_providers"]  # Skip composite adapters
            ]
        else:
            adapters_to_generate = [args.adapter]

        print(f"Generating {len(adapters_to_generate)} adapter modules...")
        for adapter_name in sorted(adapters_to_generate):
            try:
                generate_adapter_module(adapter_name, schema_dir, output_dir)
            except Exception as e:
                print(f"Error generating adapter {adapter_name}: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc()
                if not args.all:
                    return 1

    # Generate services
    if args.all or args.service:
        services_to_generate = []
        if args.all:
            services_dir = schema_dir / "services"
            services_to_generate = [p.stem for p in services_dir.glob("*.json") if p.stem not in ["__pycache__"]]
        else:
            services_to_generate = [args.service]

        print(f"Generating {len(services_to_generate)} service modules...")
        for service_name in sorted(services_to_generate):
            try:
                generate_service_module(service_name, schema_dir, output_dir)
            except Exception as e:
                print(f"Error generating service {service_name}: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc()
                if not args.all:
                    return 1

    print("\nGeneration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
