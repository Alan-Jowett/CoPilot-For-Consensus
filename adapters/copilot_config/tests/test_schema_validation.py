# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for copilot_config.schema_validation.

These tests use a temporary schema directory to avoid coupling to repo schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from copilot_config.schema_validation import validate_driver_config_against_schema


class _Cfg:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_validate_driver_config_required_and_pattern(tmp_path: Path):
    schema_root = tmp_path / "docs" / "schemas" / "configs"

    adapter_schema = {
        "type": "object",
        "properties": {
            "discriminant": {"env_var": "X", "field": "x", "required": True},
            "drivers": {
                "properties": {
                    "foo": {"$ref": "./drivers/example/foo.json"},
                }
            },
        },
    }

    driver_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "device": {"type": "string", "pattern": "^(cpu|cuda)$"},
        },
        "required": ["name", "device"],
        "additionalProperties": False,
    }

    _write(schema_root / "adapters" / "example.json", adapter_schema)
    _write(schema_root / "adapters" / "drivers" / "example" / "foo.json", driver_schema)

    with pytest.raises(ValueError, match="name parameter is required"):
        validate_driver_config_against_schema(
            adapter="example", driver="foo", config=_Cfg(name=None, device="cpu"), schema_dir=str(schema_root)
        )

    with pytest.raises(ValueError, match="device parameter is invalid"):
        validate_driver_config_against_schema(
            adapter="example", driver="foo", config=_Cfg(name="ok", device="tpu"), schema_dir=str(schema_root)
        )

    validate_driver_config_against_schema(
        adapter="example", driver="foo", config=_Cfg(name="ok", device="cpu"), schema_dir=str(schema_root)
    )
