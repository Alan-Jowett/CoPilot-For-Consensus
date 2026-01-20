# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Human-readable reports for mined logs.

This module focuses on turning the mined JSON / MiningResult into a Markdown
summary suitable for quick anomaly triage.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .mining import MiningResult, TemplateStats


_LEVEL_RE = re.compile(r"\blevel=(?P<level>[A-Za-z]+)\b")


def load_report_json(path: Path) -> dict[str, Any]:
    """Load a previously generated JSON report."""

    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _default_keywords() -> list[str]:
    # Keep this list fairly strict to avoid drowning in expected "failed" messages.
    return [
        "unexpected error",
        "traceback",
        "exception",
        "fatal",
        "panic",
        "unhandled",
        "validation failed",
        "schema validation",
        "missed heartbeats",
    ]


def _as_report_dict(result: MiningResult) -> dict[str, Any]:
    # MiningResult contains dataclasses which can be converted via asdict.
    # This keeps markdown generation consistent with JSON output semantics.
    return {
        "meta": asdict(result.meta),
        "templates": [asdict(t) for t in result.templates],
        "anomalies": result.anomalies,
    }


def _template_level(template: str) -> str | None:
    m = _LEVEL_RE.search(template)
    if not m:
        return None
    return m.group("level").upper()


def _matches_focus(
    *,
    template: str,
    samples: Iterable[str],
    focus_levels: set[str],
    include_keywords: bool,
    keywords: list[str],
) -> bool:
    lvl = _template_level(template)
    if lvl is not None:
        return lvl in focus_levels

    if not include_keywords:
        return False

    haystacks = [template.lower()] + [s.lower() for s in samples]
    for kw in keywords:
        kw_l = kw.lower()
        if any(kw_l in h for h in haystacks):
            return True
    return False


def write_report_markdown(
    result: MiningResult,
    output_path: Path,
    *,
    focus_levels: list[str] | None = None,
    include_keywords: bool = True,
    keywords: list[str] | None = None,
    top_n: int = 30,
    per_service_n: int = 10,
    rare_threshold: int = 5,
    max_samples_per_template: int = 1,
) -> None:
    report = _as_report_dict(result)
    write_report_markdown_from_report(
        report,
        output_path,
        focus_levels=focus_levels,
        include_keywords=include_keywords,
        keywords=keywords,
        top_n=top_n,
        per_service_n=per_service_n,
        rare_threshold=rare_threshold,
        max_samples_per_template=max_samples_per_template,
    )


def write_report_markdown_from_report(
    report: dict[str, Any],
    output_path: Path,
    *,
    focus_levels: list[str] | None = None,
    include_keywords: bool = True,
    keywords: list[str] | None = None,
    top_n: int = 30,
    per_service_n: int = 10,
    rare_threshold: int = 5,
    max_samples_per_template: int = 1,
) -> None:
    """Write a human-readable Markdown summary from the JSON report structure."""

    focus_levels_set = {s.upper() for s in (focus_levels or ["ERROR", "WARNING"])}
    keywords = keywords or _default_keywords()

    templates: list[dict[str, Any]] = list(report.get("templates") or [])

    focus_templates: list[dict[str, Any]] = []
    for t in templates:
        if _matches_focus(
            template=str(t.get("template") or ""),
            samples=t.get("samples") or [],
            focus_levels=focus_levels_set,
            include_keywords=include_keywords,
            keywords=keywords,
        ):
            focus_templates.append(t)

    focus_templates.sort(key=lambda x: int(x.get("count") or 0), reverse=True)

    # Group by service for per-service summaries
    by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in focus_templates:
        svc = t.get("service") or "(unknown)"
        by_service[str(svc)].append(t)

    # Rare subset (within focus)
    rare_focus = [t for t in focus_templates if int(t.get("count") or 0) <= rare_threshold]

    meta = report.get("meta") or {}

    lines: list[str] = []
    lines.append("# Log Mining Summary (Errors & Warnings)")
    lines.append("")

    lines.append("## Meta")
    lines.append("")
    lines.append(f"- created_utc: {meta.get('created_utc')}")
    lines.append(f"- input_path: {meta.get('input_path')}")
    lines.append(f"- lines_total: {meta.get('lines_total')}")
    lines.append(f"- templates_total: {meta.get('templates_total')}")
    lines.append(f"- focus_levels: {', '.join(sorted(focus_levels_set))}")
    lines.append(f"- focus_templates: {len(focus_templates)}")
    lines.append(f"- rare_threshold: {rare_threshold}")
    lines.append("")

    lines.append("## Top Focus Templates")
    lines.append("")

    for t in focus_templates[: max(0, top_n)]:
        svc = t.get("service") or "(unknown)"
        cnt = int(t.get("count") or 0)
        tid = t.get("template_id")
        templ = str(t.get("template") or "").strip()
        lines.append(f"- **{svc}** count={cnt} id={tid}: {templ}")
        samples = list(t.get("samples") or [])
        for s in samples[: max(0, max_samples_per_template)]:
            lines.append("")
            lines.append("```")
            lines.append(str(s).rstrip())
            lines.append("```")
        lines.append("")

    lines.append("## Rare Focus Templates")
    lines.append("")

    if not rare_focus:
        lines.append("(None)")
        lines.append("")
    else:
        for t in rare_focus[:200]:
            svc = t.get("service") or "(unknown)"
            cnt = int(t.get("count") or 0)
            tid = t.get("template_id")
            templ = str(t.get("template") or "").strip()
            lines.append(f"- **{svc}** count={cnt} id={tid}: {templ}")
            samples = list(t.get("samples") or [])
            for s in samples[: max(0, max_samples_per_template)]:
                lines.append("")
                lines.append("```")
                lines.append(str(s).rstrip())
                lines.append("```")
            lines.append("")

    lines.append("## By Service")
    lines.append("")

    for svc in sorted(by_service.keys()):
        lines.append(f"### {svc}")
        lines.append("")
        items = sorted(by_service[svc], key=lambda x: int(x.get("count") or 0), reverse=True)
        for t in items[: max(0, per_service_n)]:
            cnt = int(t.get("count") or 0)
            tid = t.get("template_id")
            templ = str(t.get("template") or "").strip()
            lines.append(f"- count={cnt} id={tid}: {templ}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
