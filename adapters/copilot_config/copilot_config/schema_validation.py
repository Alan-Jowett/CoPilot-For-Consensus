# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema-driven runtime validation helpers.

This module provides lightweight (stdlib-only) validation that interprets a
subset of JSON Schema keywords used by this repository.

Purpose:
- Keep "what is required/valid" in JSON Schemas.
- Provide a shared validation entry point for libraries/adapters that may be
  instantiated with already-constructed config objects (bypassing the loaders).

Note:
- Full JSON Schema validation would normally use the `jsonschema` package.
  This project keeps `copilot_config` dependency-free, so we implement only the
  small subset we rely on operationally: required, minLength, pattern, enum,
  minimum/maximum, and a basic `format: uri` check.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _resolve_schema_directory(schema_dir: str | None = None) -> Path:
    """Resolve the schema directory used by the repository."""
    if schema_dir is not None:
        return Path(schema_dir)

    # Prefer explicit environment override if present.
    import os

    env_dir = os.environ.get("SCHEMA_DIR")
    if env_dir:
        return Path(env_dir)

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "schemas" / "configs"
        if candidate.exists():
            return candidate

    # Fallback to CWD.
    return Path.cwd() / "docs" / "schemas" / "configs"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _adapter_driver_schema_path(*, schema_dir: Path, adapter: str, driver: str) -> Path:
    adapter_schema_path = schema_dir / "adapters" / f"{adapter}.json"
    if not adapter_schema_path.exists():
        raise FileNotFoundError(f"Adapter schema not found: {adapter_schema_path}")

    adapter_schema = _load_json(adapter_schema_path)
    drivers = (
        adapter_schema.get("properties", {})
        .get("drivers", {})
        .get("properties", {})
    )

    driver_info = drivers.get(driver)
    if not isinstance(driver_info, dict) or "$ref" not in driver_info:
        raise ValueError(f"Adapter {adapter} has no schema reference for driver {driver}")

    ref = driver_info["$ref"]
    if not isinstance(ref, str) or not ref:
        raise ValueError(f"Invalid $ref for {adapter}/{driver}: {ref!r}")

    return schema_dir / "adapters" / ref.lstrip("./")


def _as_mapping(config: object) -> dict[str, Any]:
    if is_dataclass(config):
        return asdict(config)
    if isinstance(config, dict):
        return config

    # Best-effort: treat as attribute bag.
    return {
        name: getattr(config, name)
        for name in dir(config)
        if not name.startswith("_") and not callable(getattr(config, name))
    }


def _is_missing_required_value(value: Any, prop_spec: dict[str, Any]) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        min_length = prop_spec.get("minLength")
        if isinstance(min_length, int) and min_length >= 1:
            if len(value.strip()) < min_length:
                return True

    return False


def _validate_uri(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _select_oneof_variant(schema: dict[str, Any], config_map: dict[str, Any]) -> dict[str, Any]:
    if "oneOf" not in schema:
        return schema

    discriminant_info = schema.get("discriminant", {})
    if not isinstance(discriminant_info, dict):
        return schema

    field = discriminant_info.get("field")
    if not isinstance(field, str) or not field:
        return schema

    selected = config_map.get(field)
    if selected is None:
        # Fallback to environment discriminant if config object doesn't contain it.
        env_var = discriminant_info.get("env_var")
        if isinstance(env_var, str) and env_var:
            import os

            selected = os.environ.get(env_var)

    one_of = schema.get("oneOf")
    if not isinstance(one_of, list) or selected is None:
        return schema

    for candidate in one_of:
        if not isinstance(candidate, dict):
            continue
        props = candidate.get("properties", {})
        if not isinstance(props, dict):
            continue
        disc_prop = props.get(field)
        if isinstance(disc_prop, dict) and disc_prop.get("const") == selected:
            return candidate

    # Unknown discriminant value: let required-field validation catch missing.
    return schema


def validate_driver_config_against_schema(
    *,
    adapter: str,
    driver: str,
    config: object,
    schema_dir: str | None = None,
) -> None:
    """Validate a driver config instance against its JSON schema.

    Raises:
        ValueError: when required fields are missing or constraints fail.
        FileNotFoundError: when schema files are missing.
    """
    schema_root = _resolve_schema_directory(schema_dir)
    driver_schema_path = _adapter_driver_schema_path(schema_dir=schema_root, adapter=adapter, driver=driver)
    if not driver_schema_path.exists():
        raise FileNotFoundError(f"Driver schema not found: {driver_schema_path}")

    schema = _load_json(driver_schema_path)
    config_map = _as_mapping(config)

    schema = _select_oneof_variant(schema, config_map)

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    required_fields: set[str] = set()
    required_list = schema.get("required", [])
    if isinstance(required_list, list):
        required_fields |= {x for x in required_list if isinstance(x, str)}

    # Back-compat: some schemas still set per-property required flags.
    for name, spec in properties.items():
        if isinstance(spec, dict) and spec.get("required") is True:
            required_fields.add(name)

    # Required checks
    for field_name in sorted(required_fields):
        spec = properties.get(field_name, {})
        if not isinstance(spec, dict):
            spec = {}

        value = config_map.get(field_name)
        if _is_missing_required_value(value, spec):
            raise ValueError(f"{field_name} parameter is required")

    # Optional/provided checks
    for field_name, spec in properties.items():
        if not isinstance(spec, dict):
            continue

        value = config_map.get(field_name)
        if value is None:
            continue

        if isinstance(value, str):
            min_length = spec.get("minLength")
            if isinstance(min_length, int) and min_length >= 1 and len(value.strip()) < min_length:
                raise ValueError(f"{field_name} parameter is required")

            pattern = spec.get("pattern")
            if isinstance(pattern, str) and pattern:
                if re.match(pattern, value) is None:
                    raise ValueError(f"{field_name} parameter is invalid")

            enum = spec.get("enum")
            if isinstance(enum, list) and enum and value not in enum:
                raise ValueError(f"{field_name} parameter is invalid")

            fmt = spec.get("format")
            if fmt == "uri" and not _validate_uri(value):
                raise ValueError(f"{field_name} parameter is invalid")

        if isinstance(value, (int, float)):
            minimum = spec.get("minimum")
            if isinstance(minimum, (int, float)) and value < minimum:
                raise ValueError(f"{field_name} parameter is invalid")

            maximum = spec.get("maximum")
            if isinstance(maximum, (int, float)) and value > maximum:
                raise ValueError(f"{field_name} parameter is invalid")
