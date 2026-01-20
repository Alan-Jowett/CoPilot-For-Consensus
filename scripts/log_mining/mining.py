# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Log template mining + anomaly-focused sampling.

This module is intentionally streaming-friendly (large input files).
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MiningConfig:
    input_format: str = "auto"  # auto|plain|docker|azure-console|azure-law
    group_by: str = "service"  # none|service
    extract_json_field: str = "message"
    include_fields: list[str] = field(default_factory=lambda: ["level", "logger"])
    max_lines: int = 0
    per_template_samples: int = 3
    rare_template_threshold: int = 5
    drain3_config_path: Path | None = None
    emit_top: int = 50
    emit_rare: int = 200


@dataclass
class MiningMeta:
    created_utc: str
    input_path: str
    input_format: str
    group_by: str
    extract_json_field: str
    include_fields: list[str]
    drain3_config_path: str | None

    lines_total: int = 0
    lines_parsed: int = 0
    templates_total: int = 0
    services: list[str] = field(default_factory=list)


@dataclass
class TemplateStats:
    template_id: str
    template: str
    service: str | None
    count: int = 0
    placeholders: int = 0

    first_seen_line: int | None = None

    samples: list[str] = field(default_factory=list)

    shortest_sample: str | None = None
    shortest_len: int | None = None

    longest_sample: str | None = None
    longest_len: int | None = None


@dataclass
class MiningResult:
    meta: MiningMeta
    templates: list[TemplateStats]
    anomalies: dict[str, Any]


@dataclass(frozen=True)
class ParsedRecord:
    service: str | None
    message: str
    raw: str


_DOCKER_PREFIX_RE = re.compile(r"^(?P<service>[^|]+?)\s*\|\s*(?P<payload>.*)$")


_ISO_TS_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"
)
_GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_INT_RE = re.compile(r"\b\d+\b")
_URL_RE = re.compile(r"\bhttps?://\S+\b")


def normalize_message(text: str) -> str:
    """Normalize obvious variables while preserving signal."""

    text = _ISO_TS_RE.sub("<TS>", text)
    text = _GUID_RE.sub("<GUID>", text)
    text = _IP_RE.sub("<IP>", text)
    text = _URL_RE.sub("<URL>", text)
    text = _HEX_RE.sub("<HEX>", text)

    # Replace standalone integers; preserve numbers embedded in words.
    text = _INT_RE.sub("<NUM>", text)

    # Collapse whitespace
    return " ".join(text.split())


def _safe_json_loads(value: str) -> Any | None:
    value = value.strip()
    if not value:
        return None
    if not ((value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]"))):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _extract_from_payload_json(
    payload_obj: dict[str, Any],
    *,
    extract_field: str,
    include_fields: list[str],
) -> str:
    prefix_parts: list[str] = []
    for f in include_fields:
        v = payload_obj.get(f)
        if v is None:
            continue
        prefix_parts.append(f"{f}={v}")

    msg = payload_obj.get(extract_field)
    if msg is None:
        # Fallback: dump compactly, but keep deterministic ordering.
        msg = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))

    if prefix_parts:
        return f"{' '.join(prefix_parts)} {msg}"
    return str(msg)


def _parse_plain_line(line: str, config: MiningConfig) -> ParsedRecord | None:
    line = line.rstrip("\r\n")
    if not line.strip():
        return None

    payload_obj = _safe_json_loads(line)
    if isinstance(payload_obj, dict):
        msg = _extract_from_payload_json(
            payload_obj,
            extract_field=config.extract_json_field,
            include_fields=config.include_fields,
        )
        return ParsedRecord(service=None, message=msg, raw=line)

    return ParsedRecord(service=None, message=line, raw=line)


