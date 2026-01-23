# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Log template mining + anomaly-focused sampling.

This module is intentionally streaming-friendly (large input files).
"""

from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MiningConfig:
    input_format: str = "auto"  # auto|plain|docker|azure-console|azure-law|azure-diagnostics
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


# ISO 8601 timestamp pattern. Allows both 'T' and ' ' separators for compatibility.
# Optional 'Z' suffix and fractional seconds for flexibility across log formats.
_ISO_TS_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"
)
_GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# IP regex intentionally over-matches (e.g. 999.999.999.999) for log normalization safety.
# For template mining, over-matching is safer than under-matching.
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
    try:
        # json.loads() requires full JSON. For auto-detection we often only have a
        # prefix (e.g. first N bytes of a large file), so decode a single JSON value
        # and ignore any trailing content.
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(value)
        return obj
    except json.JSONDecodeError:
        return None


def _dict_get_case_insensitive(payload_obj: dict[str, Any], key: str) -> Any | None:
    if key in payload_obj:
        return payload_obj[key]

    key_lower = key.lower()
    for k, v in payload_obj.items():
        if isinstance(k, str) and k.lower() == key_lower:
            return v

    return None


def _extract_from_payload_json(
    payload_obj: dict[str, Any],
    *,
    extract_field: str,
    include_fields: list[str],
) -> str:
    prefix_parts: list[str] = []
    for f in include_fields:
        v = _dict_get_case_insensitive(payload_obj, f)
        if v is None:
            continue
        prefix_parts.append(f"{f}={v}")

    msg = _dict_get_case_insensitive(payload_obj, extract_field)
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

            row_dict = dict(zip(column_names, row, strict=True))
            yield from _iter_azure_console_records_from_obj(row_dict, config)


def _iter_azure_diagnostics_records_from_obj(
    obj: Any,
    config: MiningConfig,
) -> Iterator[ParsedRecord]:
    """Iterate Azure diagnostic settings exports (NDJSON or JSON arrays).

    This is the log shape produced when archiving Container Apps logs to Blob Storage
    via Diagnostic Settings (commonly stored as NDJSON files).
    """

    items: list[Any] = []
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        items = [obj]

    for row in items:
        if not isinstance(row, dict):
            continue

        # Azure Monitor diagnostic archives for Container Apps often wrap the
        # interesting fields under `properties`.
        props = row.get("properties")
        lookup_row: dict[str, Any] = row
        if isinstance(props, dict):
            # Prefer `properties.*` for container/app fields and message, but
            # keep top-level metadata in case investigators include it.
            lookup_row = dict(row)
            lookup_row.update(props)

        service = (
            _dict_get_case_insensitive(lookup_row, "ContainerAppName")
            or _dict_get_case_insensitive(lookup_row, "ContainerName")
            or _dict_get_case_insensitive(lookup_row, "ContainerAppName_s")
            or _dict_get_case_insensitive(lookup_row, "ContainerName_s")
            or lookup_row.get("container")
        )

        extract_field = config.extract_json_field
        if _dict_get_case_insensitive(lookup_row, extract_field) is None:
            # Diagnostic Settings uses `Message` (not `message`). Prefer it when present.
            if _dict_get_case_insensitive(lookup_row, "Message") is not None:
                extract_field = "Message"
            elif _dict_get_case_insensitive(lookup_row, "Log") is not None:
                # Container Apps console/system logs commonly use `Log` under properties.
                extract_field = "Log"
            elif _dict_get_case_insensitive(lookup_row, "Log_s") is not None:
                extract_field = "Log_s"

        msg_val = _dict_get_case_insensitive(lookup_row, extract_field)
        if msg_val is None or msg_val == "":
            continue

        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"))

        # If Message itself is a JSON payload string, enrich it with include_fields.
        if isinstance(msg_val, str):
            payload_obj = _safe_json_loads(msg_val)
            if isinstance(payload_obj, dict):
                msg = _extract_from_payload_json(
                    payload_obj,
                    extract_field=config.extract_json_field,
                    include_fields=config.include_fields,
                )
            else:
                msg = _extract_from_payload_json(
                    lookup_row,
                    extract_field=extract_field,
                    include_fields=config.include_fields,
                )
        else:
            msg = _extract_from_payload_json(
                lookup_row,
                extract_field=extract_field,
                include_fields=config.include_fields,
            )

        yield ParsedRecord(service=str(service) if service else None, message=msg, raw=raw)


def _load_json_file_best_effort(path: Path) -> Any:
    # Best-effort load for azure console exports.
    # Use json.load on a file object to avoid an extra full-file string copy in memory.
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


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

    if config.input_format in {"azure-diagnostics"}:
        if sys_stdin:
            # NDJSON mode: each line is a diagnostic record object
            for line in sys.stdin:
                row = _safe_json_loads(line)
                if row is None:
                    continue
                yield from _iter_azure_diagnostics_records_from_obj(row, config)
        else:
            assert input_path is not None
            try:
                obj = _load_json_file_best_effort(input_path)
                yield from _iter_azure_diagnostics_records_from_obj(obj, config)
            except json.JSONDecodeError:
                # Not a single JSON document (likely NDJSON); stream line-by-line.
                with input_path.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        row = _safe_json_loads(line)
                        if row is None:
                            continue
                        yield from _iter_azure_diagnostics_records_from_obj(row, config)
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
        except (OSError, UnicodeError):
            head_obj = None

        if isinstance(head_obj, dict) and ("tables" in head_obj or "Tables" in head_obj):
            new_config = replace(config, input_format="azure-law")
        elif isinstance(head_obj, dict) and (
            _dict_get_case_insensitive(head_obj, "TimeGenerated") is not None
            or _dict_get_case_insensitive(head_obj, "Category") is not None
            or _dict_get_case_insensitive(head_obj, "Message") is not None
        ):
            new_config = replace(config, input_format="azure-diagnostics")
        elif isinstance(head_obj, list) and head_obj and isinstance(head_obj[0], dict) and (
            _dict_get_case_insensitive(head_obj[0], "TimeGenerated") is not None
            or _dict_get_case_insensitive(head_obj[0], "Category") is not None
            or _dict_get_case_insensitive(head_obj[0], "Message") is not None
        ):
            new_config = replace(config, input_format="azure-diagnostics")
        else:
            new_config = replace(config, input_format="azure-console")

        yield from iter_records(sys_stdin=False, input_path=input_path, config=new_config)
    else:
        # Assume docker compose logs
        new_config = replace(config, input_format="docker")
        yield from iter_records(sys_stdin=False, input_path=input_path, config=new_config)


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
    except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover
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
