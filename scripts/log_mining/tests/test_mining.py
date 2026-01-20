# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.log_mining.mining import MiningConfig, mine_logs


def test_mine_logs_empty_input(tmp_path: Path) -> None:
    pytest.importorskip("drain3")

    p = tmp_path / "empty.txt"
    p.write_text("", encoding="utf-8")

    cfg = MiningConfig(input_format="plain", group_by="none")
    result = mine_logs(sys_stdin=False, input_path=p, config=cfg)

    assert result.meta.lines_total == 0
    assert result.meta.lines_parsed == 0
    assert result.meta.templates_total == 0
    assert result.templates == []


def test_mine_logs_respects_max_lines(tmp_path: Path) -> None:
    pytest.importorskip("drain3")

    p = tmp_path / "logs.txt"
    p.write_text("a\nb\nc\n", encoding="utf-8")

    cfg = MiningConfig(input_format="plain", group_by="none", max_lines=1)
    result = mine_logs(sys_stdin=False, input_path=p, config=cfg)

    assert result.meta.lines_total == 1
    assert result.meta.lines_parsed == 1
    assert result.meta.templates_total >= 1
