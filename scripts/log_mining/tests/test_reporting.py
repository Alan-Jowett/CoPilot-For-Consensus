# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.log_mining.reporting import load_report_json, write_report_markdown_from_report


def test_load_report_json_reads_from_disk(tmp_path: Path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"meta": {"x": 1}, "templates": [], "anomalies": {}}), encoding="utf-8")

    loaded = load_report_json(p)
    assert loaded["meta"]["x"] == 1


def test_load_report_json_raises_on_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_report_json(p)


def test_write_report_markdown_from_report_writes_file(tmp_path: Path) -> None:
    report = {"meta": {"created_utc": "x", "input_path": "y"}, "templates": [], "anomalies": {}}
    out = tmp_path / "out.md"

    write_report_markdown_from_report(report, out)
    assert out.exists()
    assert "Log Mining Summary" in out.read_text(encoding="utf-8")
