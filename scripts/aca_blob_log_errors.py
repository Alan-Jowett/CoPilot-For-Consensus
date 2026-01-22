# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Extract "error-ish" Azure Container Apps logs archived to Blob Storage.

This script is intended for deployments where the Container Apps *environment*
exports logs via Azure Monitor diagnostic settings to a Storage Account.

It:
- Discovers Container Apps managed environment(s) in a resource group
- Finds diagnostic settings that archive to a Storage Account
- Downloads the latest archived blobs from the Azure Monitor containers
  (e.g. insights-logs-containerappconsolelogs)
- Parses the NDJSON content and extracts "error-ish" records for any services
  (Container Apps) in the resource group

Auth:
- Uses Azure CLI + Entra auth (`--auth-mode login`) for Storage.
- Requires you to have a data-plane role on the Storage Account, e.g.
  "Storage Blob Data Reader".

Example:
  python scripts/aca_blob_log_errors.py --resource-group copilot-app-rg

"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


AZ_BIN = "az"

CONTAINERS = (
    "insights-logs-containerappconsolelogs",
    "insights-logs-containerappsystemlogs",
)


class AzCliError(RuntimeError):
    """Raised when an Azure CLI invocation fails."""


def _run_az_json(args: Sequence[str]) -> Any:
    completed = subprocess.run(
        [AZ_BIN, *args, "-o", "json"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AzCliError(
            "Azure CLI call failed:\n"
            f"  az {' '.join(args)} -o json\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AzCliError(
            "Azure CLI returned non-JSON output:\n"
            f"  az {' '.join(args)} -o json\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        ) from exc


def _run_az(args: Sequence[str]) -> None:
    completed = subprocess.run([AZ_BIN, *args], capture_output=True, text=True)
    if completed.returncode != 0:
        raise AzCliError(
            "Azure CLI call failed:\n"
            f"  az {' '.join(args)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _parse_resource_name_from_id(resource_id: str) -> str:
    # .../storageAccounts/<name>
    parts = resource_id.strip("/").split("/")
    if len(parts) < 2:
        return resource_id
    return parts[-1]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class LogBlobRef:
    storage_account: str
    container: str
    name: str
    last_modified: str
    size: int


def _discover_managed_env_ids(resource_group: str) -> List[str]:
    envs = _run_az_json(
        [
            "resource",
            "list",
            "-g",
            resource_group,
            "--resource-type",
            "Microsoft.App/managedEnvironments",
        ]
    )
    return [e["id"] for e in envs if isinstance(e, dict) and e.get("id")]


def _discover_container_apps(resource_group: str) -> List[str]:
    apps = _run_az_json(["containerapp", "list", "-g", resource_group])
    names: List[str] = []
    for a in apps:
        if isinstance(a, dict) and a.get("name"):
            names.append(a["name"])
    return sorted(set(names))


def _discover_storage_accounts_from_env_diagnostics(env_id: str) -> List[str]:
    settings = _run_az_json(["monitor", "diagnostic-settings", "list", "--resource", env_id])
    storage_accounts: List[str] = []
    for s in settings:
        if not isinstance(s, dict):
            continue
        sa_id = s.get("storageAccountId")
        if isinstance(sa_id, str) and sa_id:
            storage_accounts.append(_parse_resource_name_from_id(sa_id))
    return sorted(set(storage_accounts))


def _list_latest_blobs(
    storage_account: str,
    container: str,
    max_blobs: int,
) -> List[LogBlobRef]:
    blobs = _run_az_json(
        [
            "storage",
            "blob",
            "list",
            "--account-name",
            storage_account,
            "--auth-mode",
            "login",
            "--container-name",
            container,
        ]
    )

    refs: List[LogBlobRef] = []
    for b in blobs:
        if not isinstance(b, dict):
            continue
        props = b.get("properties") or {}
        last_modified = props.get("lastModified")
        size = props.get("contentLength")
        name = b.get("name")
        if not (isinstance(last_modified, str) and isinstance(size, int) and isinstance(name, str)):
            continue
        refs.append(
            LogBlobRef(
                storage_account=storage_account,
                container=container,
                name=name,
                last_modified=last_modified,
                size=size,
            )
        )

    refs.sort(key=lambda r: r.last_modified)
    return refs[-max_blobs:] if max_blobs > 0 else []


def _download_blob(ref: LogBlobRef, output_path: Path) -> None:
    _ensure_dir(output_path.parent)
    _run_az(
        [
            "storage",
            "blob",
            "download",
            "--account-name",
            ref.storage_account,
            "--auth-mode",
            "login",
            "--container-name",
            ref.container,
            "--name",
            ref.name,
            "--file",
            str(output_path),
            "--only-show-errors",
        ]
    )


def _iter_ndjson(path: Path) -> Iterable[Dict[str, Any]]:
    # Azure Monitor exports here are AppendBlob with NDJSON
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                # Not NDJSON or corrupted line; stop to avoid spam.
                return
            if isinstance(rec, dict):
                yield rec


def _get_message(rec: Dict[str, Any]) -> Optional[str]:
    for key in ("message", "msg", "log", "Log", "Message", "RenderedMessage"):
        value = rec.get(key)
        if isinstance(value, str) and value.strip():
            return value
    props = rec.get("properties")
    if isinstance(props, dict):
        for key in ("message", "msg", "log", "Log", "RenderedMessage"):
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _get_ts(rec: Dict[str, Any]) -> Optional[str]:
    for key in ("time", "TimeGenerated", "timeGenerated", "timestamp", "TIMESTAMP", "TimeGeneratedUtc"):
        value = rec.get(key)
        if value:
            return str(value)
    props = rec.get("properties")
    if isinstance(props, dict):
        for key in ("time", "TimeGenerated", "timeGenerated", "timestamp"):
            value = props.get(key)
            if value:
                return str(value)
    return None


def _get_level(rec: Dict[str, Any], msg: Optional[str]) -> str:
    for key in ("level", "Level", "severity", "Severity", "severityLevel"):
        value = rec.get(key)
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, int):
            return "error" if value >= 3 else "info"
    props = rec.get("properties")
    if isinstance(props, dict):
        for key in ("level", "Level", "severity", "Severity"):
            value = props.get(key)
            if isinstance(value, str):
                return value.lower()
    if not msg:
        return "unknown"
    low = msg.lower()
    if "traceback" in low or "exception" in low:
        return "error"
    if low.startswith("error") or "\"level\":\"error\"" in low:
        return "error"
    if "warn" in low:
        return "warning"
    return "info"


_REDACTIONS: List[Tuple[re.Pattern[str], str]] = [
    # Bearer tokens
    (re.compile(r"(Authorization\s*[:=]\s*Bearer\s+)[^\s\"']+", re.IGNORECASE), r"\1<REDACTED>"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-_.]+"), r"\1<REDACTED>"),
    # App Insights connection strings
    (re.compile(r"(InstrumentationKey=)[^;\s]+", re.IGNORECASE), r"\1<REDACTED>"),
    (re.compile(r"(IngestionEndpoint=)[^;\s]+", re.IGNORECASE), r"\1<REDACTED>"),
    (re.compile(r"(Authorization=)[^;\s]+", re.IGNORECASE), r"\1<REDACTED>"),
    # Common key/value secrets
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*[^\s\"']+"), r"\1=<REDACTED>"),
    # Key Vault secret URIs
    (
        re.compile(r"https://[a-z0-9\-]+\.vault\.azure\.net/secrets/[^\s\"']+", re.IGNORECASE),
        r"<REDACTED_KV_SECRET_URI>",
    ),
]


def _redact(text: str) -> str:
    out = text
    for rx, repl in _REDACTIONS:
        out = rx.sub(repl, out)
    return out


def _service_from_record(rec: Dict[str, Any], msg: Optional[str], service_regex: re.Pattern[str]) -> Optional[str]:
    # Prefer structured fields when present
    for key in ("containerAppName", "ContainerAppName", "appName", "AppName"):
        value = rec.get(key)
        if isinstance(value, str) and value:
            return value
    props = rec.get("properties")
    if isinstance(props, dict):
        for key in ("containerAppName", "ContainerAppName", "appName", "AppName"):
            value = props.get(key)
            if isinstance(value, str) and value:
                return value

    if msg:
        match = service_regex.search(msg)
        if match:
            return match.group(0)

    try:
        dumped = json.dumps(rec, ensure_ascii=False)
    except Exception:
        return None
    match = service_regex.search(dumped)
    return match.group(0) if match else None


def _is_errorish(rec: Dict[str, Any], msg: Optional[str]) -> bool:
    level = _get_level(rec, msg)
    if level in ("error", "fatal", "critical"):
        return True

    if not msg:
        return False

    low = msg.lower()
    return any(k in low for k in (" error", "exception", "traceback", "fatal", "crash"))


def _build_service_regex(services: Sequence[str]) -> re.Pattern[str]:
    # Small list (~10-50); safe to use alternation.
    escaped = [re.escape(s) for s in sorted(set(services), key=len, reverse=True)]
    if not escaped:
        return re.compile(r"$")
    return re.compile(r"(?:" + "|".join(escaped) + r")")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract error-ish ACA log records from Azure Monitor blob export for all services in a resource group."
    )
    parser.add_argument(
        "--resource-group",
        required=True,
        help="Azure resource group containing Container Apps and the managed environment diagnostic settings.",
    )
    parser.add_argument(
        "--max-blobs",
        type=int,
        default=1,
        help="How many of the latest blobs to scan per log container (default: 1).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory. If omitted, uses a temp directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per error record to stdout.",
    )
    parser.add_argument(
        "--include-samples",
        action="store_true",
        help="Include a short redacted message sample per record (default: off).",
    )

    args = parser.parse_args(argv)

    resource_group: str = args.resource_group

    # Discover scope
    env_ids = _discover_managed_env_ids(resource_group)
    if not env_ids:
        print(f"No Container Apps managed environments found in resource group '{resource_group}'.", file=sys.stderr)
        return 2

    services = _discover_container_apps(resource_group)
    if not services:
        print(f"No Container Apps found in resource group '{resource_group}'.", file=sys.stderr)
        return 2

    service_regex = _build_service_regex(services)

    # Discover storage accounts used by env diagnostics
    storage_accounts: List[str] = []
    for env_id in env_ids:
        storage_accounts.extend(_discover_storage_accounts_from_env_diagnostics(env_id))
    storage_accounts = sorted(set(storage_accounts))

    if not storage_accounts:
        print(
            "No environment diagnostic settings with storageAccountId were found.\n"
            "Ensure the managed environment has a diagnostic setting archiving logs to Storage.",
            file=sys.stderr,
        )
        return 2

    timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) if args.out else Path(os.getenv("TEMP", ".")) / "aca-blob-errors" / timestamp
    _ensure_dir(out_dir)

    # We may have multiple storage accounts; try them in order.
    blob_refs: List[LogBlobRef] = []
    chosen_sa: Optional[str] = None
    for sa in storage_accounts:
        try:
            refs: List[LogBlobRef] = []
            for container in CONTAINERS:
                refs.extend(_list_latest_blobs(sa, container, max_blobs=max(0, args.max_blobs)))
            if refs:
                blob_refs = refs
                chosen_sa = sa
                break
        except AzCliError as exc:
            # Keep going; next storage account might be accessible.
            last_err = str(exc)
            continue

    if not blob_refs or not chosen_sa:
        print(
            "Unable to list/download blobs via --auth-mode login.\n"
            "You likely need a data-plane role on the Storage Account, e.g. 'Storage Blob Data Reader'.\n"
            "Try:\n"
            "  az role assignment create --assignee <your-object-id> --role \"Storage Blob Data Reader\" --scope <storage-account-resource-id>\n",
            file=sys.stderr,
        )
        return 3

    # Download and scan
    per_service_counts: Dict[str, int] = {s: 0 for s in services}
    total_errorish = 0

    for ref in blob_refs:
        local_name = f"{_safe_filename(ref.container)}__{_safe_filename(Path(ref.name).name)}"
        local_path = out_dir / local_name
        _download_blob(ref, local_path)

        for rec in _iter_ndjson(local_path):
            msg = _get_message(rec)
            service = _service_from_record(rec, msg, service_regex)
            if not service:
                continue
            if not _is_errorish(rec, msg):
                continue

            total_errorish += 1
            per_service_counts[service] = per_service_counts.get(service, 0) + 1

            if args.json:
                out: Dict[str, Any] = {
                    "resourceGroup": resource_group,
                    "storageAccount": chosen_sa,
                    "container": ref.container,
                    "blob": ref.name,
                    "service": service,
                    "time": _get_ts(rec),
                    "level": _get_level(rec, msg),
                }
                if args.include_samples:
                    out["message"] = _redact(msg or "")[:500]
                print(json.dumps(out, ensure_ascii=False))

    # Summary
    print("\nSummary:")
    print(f"- resourceGroup: {resource_group}")
    print(f"- storageAccount: {chosen_sa}")
    print(f"- servicesFound: {len(services)}")
    print(f"- blobsScanned: {len(blob_refs)} ({', '.join(sorted(set(r.container for r in blob_refs)))})")
    print(f"- totalErrorishRecords: {total_errorish}")

    top = sorted(per_service_counts.items(), key=lambda kv: kv[1], reverse=True)
    for svc, count in top:
        if count:
            print(f"- {svc}: {count}")

    print(f"\nOutput directory: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