def _parse_docker_line(line: str, config: MiningConfig) -> ParsedRecord | None:
    line = line.rstrip("\r\n")
    if not line.strip():
        return None

    m = _DOCKER_PREFIX_RE.match(line)
    if not m:
        # Not a docker-prefixed line; treat as plain.
        rec = _parse_plain_line(line, config)
        if rec is None:
            return None
        return ParsedRecord(service=None, message=rec.message, raw=line)

    service = m.group("service").strip()
    payload = m.group("payload").strip()

    payload_obj = _safe_json_loads(payload)
    if isinstance(payload_obj, dict):
        msg = _extract_from_payload_json(
            payload_obj,
            extract_field=config.extract_json_field,
            include_fields=config.include_fields,
        )
        return ParsedRecord(service=service, message=msg, raw=line)

    return ParsedRecord(service=service, message=payload, raw=line)


def _iter_azure_console_records_from_obj(
    obj: Any,
    config: MiningConfig,
) -> Iterator[ParsedRecord]:
    """Iterate Azure Container Apps console log exports.

    Supports:
    - JSON array of objects, each containing at least `Log_s`.
    - JSON object with a `data` array (best-effort).

    Note: For huge exports, prefer JSON Lines and pass `--format azure-console`.
    """

    items: list[Any] = []
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        if isinstance(obj.get("data"), list):
            items = obj["data"]
        else:
            # Single row
            items = [obj]

    for row in items:
        if not isinstance(row, dict):
            continue

        service = (
            row.get("ContainerName_s")
            or row.get("ContainerAppName_s")
            or row.get("container")
        )

        payload = row.get("Log_s") or row.get("log") or row.get("message")
        if not payload:
            continue

        if isinstance(payload, str):
            payload_obj = _safe_json_loads(payload)
            if isinstance(payload_obj, dict):
                msg = _extract_from_payload_json(
                    payload_obj,
                    extract_field=config.extract_json_field,
                    include_fields=config.include_fields,
                )
                yield ParsedRecord(service=str(service) if service else None, message=msg, raw=payload)
            else:
                yield ParsedRecord(service=str(service) if service else None, message=payload, raw=payload)


def _iter_azure_law_records_from_obj(
    obj: Any,
    config: MiningConfig,
) -> Iterator[ParsedRecord]:
    """Iterate Azure Log Analytics query results.

    Supports the common `az monitor log-analytics query -o json` structure:

    {
      "tables": [
        {
          "name": "PrimaryResult",
          "columns": [{"name": "Log_s"}, ...],
          "rows": [[...], ...]
        }
      ]
    }

    Also supports a list-of-objects export (already-row-mapped JSON).
    """

    # If already a list of dict rows, reuse console parsing heuristics.
    if isinstance(obj, list):
        yield from _iter_azure_console_records_from_obj(obj, config)
        return

    if not isinstance(obj, dict):
        return

    tables = obj.get("tables") or obj.get("Tables")
    if not isinstance(tables, list):
        # Could be a single-row dict
        yield from _iter_azure_console_records_from_obj(obj, config)
        return

    for table in tables:
        if not isinstance(table, dict):
            continue

        columns = table.get("columns")
        rows = table.get("rows")
        if not isinstance(columns, list) or not isinstance(rows, list):
            continue

        column_names: list[str] = []
        for c in columns:
            if isinstance(c, dict) and isinstance(c.get("name"), str):
                column_names.append(c["name"])

        if not column_names:
            continue

        for row in rows:
            if not isinstance(row, list):
                continue
            if len(row) != len(column_names):
                # Best-effort: skip malformed rows
                continue

            row_dict = dict(zip(column_names, row, strict=False))
            yield from _iter_azure_console_records_from_obj(row_dict, config)


