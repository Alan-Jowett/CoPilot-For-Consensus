# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Export data from a CoPilot-for-Consensus document store.

Supports Azure Cosmos DB (SQL API) and MongoDB as sources.
Writes NDJSON files suitable for data-migration-import.py.

Usage:
    # From Azure Cosmos DB (connection string)
    python scripts/data-migration-export.py --source-type cosmos \
        --cosmos-endpoint https://account.documents.azure.com:443/ \
        --cosmos-key "<key>"

    # From Azure Cosmos DB (RBAC / DefaultAzureCredential)
    python scripts/data-migration-export.py --source-type cosmos \
        --cosmos-endpoint https://account.documents.azure.com:443/ \
        --use-rbac

    # From MongoDB (Docker Compose)
    python scripts/data-migration-export.py --source-type mongodb \
        --mongo-uri "mongodb://user:pass@localhost:27017/?authSource=admin"

    # Specific collections only
    python scripts/data-migration-export.py --source-type cosmos \
        --cosmos-endpoint ... --cosmos-key ... \
        --collections sources,archives
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Database → collection mapping (mirrors collections.config.json + auth)
DATABASE_COLLECTIONS = {
    "copilot": ["sources", "archives", "messages", "threads", "chunks", "summaries"],
    "auth": ["user_roles"],
}


def export_cosmos(endpoint: str, key: str | None, use_rbac: bool,
                  databases: dict[str, list[str]], output_dir: Path) -> dict[str, int]:
    """Export from Azure Cosmos DB SQL API."""
    from azure.cosmos import CosmosClient

    if use_rbac:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        client = CosmosClient(endpoint, credential=credential)
        print(f"  Auth: Azure AD / RBAC (DefaultAzureCredential)")
    else:
        if not key:
            raise ValueError("Cosmos DB key is required when not using RBAC")
        client = CosmosClient(endpoint, credential=key)
        print(f"  Auth: Connection string (account key)")

    counts: dict[str, int] = {}

    for db_name, collections in databases.items():
        try:
            database = client.get_database_client(db_name)
        except Exception as e:
            print(f"  WARNING: Could not access database '{db_name}': {e}")
            continue

        for collection in collections:
            key_label = f"{db_name}.{collection}"
            out_file = output_dir / db_name / f"{collection}.json"

            print(f"  Exporting {key_label} ... ", end="", flush=True)
            try:
                container = database.get_container_client(collection)
                items = list(container.query_items(
                    query="SELECT * FROM c",
                    enable_cross_partition_query=True,
                ))

                # Write NDJSON (one JSON object per line)
                with open(out_file, "w", encoding="utf-8") as f:
                    for item in items:
                        # Remove Cosmos system properties
                        for sys_key in ("_rid", "_self", "_etag", "_attachments", "_ts"):
                            item.pop(sys_key, None)
                        f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

                counts[key_label] = len(items)
                print(f"{len(items)} documents")
            except Exception as e:
                print(f"FAILED: {e}")
                counts[key_label] = -1

    return counts


def export_mongodb(uri: str, databases: dict[str, list[str]], output_dir: Path) -> dict[str, int]:
    """Export from MongoDB using pymongo."""
    try:
        import pymongo
    except ImportError:
        print("ERROR: pymongo is required for MongoDB export. Install with: pip install pymongo")
        sys.exit(1)

    client = pymongo.MongoClient(uri)
    counts: dict[str, int] = {}

    for db_name, collections in databases.items():
        database = client[db_name]

        for collection in collections:
            key_label = f"{db_name}.{collection}"
            out_file = output_dir / db_name / f"{collection}.json"

            print(f"  Exporting {key_label} ... ", end="", flush=True)
            try:
                coll = database[collection]
                items = list(coll.find({}))

                with open(out_file, "w", encoding="utf-8") as f:
                    for item in items:
                        # Convert ObjectId to string
                        if "_id" in item:
                            item["_id"] = str(item["_id"])
                        f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

                counts[key_label] = len(items)
                print(f"{len(items)} documents")
            except Exception as e:
                print(f"FAILED: {e}")
                counts[key_label] = -1

    client.close()
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Export data from a CoPilot-for-Consensus deployment."
    )
    parser.add_argument("--source-type", required=True, choices=["cosmos", "mongodb"],
                        help="Source database type")
    parser.add_argument("--cosmos-endpoint", help="Azure Cosmos DB endpoint URL")
    parser.add_argument("--cosmos-key", help="Azure Cosmos DB account key")
    parser.add_argument("--use-rbac", action="store_true",
                        help="Use Azure AD / RBAC auth (DefaultAzureCredential)")
    parser.add_argument("--mongo-uri", help="MongoDB connection URI")
    parser.add_argument("--collections", help="Comma-separated list of collections to export")
    parser.add_argument("--output-dir", help="Output directory (default: data-export-<timestamp>)")

    args = parser.parse_args()

    # Resolve defaults from environment
    if args.source_type == "cosmos":
        if not args.cosmos_endpoint:
            args.cosmos_endpoint = os.environ.get("SRC_COSMOS_ENDPOINT") or os.environ.get("COSMOS_ENDPOINT")
        if not args.cosmos_key and not args.use_rbac:
            args.cosmos_key = os.environ.get("SRC_COSMOS_KEY") or os.environ.get("COSMOS_KEY")
        if not args.cosmos_endpoint:
            parser.error("--cosmos-endpoint is required for Cosmos DB export (or set SRC_COSMOS_ENDPOINT)")
        if not args.cosmos_key and not args.use_rbac:
            parser.error("--cosmos-key or --use-rbac is required for Cosmos DB export")
    elif args.source_type == "mongodb":
        if not args.mongo_uri:
            args.mongo_uri = os.environ.get("SRC_MONGO_URI") or "mongodb://localhost:27017/"

    # Filter collections
    databases = {db: list(colls) for db, colls in DATABASE_COLLECTIONS.items()}
    if args.collections:
        requested = [c.strip() for c in args.collections.split(",")]
        databases = {
            db: [c for c in colls if c in requested]
            for db, colls in databases.items()
        }
        databases = {db: colls for db, colls in databases.items() if colls}

    # Output directory
    if not args.output_dir:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        args.output_dir = f"data-export-{timestamp}"
    output_dir = Path(args.output_dir)

    # Create directory structure
    for db_name in databases:
        (output_dir / db_name).mkdir(parents=True, exist_ok=True)

    print()
    print("=== CoPilot-for-Consensus Data Export ===")
    print(f"  Source: {args.source_type}")
    print(f"  Output: {output_dir}")
    print()

    start = time.time()

    if args.source_type == "cosmos":
        counts = export_cosmos(
            args.cosmos_endpoint, args.cosmos_key, args.use_rbac,
            databases, output_dir,
        )
    else:
        counts = export_mongodb(args.mongo_uri, databases, output_dir)

    elapsed = time.time() - start

    # Write manifest
    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_type": args.source_type,
        "source_endpoint": args.cosmos_endpoint if args.source_type == "cosmos" else args.mongo_uri,
        "databases": {db: list(colls) for db, colls in databases.items()},
        "document_counts": counts,
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    total = sum(v for v in counts.values() if v > 0)
    errors = sum(1 for v in counts.values() if v < 0)

    print()
    print("=== Export Complete ===")
    print(f"  Total documents: {total:,}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Output: {output_dir}")
    if errors:
        print(f"  Errors: {errors} collection(s) failed")
    print()
    print("To import this data:")
    print(f'  python scripts/data-migration-import.py --dest-type <cosmos|mongodb> --export-dir "{output_dir}"')


if __name__ == "__main__":
    main()
