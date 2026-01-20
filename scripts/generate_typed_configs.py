#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generate typed dataclass hierarchies from JSON schemas with 1:1 schema-to-module mapping.

This script reads service/adapter/driver configuration schemas and generates Python dataclasses
with a structure that mirrors the schema file organization:
- docs/schemas/v1/configs/services/X.json → generated/services/X.py
- docs/schemas/v1/configs/adapters/Y.json → generated/adapters/Y.py

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
import textwrap
from pathlib import Path
from typing import Any

_MAX_LINE_LENGTH = 120


def _wrap_comment_lines(description: str, *, indent: str = "    # ") -> list[str]:
    """Wrap description text into comment lines within the configured line length."""
    available_width = max(1, _MAX_LINE_LENGTH - len(indent))
    lines: list[str] = []
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        for wrapped in textwrap.wrap(
            stripped,
            width=available_width,
            break_long_words=False,
            break_on_hyphens=False,
        ):
            lines.append(f"{indent}{wrapped}")
    return lines


def _pipe_union(type_names: list[str]) -> str:
    """Join type names as a PEP 604 pipe-union, preserving order and removing duplicates."""
    unique: list[str] = []
    seen: set[str] = set()
    for type_name in type_names:
        if type_name in seen:
            continue
        seen.add(type_name)
        unique.append(type_name)
    return " | ".join(unique)


def _make_optional(type_annotation: str) -> str:
    """Return a type annotation that includes None (PEP 604 style)."""
    parts = [p.strip() for p in type_annotation.split("|")]
    if any(p == "None" for p in parts):
        return type_annotation
    if type_annotation:
        return f"{type_annotation} | None"
    return "None"


