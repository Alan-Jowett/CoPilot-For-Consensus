# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

from __future__ import annotations

import json
from pathlib import Path

from scripts.log_mining.mining import (
    MiningConfig,
    _iter_azure_console_records_from_obj,
    _iter_azure_diagnostics_records_from_obj,
    _iter_azure_law_records_from_obj,
    iter_records,
    normalize_message,
)
from scripts.log_mining.reporting import write_report_markdown_from_report


def test_normalize_message_replaces_obvious_variables() -> None:
    raw = (
        "2026-01-20T01:25:11.161238Z requestId=1e4a3f06-0b6d-4d2a-b8c8-7c9fd3b8a6c1 "
        "from 10.1.2.3 to https://example.com/api/v1/items/123 port 27017"
    )
    out = normalize_message(raw)
    assert "2026-01-20" not in out
    assert "1e4a3f06-0b6d" not in out
    assert "10.1.2.3" not in out
    assert "https://example.com" not in out
    assert "<TS>" in out
    assert "<GUID>" in out
    assert "<IP>" in out
    assert "<URL>" in out
    assert "<NUM>" in out


def test_iter_records_docker_parses_service_and_json_payload(tmp_path: Path) -> None:
    p = tmp_path / "logs.txt"
    payload = {"timestamp": "2026-01-20T01:25:11.161238Z", "level": "INFO", "logger": "__main__", "message": "Connected to MongoDB at documentdb:27017"}
    p.write_text(f"retry-job-1  | {json.dumps(payload)}\n", encoding="utf-8")

    cfg = MiningConfig(input_format="docker", group_by="service")
    recs = list(iter_records(sys_stdin=False, input_path=p, config=cfg))
    assert len(recs) == 1
    assert recs[0].service.strip() == "retry-job-1"
    assert "level=INFO" in recs[0].message
    assert "logger=__main__" in recs[0].message
    assert "Connected to MongoDB" in recs[0].message


def test_azure_console_extracts_Log_s_and_container_name() -> None:
    obj = [
        {
            "ContainerName_s": "reporting",
            "Log_s": json.dumps({"level": "INFO", "logger": "reporting", "message": "Shutting down"}),
        }
    ]

    cfg = MiningConfig(input_format="azure-console", group_by="service")
    recs = list(_iter_azure_console_records_from_obj(obj, cfg))
    assert len(recs) == 1
    assert recs[0].service == "reporting"
    assert "level=INFO" in recs[0].message
    assert "logger=reporting" in recs[0].message
    assert recs[0].message.endswith("Shutting down")


def test_azure_law_tables_rows_extracts_log_s() -> None:
    obj = {
        "tables": [
            {
                "name": "PrimaryResult",
                "columns": [
                    {"name": "TimeGenerated", "type": "datetime"},
                    {"name": "ContainerName_s", "type": "string"},
                    {"name": "Log_s", "type": "string"},
                ],
                "rows": [
                    [
                        "2026-01-19T23:24:16.4685245Z",
                        "reporting",
                        json.dumps(
                            {
                                "timestamp": "2026-01-19T23:24:15.092559Z",
                                "level": "INFO",
                                "logger": "reporting",
                                "message": "Shutting down",
                            }
                        ),
                    ]
                ],
            }
        ]
    }

    cfg = MiningConfig(input_format="azure-law", group_by="service")
    recs = list(_iter_azure_law_records_from_obj(obj, cfg))
    assert len(recs) == 1
    assert recs[0].service == "reporting"
    assert "level=INFO" in recs[0].message
    assert "logger=reporting" in recs[0].message
    assert recs[0].message.endswith("Shutting down")


def test_azure_diagnostics_extracts_message_and_containerappname() -> None:
    obj = {
        "TimeGenerated": "2026-01-19T23:24:16.4685245Z",
        "Category": "ContainerAppConsoleLogs",
        "Level": "INFO",
        "ContainerAppName": "reporting",
        "Message": "Shutting down",
    }

    cfg = MiningConfig(input_format="azure-diagnostics", group_by="service")
    recs = list(_iter_azure_diagnostics_records_from_obj(obj, cfg))
    assert len(recs) == 1
    assert recs[0].service == "reporting"
    # Default include_fields are level/logger; case-insensitive lookup should find Level.
    assert "level=INFO" in recs[0].message
    assert recs[0].message.endswith("Shutting down")


def test_markdown_focus_includes_warning_and_error(tmp_path: Path) -> None:
    report = {
        "meta": {
            "created_utc": "2026-01-19T00:00:00Z",
            "input_path": "demo",
            "lines_total": 3,
            "templates_total": 2,
        },
        "templates": [
            {
                "service": "svc",
                "template_id": "1",
                "template": "level=INFO logger=x all good",
                "count": 10,
                "samples": ["svc | {\"level\":\"INFO\",\"message\":\"all good\"}"],
            },
            {
                "service": "svc",
                "template_id": "2",
                "template": "level=ERROR logger=x something failed",
                "count": 1,
                "samples": ["svc | {\"level\":\"ERROR\",\"message\":\"something failed\"}"],
            },
        ],
        "anomalies": {},
    }

    out = tmp_path / "out.md"
    write_report_markdown_from_report(
        report,
        out,
        focus_levels=["ERROR", "WARNING"],
        include_keywords=False,
        top_n=10,
        per_service_n=10,
        rare_threshold=2,
        max_samples_per_template=1,
    )

    text = out.read_text(encoding="utf-8")
    assert "level=ERROR" in text
    assert "level=INFO" not in text
