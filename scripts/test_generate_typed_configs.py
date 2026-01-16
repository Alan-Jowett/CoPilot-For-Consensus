# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for scripts/generate_typed_configs.py.

These are intentionally narrow unit tests that validate:
- required vs optional field generation
- deterministic ordering
- type mapping
- basic module writing for adapters/services
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_generator_module():
    module_path = Path(__file__).resolve().parent / "generate_typed_configs.py"
    spec = importlib.util.spec_from_file_location("generate_typed_configs", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_driver_dataclass_required_first_and_description_comment():
    gen = _load_generator_module()

    driver_schema = {
        "properties": {
            "required_no_default": {
                "type": "string",
                "required": True,
                "description": "Required string",
            },
            "optional_with_default": {
                "type": "integer",
                "default": 7,
                "description": "Optional int with default",
            },
        }
    }

    class_name, code = gen.generate_driver_dataclass(
        adapter_name="metrics",
        driver_name="pushgateway",
        driver_schema=driver_schema,
        common_properties=None,
    )

    assert class_name == "DriverConfig_Metrics_Pushgateway"

    required_line = "    required_no_default: str"
    optional_line = "    optional_with_default: int = 7"

    assert required_line in code
    assert optional_line in code
    assert code.index(required_line) < code.index(optional_line)

    # Descriptions are consistently emitted as comments (not docstring hacks).
    assert "# Required string" in code
    assert "# Optional int with default" in code
    assert '"""Required string"""' not in code


def test_schema_type_to_python_type_mappings():
    gen = _load_generator_module()

    assert gen.schema_type_to_python_type("string") == "str"
    assert gen.schema_type_to_python_type("integer") == "int"
    assert gen.schema_type_to_python_type("boolean") == "bool"
    assert gen.schema_type_to_python_type("object") == "Dict[str, Any]"
    assert gen.schema_type_to_python_type("array") == "List[Any]"


def test_generate_adapter_and_service_modules_minimal(tmp_path: Path):
    gen = _load_generator_module()

    schema_dir = tmp_path / "docs" / "schemas" / "configs"
    adapters_dir = schema_dir / "adapters"
    services_dir = schema_dir / "services"
    adapters_dir.mkdir(parents=True)
    services_dir.mkdir(parents=True)

    # Adapter schema + driver schema
    (adapters_dir / "drivers" / "metrics").mkdir(parents=True)
    driver_ref = "drivers/metrics/pushgateway.json"

    adapter_schema = {
        "properties": {
            "discriminant": {
                "env_var": "METRICS_TYPE",
                "field": "metrics_type",
                "enum": ["pushgateway"],
                "required": True,
            },
            "drivers": {
                "properties": {
                    "pushgateway": {"$ref": f"./{driver_ref}"},
                }
            },
        }
    }
    (adapters_dir / "metrics.json").write_text(json.dumps(adapter_schema), encoding="utf-8")

    driver_schema = {
        "properties": {
            "gateway": {"type": "string", "required": True},
        }
    }
    (adapters_dir / driver_ref).write_text(json.dumps(driver_schema), encoding="utf-8")

    # Service schema referencing the adapter
    service_schema = {
        "service_settings": {
            "http_port": {"type": "integer", "default": 8000},
        },
        "adapters": {
            "metrics": {"$ref": "../adapters/metrics.json"},
        },
    }
    (services_dir / "ingestion.json").write_text(json.dumps(service_schema), encoding="utf-8")

    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)

    gen.generate_adapter_module("metrics", schema_dir, output_dir)
    gen.generate_service_module("ingestion", schema_dir, output_dir)

    adapter_out = output_dir / "adapters" / "metrics.py"
    service_out = output_dir / "services" / "ingestion.py"

    assert adapter_out.exists()
    assert service_out.exists()

    adapter_text = adapter_out.read_text(encoding="utf-8")
    service_text = service_out.read_text(encoding="utf-8")

    assert "class DriverConfig_Metrics_Pushgateway" in adapter_text
    assert "class AdapterConfig_Metrics" in adapter_text
    assert "metrics_type" in adapter_text

    assert "class ServiceSettings_Ingestion" in service_text
    assert "class ServiceConfig_Ingestion" in service_text
    assert "from ..adapters.metrics import AdapterConfig_Metrics" in service_text


def test_generate_composite_adapter_module(tmp_path: Path):
    gen = _load_generator_module()

    schema_dir = tmp_path / "docs" / "schemas" / "configs"
    adapters_dir = schema_dir / "adapters"
    adapters_dir.mkdir(parents=True)

    # Composite adapter schema with a single top-level object containing $ref driver schemas.
    (adapters_dir / "drivers" / "oidc_providers").mkdir(parents=True)
    github_ref = "drivers/oidc_providers/oidc_github.json"

    adapter_schema = {
        "properties": {
            "oidc_providers": {
                "type": "object",
                "properties": {
                    "github": {"$ref": f"./{github_ref}"},
                },
            }
        }
    }
    (adapters_dir / "oidc_providers.json").write_text(json.dumps(adapter_schema), encoding="utf-8")

    driver_schema = {
        "properties": {
            "github_client_id": {"type": "string", "required": False},
        }
    }
    (adapters_dir / github_ref).write_text(json.dumps(driver_schema), encoding="utf-8")

    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)

    gen.generate_adapter_module("oidc_providers", schema_dir, output_dir)

    adapter_out = output_dir / "adapters" / "oidc_providers.py"
    assert adapter_out.exists()

    adapter_text = adapter_out.read_text(encoding="utf-8")
    assert "class AdapterConfig_OidcProviders" in adapter_text
    assert "class DriverConfig_OidcProviders_Github" in adapter_text
