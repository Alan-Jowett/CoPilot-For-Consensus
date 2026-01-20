# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

from __future__ import annotations

import json
from pathlib import Path

from scripts.log_mining.cli import main
from scripts.log_mining.mining import MiningMeta, MiningResult


def _minimal_result(*, input_path: str = "stdin") -> MiningResult:
    meta = MiningMeta(
        created_utc="2026-01-01T00:00:00Z",
        input_path=input_path,
        input_format="plain",
        group_by="none",
        extract_json_field="message",
        include_fields=["level", "logger"],
        drain3_config_path=None,
        lines_total=0,
        lines_parsed=0,
        templates_total=0,
        services=[],
    )
    return MiningResult(meta=meta, templates=[], anomalies={})


def test_cli_main_mines_and_writes_json(monkeypatch, tmp_path: Path) -> None:
    in_path = tmp_path / "in.txt"
    in_path.write_text("hello\n", encoding="utf-8")

    out_json = tmp_path / "report.json"

    def fake_mine_logs(*, sys_stdin: bool, input_path: Path | None, config) -> MiningResult:  # noqa: ANN001
        assert sys_stdin is False
        assert input_path is not None
        return _minimal_result(input_path=str(input_path))

    def fake_write_report_json(result: MiningResult, output_path: Path) -> None:
        output_path.write_text(json.dumps({"meta": {"input_path": result.meta.input_path}}), encoding="utf-8")

    monkeypatch.setattr("scripts.log_mining.cli.mine_logs", fake_mine_logs)
    monkeypatch.setattr("scripts.log_mining.cli.write_report_json", fake_write_report_json)

    rc = main(["--input", str(in_path), "--output", str(out_json), "--format", "plain", "--group-by", "none"])
    assert rc == 0
    assert out_json.exists()


def test_cli_main_input_is_report_renders_markdown(monkeypatch, tmp_path: Path) -> None:
    report_json = tmp_path / "report.json"
    report_json.write_text(json.dumps({"meta": {}, "templates": [], "anomalies": {}}), encoding="utf-8")

    out_md = tmp_path / "out.md"

    def fake_write_report_markdown_from_report(report: dict, output_path: Path, **kwargs) -> None:  # noqa: ANN001
        output_path.write_text("# ok\n", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.log_mining.cli.write_report_markdown_from_report",
        fake_write_report_markdown_from_report,
    )

    rc = main(
        [
            "--input-is-report",
            "--input",
            str(report_json),
            "--output-markdown",
            str(out_md),
        ]
    )
    assert rc == 0
    assert out_md.read_text(encoding="utf-8").startswith("#")