def _load_json_file_best_effort(path: Path) -> Any:
    # Best-effort load for azure console exports. If the file is huge, this can be memory heavy.
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def iter_records(
    *,
    sys_stdin: bool,
    input_path: Path | None,
    config: MiningConfig,
) -> Iterator[ParsedRecord]:
    if config.input_format in {"plain"}:
        if sys_stdin:
            for line in sys.stdin:
                rec = _parse_plain_line(line, config)
                if rec:
                    yield rec
        else:
            assert input_path is not None
            with input_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    rec = _parse_plain_line(line, config)
                    if rec:
                        yield rec
        return

    if config.input_format in {"docker"}:
        if sys_stdin:
            for line in sys.stdin:
                rec = _parse_docker_line(line, config)
                if rec:
                    yield rec
        else:
            assert input_path is not None
            with input_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    rec = _parse_docker_line(line, config)
                    if rec:
                        yield rec
        return

    if config.input_format in {"azure-console"}:
        if sys_stdin:
            # JSON lines mode: each line is an object
            for line in sys.stdin:
                row = _safe_json_loads(line)
                if row is None:
                    continue
                yield from _iter_azure_console_records_from_obj(row, config)
        else:
            assert input_path is not None
            obj = _load_json_file_best_effort(input_path)
            yield from _iter_azure_console_records_from_obj(obj, config)
        return

    if config.input_format in {"azure-law"}:
        if sys_stdin:
            # JSON lines mode: each line is an object/table payload
            for line in sys.stdin:
                row = _safe_json_loads(line)
                if row is None:
                    continue
                yield from _iter_azure_law_records_from_obj(row, config)
        else:
            assert input_path is not None
            obj = _load_json_file_best_effort(input_path)
            yield from _iter_azure_law_records_from_obj(obj, config)
        return

    # auto
    if sys_stdin:
        # Assume docker compose logs by default for stdin
        for line in sys.stdin:
            rec = _parse_docker_line(line, config)
            if rec:
                yield rec
        return

    assert input_path is not None
    # Detect based on first non-empty character
    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        first_nonempty = ""
        for line in f:
            if line.strip():
                first_nonempty = line.lstrip()[:1]
                break

    if first_nonempty == "[" or first_nonempty == "{":
        # Distinguish Azure Log Analytics query results (tables/rows) vs console exports.
        # We intentionally peek only at JSON header to keep this fast.
        try:
            with input_path.open("r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
            head_obj = _safe_json_loads(head)
        except Exception:
            head_obj = None

        if isinstance(head_obj, dict) and ("tables" in head_obj or "Tables" in head_obj):
            config = MiningConfig(**{**config.__dict__, "input_format": "azure-law"})
        else:
            config = MiningConfig(**{**config.__dict__, "input_format": "azure-console"})

        yield from iter_records(sys_stdin=False, input_path=input_path, config=config)
    else:
        # Assume docker compose logs
        config = MiningConfig(**{**config.__dict__, "input_format": "docker"})
        yield from iter_records(sys_stdin=False, input_path=input_path, config=config)


def _reservoir_add(samples: list[str], sample: str, k: int, seen: int) -> None:
    if k <= 0:
        return
    if len(samples) < k:
        samples.append(sample)
        return
    # Replace elements with decreasing probability
    j = random.randint(0, seen - 1)
    if j < k:
        samples[j] = sample


def mine_logs(*, sys_stdin: bool, input_path: Path | None, config: MiningConfig) -> MiningResult:
    try:
        from drain3.template_miner import TemplateMiner
        from drain3.template_miner_config import TemplateMinerConfig
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency 'drain3'. Install via: pip install -r scripts/requirements.txt"
        ) from e

    drain_cfg = TemplateMinerConfig()
    if config.drain3_config_path is not None:
        drain_cfg.load(str(config.drain3_config_path))

    miner = TemplateMiner(config=drain_cfg)

    meta = MiningMeta(
        created_utc=_utc_now_iso(),
        input_path=str(input_path) if input_path else "stdin",
        input_format=config.input_format,
        group_by=config.group_by,
        extract_json_field=config.extract_json_field,
        include_fields=list(config.include_fields),
        drain3_config_path=str(config.drain3_config_path) if config.drain3_config_path else None,
    )

    stats_by_key: dict[tuple[str | None, str], TemplateStats] = {}
    template_first_seen: dict[tuple[str | None, str], str] = {}

    # Iterate records
    for rec in iter_records(sys_stdin=sys_stdin, input_path=input_path, config=config):
        meta.lines_total += 1
        if config.max_lines and meta.lines_total > config.max_lines:
            break

        service = rec.service if config.group_by == "service" else None

        mined_text = normalize_message(rec.message)
        if not mined_text:
            continue

        meta.lines_parsed += 1

        res = miner.add_log_message(mined_text)
        template = res["template_mined"]
        template_id = str(res["cluster_id"]) if res.get("cluster_id") is not None else "unknown"

        key = (service, template_id)

        if key not in stats_by_key:
            placeholders = template.count("<*>")
            stats_by_key[key] = TemplateStats(
                template_id=template_id,
                template=template,
                service=service,
                count=0,
                placeholders=placeholders,
                first_seen_line=meta.lines_total,
            )
            template_first_seen[key] = rec.raw

        ts = stats_by_key[key]
        ts.count += 1

        # Reservoir samples from raw (original) lines for investigators.
        _reservoir_add(ts.samples, rec.raw, config.per_template_samples, ts.count)

        ln = len(rec.raw)
        if ts.shortest_len is None or ln < ts.shortest_len:
            ts.shortest_len = ln
            ts.shortest_sample = rec.raw
        if ts.longest_len is None or ln > ts.longest_len:
            ts.longest_len = ln
            ts.longest_sample = rec.raw

    templates = list(stats_by_key.values())
    templates.sort(key=lambda t: t.count, reverse=True)

    services = sorted({t.service for t in templates if t.service})
    meta.services = services
    meta.templates_total = len(templates)

    rare = [t for t in templates if t.count <= config.rare_template_threshold]

    anomalies: dict[str, Any] = {
        "rare_templates": [
            {
                "service": t.service,
                "template_id": t.template_id,
                "template": t.template,
                "count": t.count,
                "first_seen_line": t.first_seen_line,
                "samples": t.samples,
            }
            for t in rare[: config.emit_rare]
        ],
        "first_seen": [
            {
                "service": t.service,
                "template_id": t.template_id,
                "template": t.template,
                "count": t.count,
                "first_seen_line": t.first_seen_line,
                "first_seen_raw": template_first_seen[(t.service, t.template_id)],
            }
            for t in templates[: min(len(templates), config.emit_top)]
            if (t.service, t.template_id) in template_first_seen
        ],
    }

    # Trim template list for report size while keeping enough for investigation.
    # Full templates are still included, but we keep the report modest.
    trimmed_templates = templates

    return MiningResult(meta=meta, templates=trimmed_templates, anomalies=anomalies)


def write_report_json(result: MiningResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _template_to_dict(t: TemplateStats) -> dict[str, Any]:
        return {
            "service": t.service,
            "template_id": t.template_id,
            "template": t.template,
            "count": t.count,
            "placeholders": t.placeholders,
            "first_seen_line": t.first_seen_line,
            "samples": t.samples,
            "shortest_len": t.shortest_len,
            "shortest_sample": t.shortest_sample,
            "longest_len": t.longest_len,
            "longest_sample": t.longest_sample,
        }

    payload = {
        "meta": {
            "created_utc": result.meta.created_utc,
            "input_path": result.meta.input_path,
            "input_format": result.meta.input_format,
            "group_by": result.meta.group_by,
            "extract_json_field": result.meta.extract_json_field,
            "include_fields": result.meta.include_fields,
            "drain3_config_path": result.meta.drain3_config_path,
            "lines_total": result.meta.lines_total,
            "lines_parsed": result.meta.lines_parsed,
            "templates_total": result.meta.templates_total,
            "services": result.meta.services,
        },
        "templates": [_template_to_dict(t) for t in result.templates],
        "anomalies": result.anomalies,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