def resolve_schema_directory() -> Path:
    """Resolve the schema directory path."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    schema_dir = repo_root / "docs" / "schemas" / "v1" / "configs"

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


def schema_type_to_python_type(schema_type: str | list[Any], default_value: Any = None) -> str:
    """Convert schema type to a Python type annotation.

    Notes:
    - Supports a JSON Schema "type" being either a string or a list.
    - Uses PEP 604 unions (e.g., `str | None`) and builtin generics (e.g., `dict[str, Any]`).
    """

    del default_value

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
        "null": "None",
    }

    if isinstance(schema_type, list):
        non_null = [t for t in schema_type if t != "null"]
        mapped = [type_mapping.get(t, "Any") for t in non_null]
        if "null" in schema_type:
            mapped.append("None")
        if not mapped:
            return "Any"
        if len(mapped) == 1:
            return mapped[0]
        return _pipe_union(mapped)

    return type_mapping.get(schema_type, "Any")


def _type_allows_null(prop_spec: dict[str, Any]) -> bool:
    schema_type = prop_spec.get("type")
    return isinstance(schema_type, list) and "null" in schema_type


def _format_literal(value: Any) -> str:
    """Format a literal value for embedding in generated Python."""
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int | float):
        return str(value)
    return repr(value)


def _generate_dataclass_code(
    *,
    class_name: str,
    doc: str,
    properties: dict[str, Any],
    required_fields: set[str] | None = None,
) -> str:
    """Generate a dataclass body for a schema properties dict."""
    required_fields = required_fields or set()
    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """{doc}"""',
    ]

    # Match checked-in formatting: blank line between docstring and body.
    lines.append("")

    if not properties:
        lines.append("    pass")
        return "\n".join(lines)

    sorted_props = sorted(properties.items())

    required_no_default: list[tuple[str, dict[str, Any]]] = []
    with_default_or_optional: list[tuple[str, dict[str, Any]]] = []

    for prop_name, prop_spec in sorted_props:
        if not isinstance(prop_spec, dict):
            continue

        # const fields are always required and have an implicit default
        if "const" in prop_spec:
            with_default_or_optional.append((prop_name, prop_spec))
            continue

        default = prop_spec.get("default")
        required = prop_name in required_fields or prop_spec.get("required", False)

        if required and default is None:
            required_no_default.append((prop_name, prop_spec))
        else:
            with_default_or_optional.append((prop_name, prop_spec))

    all_fields = required_no_default + with_default_or_optional

    for prop_name, prop_spec in all_fields:
        prop_type = prop_spec.get("type", "string")
        default = prop_spec.get("default")
        required = prop_name in required_fields or prop_spec.get("required", False)
        description = prop_spec.get("description", "")

        field_name = to_python_field_name(prop_name)

        if "const" in prop_spec:
            const_value = prop_spec["const"]
            type_annotation = f"Literal[{_format_literal(const_value)}]"
            lines.append(f"    {field_name}: {type_annotation} = {_format_literal(const_value)}")
        else:
            py_type = schema_type_to_python_type(prop_type, default)

            if required:
                # Required fields should not be Optional unless schema explicitly allows null.
                type_annotation = py_type
            else:
                if default is not None and not _type_allows_null(prop_spec):
                    # A non-null default implies the value is always present.
                    type_annotation = py_type
                else:
                    # Truly optional field.
                    type_annotation = py_type if _type_allows_null(prop_spec) else _make_optional(py_type)

            if default is not None:
                lines.append(f"    {field_name}: {type_annotation} = {_format_literal(default)}")
            elif not required:
                lines.append(f"    {field_name}: {type_annotation} = None")
            else:
                lines.append(f"    {field_name}: {type_annotation}")

        if description:
            lines.extend(_wrap_comment_lines(description))

    return "\n".join(lines)


def generate_driver_dataclass(
    adapter_name: str,
    driver_name: str,
    driver_schema: dict[str, Any],
    common_properties: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Generate a dataclass for a specific driver."""
    class_name = f"DriverConfig_{to_python_class_name(adapter_name)}_{to_python_class_name(driver_name)}"

    # Support strict discriminated unions for drivers with nested oneOf schemas.
    if "oneOf" in driver_schema:
        discriminant_info = driver_schema.get("discriminant", {}) if isinstance(driver_schema, dict) else {}
        discriminant_field = discriminant_info.get("field")

        one_of = driver_schema.get("oneOf")
        if not isinstance(one_of, list) or not discriminant_field:
            raise ValueError(
                f"Driver schema for {adapter_name}/{driver_name} uses oneOf but is missing a discriminant.field"
            )

        variant_class_names: list[str] = []
        variant_codes: list[str] = []

        for idx, variant_schema in enumerate(one_of):
            if not isinstance(variant_schema, dict):
                continue

            properties = variant_schema.get("properties", {})
            if not isinstance(properties, dict):
                properties = {}

            required_list = variant_schema.get("required", [])
            required_fields = set(required_list) if isinstance(required_list, list) else set()

            if common_properties:
                for key, value in common_properties.items():
                    if key not in properties:
                        properties[key] = value

            # Prefer the discriminant const value for naming.
            discriminant_prop = properties.get(discriminant_field, {})
            const_value = None
            if isinstance(discriminant_prop, dict):
                const_value = discriminant_prop.get("const")

            variant_suffix = None
            if isinstance(const_value, str) and const_value:
                variant_suffix = to_python_class_name(const_value)
            elif isinstance(variant_schema.get("title"), str) and variant_schema.get("title"):
                variant_suffix = to_python_class_name(variant_schema["title"].replace(" ", "_"))
            else:
                variant_suffix = f"Variant{idx + 1}"

            variant_class_name = f"{class_name}_{variant_suffix}"
            variant_class_names.append(variant_class_name)
            variant_codes.append(
                _generate_dataclass_code(
                    class_name=variant_class_name,
                    doc=f"Configuration variant for {adapter_name} adapter using {driver_name} driver.",
                    properties=properties,
                    required_fields=required_fields,
                )
            )

        if not variant_class_names:
            raise ValueError(f"Driver schema for {adapter_name}/{driver_name} oneOf produced no variants")

        alias_lines = [f"{class_name}: TypeAlias = ("]
        for idx, variant_class_name in enumerate(variant_class_names):
            if idx == 0:
                alias_lines.append(f"    {variant_class_name}")
            else:
                alias_lines.append(f"    | {variant_class_name}")
        alias_lines.append(")")
        alias_code = "\n".join(alias_lines)

        return class_name, "\n\n\n".join([*variant_codes, alias_code])

    # Merge driver properties with common properties
    properties = driver_schema.get("properties", {})
    if common_properties:
        for key, value in common_properties.items():
            if key not in properties:
                properties[key] = value

    required_list = driver_schema.get("required", [])
    required_fields = set(required_list) if isinstance(required_list, list) else set()

    return class_name, _generate_dataclass_code(
        class_name=class_name,
        doc=f"Configuration for {adapter_name} adapter using {driver_name} driver.",
        properties=properties,
        required_fields=required_fields,
    )


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

    # Match checked-in formatting: blank line between docstring and fields.
    lines.append("")

    if discriminant_enum:
        literal_type = "Literal[" + ", ".join(json.dumps(v) for v in sorted(discriminant_enum)) + "]"
        lines.append(f"    {discriminant_field}: {literal_type}")

        raw_driver_union_types = [driver_classes.get(driver, "Any") for driver in sorted(discriminant_enum)]
        driver_union_types: list[str] = []
        for type_name in raw_driver_union_types:
            if type_name not in driver_union_types:
                driver_union_types.append(type_name)

        driver_union = _pipe_union(driver_union_types)
        driver_line = f"    driver: {driver_union}"

        # Match checked-in formatting: wrap only when the union would get very long.
        # Empirically, the repo wraps `driver:` unions when there are 3+ variants and
        # the single-line representation is roughly 120+ chars.
        if len(driver_union_types) >= 3 and len(driver_line) >= 120:
            lines.append("    driver: (")
            for idx, type_name in enumerate(driver_union_types):
                if idx == 0:
                    lines.append(f"        {type_name}")
                else:
                    lines.append(f"        | {type_name}")
            lines.append("    )")
        else:
            lines.append(driver_line)
    else:
        lines.append("    config: dict[str, Any]")

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

    all_classes = []

    # Composite adapters (no discriminant) are still generated so that service modules
    # can import their AdapterConfig_* types and static analysis (e.g., pylint) doesn't fail.
    if not discriminant_info:
        adapter_class_name = f"AdapterConfig_{to_python_class_name(adapter_name)}"

        properties = adapter_schema.get("properties", {})

        # Best-effort typed composite support:
        # - If the adapter schema is a single top-level object containing provider keys ($ref),
        #   generate DriverConfig_* dataclasses and a nested container dataclass.
        # - Otherwise, fall back to a generic Dict[str, Any] config field.
        if len(properties) == 1:
            composite_field_name, composite_spec = next(iter(properties.items()))
            composite_properties = composite_spec.get("properties", {}) if isinstance(composite_spec, dict) else {}

            driver_classes: dict[str, str] = {}
            for driver_name, driver_info in sorted(composite_properties.items()):
                if not isinstance(driver_info, dict) or "$ref" not in driver_info:
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
                    common_properties=None,
                )
                driver_classes[driver_name] = driver_class_name
                all_classes.append(driver_class_code)

            container_class_name = f"CompositeConfig_{to_python_class_name(adapter_name)}"
            container_lines = [
                "@dataclass",
                f"class {container_class_name}:",
                f'    """Composite configuration container for {adapter_name} adapter."""',
            ]

            container_lines.append("")

            if driver_classes:
                for driver_name in sorted(driver_classes.keys()):
                    field_name = to_python_field_name(driver_name)
                    driver_class_name = driver_classes[driver_name]
                    container_lines.append(f"    {field_name}: {driver_class_name} | None = None")
            else:
                container_lines.append("    config: dict[str, Any]")

            all_classes.append("\n".join(container_lines))

            adapter_lines = [
                "@dataclass",
                f"class {adapter_class_name}:",
                f'    """Configuration for {adapter_name} adapter."""',
                "",
                f"    {to_python_field_name(composite_field_name)}: {container_class_name} | None = None",
            ]
            all_classes.append("\n".join(adapter_lines))
        else:
            adapter_lines = [
                "@dataclass",
                f"class {adapter_class_name}:",
                f'    """Configuration for {adapter_name} adapter."""',
                "",
                "    config: dict[str, Any]",
            ]
            all_classes.append("\n".join(adapter_lines))

        combined = "\n".join(all_classes)
        typing_names: list[str] = []
        if "Any" in combined:
            typing_names.append("Any")
        if "Literal[" in combined:
            typing_names.append("Literal")
        if "TypeAlias" in combined:
            typing_names.append("TypeAlias")

        ordered = [name for name in ["Any", "Literal", "TypeAlias"] if name in typing_names]

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
        ]
        if ordered:
            imports.append(f"from typing import {', '.join(ordered)}")

        # Match checked-in formatting: leave two blank lines before first class.
        imports.append("")

        output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

        output_path = output_dir / "adapters" / f"{adapter_name}.py"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(output)

        print(f"Generated: {output_path}")
        return adapter_class_name

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

    combined = "\n".join(all_classes)
    typing_names: list[str] = []
    if "Any" in combined:
        typing_names.append("Any")
    if "Literal[" in combined:
        typing_names.append("Literal")
    if "TypeAlias" in combined:
        typing_names.append("TypeAlias")

    ordered = [name for name in ["Any", "Literal", "TypeAlias"] if name in typing_names]

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
    ]
    if ordered:
        imports.append(f"from typing import {', '.join(ordered)}")

    # Match checked-in formatting: leave two blank lines before first class.
    imports.append("")

    output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

    output_path = output_dir / "adapters" / f"{adapter_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
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
        # Match checked-in formatting: blank line between docstring and fields.
        lines.append("")
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
                type_annotation = _make_optional(py_type)

            if default is not None:
                lines.append(f"    {field_name}: {type_annotation} = {_format_literal(default)}")
            elif not required:
                lines.append(f"    {field_name}: {type_annotation} = None")
            else:
                lines.append(f"    {field_name}: {type_annotation}")

    return class_name, "\n".join(lines)


