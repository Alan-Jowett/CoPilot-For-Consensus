#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Get lightweight data volume counts across stores.

Goal
----
Provide quick counts for:
- archives
- emails (stored as MongoDB collection: messages)
- chunks
- embeddings (stored in Qdrant)
- reports

Cost / RU guidance
------------------
Preferred (Azure): For Cosmos DB, this script can query Azure Monitor *metrics*
to retrieve per-collection document counts (no Cosmos RU consumption).

Fallback (direct DB): For MongoDB/CosmosDB (Mongo API), the fallback path uses the
`collStats` command to read collection metadata (including `count`) instead of
running `count_documents({})`. This avoids a full collection scan and is typically
far cheaper.

Qdrant counts are obtained via the Qdrant HTTP API (`/collections/<name>`).

Environment variables
---------------------
- MONGO_URI (default: mongodb://root:example@documentdb:27017/admin)
- MONGO_DB (default: copilot)

- QDRANT_HOST (default: vectorstore)
- QDRANT_PORT (default: 6333)
- QDRANT_COLLECTION (default: embeddings)
- QDRANT_API_KEY (optional)

- COSMOS_RESOURCE_ID (optional). If set, and mode is `auto` or `azure-metrics`,
  the script queries Azure Monitor metrics for per-collection document counts.
- COSMOS_RESOURCE_GROUP (optional). If set (or passed via --resource-group), the
    script will attempt to discover the Cosmos DB account resource ID.
- COSMOS_ACCOUNT_NAME (optional). If multiple Cosmos accounts exist in the
    resource group, provide this to select the right one.
- COSMOS_METRIC_NAME (default: DocumentCount)
- COSMOS_DIMENSION (optional; default: auto-detect)
- COSMOS_DATABASE (optional; if set, filters metric series to this DB)
- COSMOS_OFFSET (default: 6h)
- COSMOS_INTERVAL (default: 5m)

Usage
-----
PowerShell example:

    python scripts/get_data_counts.py --format table

JSON output:

    python scripts/get_data_counts.py --format json

Include additional Mongo collections:

    python scripts/get_data_counts.py --include-all

"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@documentdb:27017/admin")
DEFAULT_MONGO_DB = os.environ.get("MONGO_DB", "copilot")

DEFAULT_QDRANT_HOST = os.environ.get("QDRANT_HOST", "vectorstore")
DEFAULT_QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
DEFAULT_QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "embeddings")
DEFAULT_QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")

DEFAULT_COSMOS_RESOURCE_ID = os.environ.get("COSMOS_RESOURCE_ID")
DEFAULT_COSMOS_RESOURCE_GROUP = os.environ.get("COSMOS_RESOURCE_GROUP")
DEFAULT_COSMOS_ACCOUNT_NAME = os.environ.get("COSMOS_ACCOUNT_NAME")
DEFAULT_COSMOS_METRIC_NAME = os.environ.get("COSMOS_METRIC_NAME", "DocumentCount")
DEFAULT_COSMOS_DIMENSION = os.environ.get("COSMOS_DIMENSION")
DEFAULT_COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE")
DEFAULT_COSMOS_OFFSET = os.environ.get("COSMOS_OFFSET", "6h")
DEFAULT_COSMOS_INTERVAL = os.environ.get("COSMOS_INTERVAL", "5m")


@dataclass(frozen=True)
class CountResult:
    """A single named count."""

    name: str
    count: int | None
    source: str
    detail: str | None = None


def _format_table(rows: list[CountResult]) -> str:
    headers = ["name", "count", "source"]
    table_rows: list[list[str]] = []
    for r in rows:
        table_rows.append([r.name, "" if r.count is None else str(r.count), r.source])

    widths = [len(h) for h in headers]
    for row in table_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(r) for r in table_rows)
    return "\n".join(lines)


def _qdrant_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    # Qdrant supports API key via "api-key" header.
    # Some proxies use Bearer token; include both harmlessly.
    return {"api-key": api_key, "Authorization": f"Bearer {api_key}"}


def get_qdrant_points_count(
    *,
    host: str,
    port: int,
    collection: str,
    api_key: str | None = None,
    timeout_seconds: float = 10.0,
) -> CountResult:
    """Return the number of vectors/points in a Qdrant collection."""

    base_url = f"http://{host}:{port}"
    url = f"{base_url}/collections/{collection}"
    try:
        resp = requests.get(url, headers=_qdrant_headers(api_key), timeout=(3, timeout_seconds))
        resp.raise_for_status()
        data = resp.json()
        points = data.get("result", {}).get("points_count")
        if isinstance(points, int):
            return CountResult(name=collection, count=points, source="qdrant")
        return CountResult(
            name=collection,
            count=None,
            source="qdrant",
            detail=f"Unexpected response shape from {url}",
        )
    except Exception as exc:
        return CountResult(name=collection, count=None, source="qdrant", detail=str(exc))


