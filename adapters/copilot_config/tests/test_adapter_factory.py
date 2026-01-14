# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for copilot_config.adapter_factory."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from copilot_config.adapter_factory import create_adapter


@dataclass
class _TestDriverConfig:
    value: str


@dataclass
class _TestAdapterConfig:
    test_type: str
    driver: _TestDriverConfig


def test_create_adapter_dispatches_case_insensitive():
    config = _TestAdapterConfig(test_type="A", driver=_TestDriverConfig(value="x"))

    created = create_adapter(
        config,
        adapter_name="test_adapter",
        get_driver_type=lambda c: c.test_type,
        get_driver_config=lambda c: c.driver,
        drivers={"a": lambda d: f"created:{d.value}"},
    )

    assert created == "created:x"


def test_create_adapter_unknown_driver_message_is_helpful():
    config = _TestAdapterConfig(test_type="missing", driver=_TestDriverConfig(value="x"))

    with pytest.raises(ValueError, match=r"Unknown test_adapter driver: missing"):
        create_adapter(
            config,
            adapter_name="test_adapter",
            get_driver_type=lambda c: c.test_type,
            get_driver_config=lambda c: c.driver,
            drivers={"a": lambda d: d.value, "b": lambda d: d.value},
        )


def test_create_adapter_requires_config():
    with pytest.raises(ValueError, match=r"test_adapter config is required"):
        create_adapter(  # type: ignore[arg-type]
            None,
            adapter_name="test_adapter",
            get_driver_type=lambda _c: "a",
            get_driver_config=lambda _c: _TestDriverConfig(value="x"),
            drivers={"a": lambda d: d.value},
        )