def generate_service_config_dataclass(
    service_name: str,
    service_settings_class: str,
    adapter_classes: dict[str, str],
    required_adapters: set[str] | None = None,
) -> tuple[str, str]:
    """Generate the top-level ServiceConfig dataclass."""
    class_name = f"ServiceConfig_{to_python_class_name(service_name)}"

    required_adapters = required_adapters or set()

    lines = [
        "@dataclass",
        f"class {class_name}:",
        f'    """Top-level configuration for {service_name} service."""',
        "",
        f"    service_settings: {service_settings_class}",
    ]

    if adapter_classes:
        required_fields: list[tuple[str, str]] = []
        optional_fields: list[tuple[str, str]] = []

        for adapter_name in sorted(adapter_classes.keys()):
            adapter_class = adapter_classes[adapter_name]
            field_name = to_python_field_name(adapter_name)

            if adapter_name in required_adapters:
                required_fields.append((field_name, adapter_class))
            else:
                optional_fields.append((field_name, adapter_class))

        # Dataclasses require all non-default fields to come before defaulted fields.
        for field_name, adapter_class in required_fields:
            lines.append(f"    {field_name}: {adapter_class}")
        for field_name, adapter_class in optional_fields:
            lines.append(f"    {field_name}: {adapter_class} | None = None")

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
    required_adapters: set[str] = set()

    for adapter_name, adapter_ref in sorted(adapters_schema.items()):
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue

        if adapter_ref.get("required") is True:
            required_adapters.add(adapter_name)

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
        required_adapters,
    )
    all_classes.append(service_config_code)

    output = "\n".join(imports) + "\n\n" + "\n\n\n".join(all_classes) + "\n"

    output_path = output_dir / "services" / f"{service_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
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
            adapters_to_generate = [p.stem for p in adapters_dir.glob("*.json") if p.stem not in ["__pycache__"]]
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