def _run_az_json(args: list[str]) -> dict[str, Any]:
    """Run `az` and parse JSON output.

    This intentionally depends on `az` being available and authenticated.
    """

    az_path = shutil.which("az") or shutil.which("az.cmd") or shutil.which("az.CMD")
    if not az_path:
        raise RuntimeError("Azure CLI not found on PATH (expected 'az')")

    completed = subprocess.run(
        [az_path, *args, "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        msg = stderr or stdout or f"az exited with {completed.returncode}"
        raise RuntimeError(msg)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("az returned non-JSON output") from exc


def resolve_cosmos_resource_id_from_resource_group(
    *,
    resource_group: str,
    account_name: str | None = None,
) -> str:
    """Discover a Cosmos DB account resource ID from a resource group.

    Uses `az resource list` to find resources of type
    `Microsoft.DocumentDB/databaseAccounts`.
    """

    payload = _run_az_json(
        [
            "resource",
            "list",
            "-g",
            resource_group,
            "--resource-type",
            "Microsoft.DocumentDB/databaseAccounts",
        ]
    )

    if not isinstance(payload, list):
        raise RuntimeError("Unexpected az resource list output")

    resources: list[dict[str, Any]] = [r for r in payload if isinstance(r, dict)]
    if not resources:
        raise RuntimeError(
            f"No Cosmos DB accounts found in resource group '{resource_group}' (type Microsoft.DocumentDB/databaseAccounts)"
        )

    if account_name:
        for r in resources:
            if r.get("name") == account_name and isinstance(r.get("id"), str):
                return r["id"]
        available = ", ".join(sorted({str(r.get('name')) for r in resources if r.get("name")}))
        raise RuntimeError(
            f"Cosmos account '{account_name}' not found in resource group '{resource_group}'. Available: {available}"
        )

    if len(resources) == 1 and isinstance(resources[0].get("id"), str):
        return resources[0]["id"]

    available = ", ".join(sorted({str(r.get('name')) for r in resources if r.get("name")}))
    raise RuntimeError(
        f"Multiple Cosmos accounts found in resource group '{resource_group}'. Use --cosmos-account-name. Available: {available}"
    )


def _extract_latest_number(point: dict[str, Any]) -> int | None:
    for key in ["maximum", "average", "total", "minimum"]:
        val = point.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    return None


def parse_azure_metrics_series_counts(
    payload: dict[str, Any],
    *,
    dimension_name: str | None = None,
) -> dict[str, int]:
    """Parse `az monitor metrics list` JSON into {dimension_value: latest_count}."""

    values = payload.get("value")
    if not isinstance(values, list) or not values:
        return {}

    metric = values[0]
    timeseries = metric.get("timeseries")
    if not isinstance(timeseries, list):
        return {}

    out: dict[str, int] = {}
    wanted_dimension = dimension_name.casefold() if isinstance(dimension_name, str) else None

    for series in timeseries:
        metadata_values = series.get("metadatavalues")
        if not isinstance(metadata_values, list) or not metadata_values:
            continue

        dim_val: str | None = None
        if wanted_dimension:
            for mv in metadata_values:
                mv_name = mv.get("name", {}).get("value")
                if isinstance(mv_name, str) and mv_name.casefold() == wanted_dimension:
                    dim_val = mv.get("value")
                    break
        else:
            # Auto-detect: use the first metadata dimension value.
            dim_val = metadata_values[0].get("value")

        if not isinstance(dim_val, str) or not dim_val:
            continue

        data = series.get("data")
        if not isinstance(data, list) or not data:
            continue

        latest = None
        # Azure Monitor includes points in chronological order; take the last non-null.
        for point in reversed(data):
            if isinstance(point, dict):
                latest = _extract_latest_number(point)
                if latest is not None:
                    break

        if latest is None:
            continue

        out[dim_val] = latest

    return out


def get_cosmos_collection_doc_counts_via_metrics(
    *,
    resource_id: str,
    metric_name: str,
    dimension: str | None,
    database: str | None,
    offset: str = "6h",
    interval: str = "5m",
) -> dict[str, int]:
    """Fetch Cosmos doc counts via Azure Monitor metrics (no RU).

    Notes:
    - `metric_name` is typically `DocumentCount`.
    - `dimension` is often `CollectionName` (may vary); if not provided, this
      function will still parse output but uses the first metadata value.
    """

    args = [
        "monitor",
        "metrics",
        "list",
        "--resource",
        resource_id,
        "--metric",
        metric_name,
        "--interval",
        interval,
        "--offset",
        offset,
        "--aggregation",
        "Maximum",
    ]

    if dimension:
        args.extend(["--dimension", dimension])

    if database:
        # Cosmos metrics commonly include DatabaseName as a dimension.
        # This filter is best-effort; if the dimension doesn't exist, az will fail.
        args.extend(["--filter", f"DatabaseName eq '{database}'"])

    payload = _run_az_json(args)
    return parse_azure_metrics_series_counts(payload, dimension_name=dimension)


def get_cosmos_database_doc_counts_via_metrics(
    *,
    resource_id: str,
    metric_name: str,
    offset: str,
    interval: str,
) -> dict[str, int]:
    """Fetch Cosmos doc counts by database name via Azure Monitor metrics (no RU)."""

    return get_cosmos_collection_doc_counts_via_metrics(
        resource_id=resource_id,
        metric_name=metric_name,
        dimension="DatabaseName",
        database=None,
        offset=offset,
        interval=interval,
    )


def _get_mongo_client(mongo_uri: str):
    try:
        from pymongo import MongoClient
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pymongo is required to query MongoDB/CosmosDB") from exc

    return MongoClient(
        mongo_uri,
        directConnection=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
    )


def get_mongo_collstats_counts(
    *,
    mongo_uri: str,
    database: str,
    collections: dict[str, str],
) -> list[CountResult]:
    """Return collection counts from MongoDB using `collStats` (metadata-based)."""

    client = _get_mongo_client(mongo_uri)
    db = client[database]

    results: list[CountResult] = []

    # Trigger a ping early for clearer errors.
    try:
        client.admin.command("ping")
    except Exception as exc:
        for friendly_name in collections:
            results.append(
                CountResult(
                    name=friendly_name,
                    count=None,
                    source="mongodb",
                    detail=f"MongoDB ping failed: {exc}",
                )
            )
        return results

    for friendly_name, collection_name in collections.items():
        try:
            stats = db.command("collStats", collection_name)
            count = stats.get("count")
            if isinstance(count, int):
                results.append(CountResult(name=friendly_name, count=count, source="mongodb"))
            else:
                results.append(
                    CountResult(
                        name=friendly_name,
                        count=None,
                        source="mongodb",
                        detail=f"Missing 'count' in collStats for {collection_name}",
                    )
                )
        except Exception as exc:
            results.append(
                CountResult(
                    name=friendly_name,
                    count=None,
                    source="mongodb",
                    detail=str(exc),
                )
            )

    return results


def build_default_mongo_collection_map(*, include_all: bool) -> dict[str, str]:
    """Build a friendly-name to collection-name mapping."""

    base: dict[str, str] = {
        "archives": "archives",
        "emails": "messages",
        "chunks": "chunks",
        "reports": "reports",
    }

    if include_all:
        base.update(
            {
                "threads": "threads",
                "summaries": "summaries",
                "sources": "sources",
            }
        )

    return base


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get cheap counts of stored entities (MongoDB + Qdrant).")

    parser.add_argument("--mongo-uri", default=DEFAULT_MONGO_URI)
    parser.add_argument("--mongo-db", default=DEFAULT_MONGO_DB)

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any count cannot be computed.",
    )

    parser.add_argument(
        "--mode",
        choices=["auto", "azure-metrics", "mongodb"],
        default="auto",
        help="How to get document counts for archives/emails/chunks/reports.",
    )

    parser.add_argument("--cosmos-resource-id", default=DEFAULT_COSMOS_RESOURCE_ID)
    parser.add_argument(
        "--resource-group",
        default=DEFAULT_COSMOS_RESOURCE_GROUP,
        help="Azure resource group containing the Cosmos DB account (used to auto-discover --cosmos-resource-id).",
    )
    parser.add_argument(
        "--cosmos-account-name",
        default=DEFAULT_COSMOS_ACCOUNT_NAME,
        help="Cosmos DB account name (required if multiple accounts exist in the resource group).",
    )
    parser.add_argument("--cosmos-metric-name", default=DEFAULT_COSMOS_METRIC_NAME)
    parser.add_argument(
        "--cosmos-dimension",
        default=DEFAULT_COSMOS_DIMENSION,
        help="Dimension name for collection/container (commonly 'CollectionName').",
    )
    parser.add_argument(
        "--cosmos-database",
        default=DEFAULT_COSMOS_DATABASE,
        help="Optional Cosmos DB name filter (dimension 'DatabaseName').",
    )

    parser.add_argument(
        "--cosmos-offset",
        default=DEFAULT_COSMOS_OFFSET,
        help="How far back to query metrics (Azure CLI --offset). Examples: '1h', '6h', '1d'.",
    )
    parser.add_argument(
        "--cosmos-interval",
        default=DEFAULT_COSMOS_INTERVAL,
        help="Metrics aggregation interval (Azure CLI --interval). Examples: '1m', '5m', '1h'.",
    )

    parser.add_argument(
        "--no-cosmos-db-total",
        dest="include_cosmos_db_total",
        action="store_false",
        help="Do not include the 'documents_total' row from Cosmos metrics (DatabaseName dimension).",
    )

    parser.set_defaults(include_cosmos_db_total=True)

    parser.add_argument("--qdrant-host", default=DEFAULT_QDRANT_HOST)
    parser.add_argument("--qdrant-port", type=int, default=DEFAULT_QDRANT_PORT)
    parser.add_argument("--qdrant-collection", default=DEFAULT_QDRANT_COLLECTION)
    parser.add_argument("--qdrant-api-key", default=DEFAULT_QDRANT_API_KEY)

    parser.add_argument("--include-all", action="store_true", help="Also include threads/summaries/sources.")

    parser.add_argument("--format", choices=["table", "json"], default="table")

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    mongo_map = build_default_mongo_collection_map(include_all=bool(args.include_all))

    mongo_results: list[CountResult]

    cosmos_resource_id = args.cosmos_resource_id
    if not cosmos_resource_id and args.resource_group:
        try:
            cosmos_resource_id = resolve_cosmos_resource_id_from_resource_group(
                resource_group=args.resource_group,
                account_name=args.cosmos_account_name,
            )
        except Exception:
            # Resolution failures are handled below depending on mode.
            cosmos_resource_id = None

    use_metrics = args.mode == "azure-metrics" or (args.mode == "auto" and bool(cosmos_resource_id))

    if use_metrics:
        try:
            if not cosmos_resource_id:
                raise RuntimeError(
                    "Cosmos resource id is required for azure-metrics mode. Provide --cosmos-resource-id or --resource-group."
                )
            series = get_cosmos_collection_doc_counts_via_metrics(
                resource_id=cosmos_resource_id,
                metric_name=args.cosmos_metric_name,
                dimension=args.cosmos_dimension,
                database=args.cosmos_database,
                offset=args.cosmos_offset,
                interval=args.cosmos_interval,
            )
            mongo_results = []
            for friendly_name, collection_name in mongo_map.items():
                value = series.get(collection_name)
                mongo_results.append(
                    CountResult(
                        name=friendly_name,
                        count=value,
                        source="azure-monitor-metrics",
                        detail=None if value is not None else "No timeseries for collection/container",
                    )
                )

            if args.include_cosmos_db_total:
                db_series = get_cosmos_database_doc_counts_via_metrics(
                    resource_id=cosmos_resource_id,
                    metric_name=args.cosmos_metric_name,
                    offset=args.cosmos_offset,
                    interval=args.cosmos_interval,
                )
                db_name = args.mongo_db
                mongo_results.append(
                    CountResult(
                        name="documents_total",
                        count=db_series.get(db_name),
                        source="azure-monitor-metrics",
                        detail=None if db_series.get(db_name) is not None else f"No timeseries for DatabaseName={db_name}",
                    )
                )
        except Exception as exc:
            # In auto mode, fall back to direct DB. In azure-metrics mode, surface failure.
            if args.mode == "azure-metrics":
                mongo_results = [
                    CountResult(
                        name=k,
                        count=None,
                        source="azure-monitor-metrics",
                        detail=str(exc),
                    )
                    for k in mongo_map
                ]
            else:
                mongo_results = get_mongo_collstats_counts(
                    mongo_uri=args.mongo_uri,
                    database=args.mongo_db,
                    collections=mongo_map,
                )
    else:
        mongo_results = get_mongo_collstats_counts(
            mongo_uri=args.mongo_uri,
            database=args.mongo_db,
            collections=mongo_map,
        )

    qdrant_result = get_qdrant_points_count(
        host=args.qdrant_host,
        port=args.qdrant_port,
        collection=args.qdrant_collection,
        api_key=args.qdrant_api_key,
    )

    all_results = [*mongo_results, qdrant_result]

    if args.format == "json":
        payload: dict[str, Any] = {
            "counts": {r.name: r.count for r in all_results},
            "details": {r.name: r.detail for r in all_results if r.detail},
            "sources": {r.name: r.source for r in all_results},
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(_format_table(all_results))
    sys.stdout.write("\n")

    any_missing = any(r.count is None for r in all_results)
    any_present = any(r.count is not None for r in all_results)

    # By default, succeed if we computed at least one count.
    if args.strict:
        return 2 if any_missing else 0

    return 0 if any_present else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
