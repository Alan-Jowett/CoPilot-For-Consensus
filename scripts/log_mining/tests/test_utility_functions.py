# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for utility functions in mining.py."""

from __future__ import annotations

from scripts.log_mining.mining import (
    MiningConfig,
    _extract_from_payload_json,
    _parse_docker_line,
    _parse_plain_line,
    _reservoir_add,
    _safe_json_loads,
)


def test_safe_json_loads_valid_object() -> None:
    result = _safe_json_loads('{"key": "value"}')
    assert result == {"key": "value"}


def test_safe_json_loads_valid_array() -> None:
    result = _safe_json_loads('["a", "b"]')
    assert result == ["a", "b"]


def test_safe_json_loads_empty_string() -> None:
    result = _safe_json_loads("")
    assert result is None


def test_safe_json_loads_whitespace_only() -> None:
    result = _safe_json_loads("   ")
    assert result is None


def test_safe_json_loads_invalid_json() -> None:
    result = _safe_json_loads('{"key": ')
    assert result is None


def test_safe_json_loads_non_json_string() -> None:
    result = _safe_json_loads("plain text")
    assert result is None


def test_extract_from_payload_json_with_message() -> None:
    payload = {"level": "ERROR", "logger": "test", "message": "Test message"}
    result = _extract_from_payload_json(payload, extract_field="message", include_fields=["level", "logger"])
    assert result == "level=ERROR logger=test Test message"


def test_extract_from_payload_json_without_message() -> None:
    payload = {"level": "ERROR", "data": "value"}
    result = _extract_from_payload_json(payload, extract_field="message", include_fields=["level"])
    # Should fallback to JSON dump
    assert "level=ERROR" in result
    assert "data" in result


def test_extract_from_payload_json_no_include_fields() -> None:
    payload = {"message": "Test message"}
    result = _extract_from_payload_json(payload, extract_field="message", include_fields=[])
    assert result == "Test message"


def test_parse_plain_line_json() -> None:
    config = MiningConfig(input_format="plain", group_by="none")
    line = '{"level": "ERROR", "message": "Test"}'
    result = _parse_plain_line(line, config)
    assert result is not None
    assert result.service is None
    assert "level=ERROR" in result.message
    assert "Test" in result.message


def test_parse_plain_line_text() -> None:
    config = MiningConfig(input_format="plain", group_by="none")
    line = "Plain text message"
    result = _parse_plain_line(line, config)
    assert result is not None
    assert result.service is None
    assert result.message == "Plain text message"


def test_parse_plain_line_empty() -> None:
    config = MiningConfig(input_format="plain", group_by="none")
    result = _parse_plain_line("", config)
    assert result is None


def test_parse_docker_line_with_service_json() -> None:
    config = MiningConfig(input_format="docker", group_by="service")
    line = 'myservice | {"level": "ERROR", "message": "Test"}'
    result = _parse_docker_line(line, config)
    assert result is not None
    assert result.service == "myservice"
    assert "level=ERROR" in result.message
    assert "Test" in result.message


def test_parse_docker_line_with_service_text() -> None:
    config = MiningConfig(input_format="docker", group_by="service")
    line = "myservice | Plain text message"
    result = _parse_docker_line(line, config)
    assert result is not None
    assert result.service == "myservice"
    assert result.message == "Plain text message"


def test_parse_docker_line_no_prefix() -> None:
    config = MiningConfig(input_format="docker", group_by="service")
    line = "Plain text without docker prefix"
    result = _parse_docker_line(line, config)
    assert result is not None
    assert result.service is None
    assert result.message == "Plain text without docker prefix"


def test_parse_docker_line_empty() -> None:
    config = MiningConfig(input_format="docker", group_by="service")
    result = _parse_docker_line("", config)
    assert result is None


def test_reservoir_add_less_than_k() -> None:
    samples: list[str] = []
    _reservoir_add(samples, "sample1", k=3, seen=1)
    assert samples == ["sample1"]
    _reservoir_add(samples, "sample2", k=3, seen=2)
    assert samples == ["sample1", "sample2"]


def test_reservoir_add_at_k() -> None:
    samples: list[str] = ["s1", "s2", "s3"]
    # With k=3, should replace with decreasing probability
    _reservoir_add(samples, "s4", k=3, seen=4)
    # Can't assert exact replacement due to randomness, but length should stay 3
    assert len(samples) == 3


def test_reservoir_add_k_zero() -> None:
    samples: list[str] = []
    _reservoir_add(samples, "sample", k=0, seen=1)
    assert samples == []


def test_reservoir_add_k_negative() -> None:
    samples: list[str] = []
    _reservoir_add(samples, "sample", k=-1, seen=1)
    assert samples == []
