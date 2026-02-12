# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Import data into a CoPilot-for-Consensus document store.

Supports Azure Cosmos DB (SQL API) and MongoDB as destinations.
Reads NDJSON files produced by data-migration-export.py.

Usage:
    # Into Azure Cosmos DB (connection string)
    python scripts/data-migration-import.py --dest-type cosmos \
        --cosmos-endpoint https://account.documents.azure.com:443/ \
        --cosmos-key "<key>" \
        --export-dir data-export-20260212T170000

    # Into Azure Cosmos DB (RBAC / DefaultAzureCredential)
    python scripts/data-migration-import.py --dest-type cosmos \
        --cosmos-endpoint https://account.documents.azure.com:443/ \
        --use-rbac \
        --export-dir data-export-20260212T170000

    # Into MongoDB (Docker Compose)
    python scripts/data-migration-import.py --dest-type mongodb \
        --mongo-uri "mongodb://user:pass@localhost:27017/?authSource=admin" \
        --export-dir data-export-20260212T170000
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0

# Partition key paths per container (must match infra/azure/modules/cosmos.bicep).
# The Bicep deploys both a shared "documents" container (partition key /collection)
# and individual per-collection containers (partition key /id).
# The application uses the per-collection containers for data storage.
COSMOS_PARTITION_KEYS = {
    # Shared container (may exist but typically unused by the application)
    "documents": "/collection",
    # copilot database — per-collection containers
    "sources": "/id",
    "archives": "/id",
    "messages": "/id",
    "threads": "/id",
    "chunks": "/id",
    "summaries": "/id",
    "reports": "/id",
    # auth database
    "user_roles": "/id",
}


def iter_ndjson(file_path: Path):
    """Iterate over an NDJSON file, yielding one parsed dict per line."""
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def count_ndjson_lines(file_path: Path) -> int:
    """Count non-empty lines in an NDJSON file without loading into memory."""
    count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def import_cosmos(endpoint: str, key: str | None, use_rbac: bool,
                  export_dir: Path, databases: dict[str, list[str]],
                  mode: str, batch_size: int) -> dict[str, int]:
    """Import into Azure Cosmos DB SQL API."""
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceExistsError

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
        # Create database if needed
        try:
            database = client.create_database_if_not_exists(db_name)
        except Exception as e:
            print(f"  WARNING: Could not create/access database '{db_name}': {e}")
            continue

        for collection in collections:
            key_label = f"{db_name}.{collection}"
            in_file = export_dir / db_name / f"{collection}.json"

            if not in_file.exists():
                print(f"  SKIP {key_label} (file not found)")
                continue

            doc_count = count_ndjson_lines(in_file)
            if doc_count == 0:
                print(f"  SKIP {key_label} (empty)")
                continue

            print(f"  Importing {key_label} ({doc_count:,} docs) ... ", end="", flush=True)

            # Create container if needed
            partition_key_path = COSMOS_PARTITION_KEYS.get(collection, "/id")
            try:
                container = database.create_container_if_not_exists(
                    id=collection,
                    partition_key=PartitionKey(path=partition_key_path),
                )
            except Exception as e:
                print(f"FAILED to create container: {e}")
                counts[key_label] = -1
                continue

            imported = 0
            skipped = 0
            errors = 0

            for i, item in enumerate(iter_ndjson(in_file)):
                # Ensure 'id' field exists (Cosmos requires it)
                if "id" not in item and "_id" in item:
                    item["id"] = item["_id"]

                # Retry with exponential backoff for 429 (throttling)
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        if mode == "upsert":
                            container.upsert_item(item)
                            imported += 1
                        else:
                            try:
                                container.create_item(item)
                                imported += 1
                            except CosmosResourceExistsError:
                                skipped += 1
                        break  # success
                    except CosmosHttpResponseError as e:
                        if e.status_code == 429 and attempt < MAX_RETRIES:
                            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                            retry_after = getattr(e, "retry_after", None)
                            if retry_after:
                                wait = max(wait, retry_after / 1000.0)
                            time.sleep(wait)
                            continue
                        errors += 1
                        if errors <= 3:
                            print(f"\n    Error on doc {i}: {e}", end="")
                        break
                    except Exception as e:
                        errors += 1
                        if errors <= 3:
                            print(f"\n    Error on doc {i}: {e}", end="")
                        break

                # Progress indicator
                if (i + 1) % batch_size == 0:
                    print(f"\r  Importing {key_label} ({i+1:,}/{doc_count:,}) ... ", end="", flush=True)

            counts[key_label] = imported
            status = f"{imported:,} imported"
            if skipped:
                status += f", {skipped:,} skipped"
            if errors:
                status += f", {errors} errors"
            print(f"\r  Importing {key_label} ... {status}            ")

    return counts


def import_mongodb(uri: str, export_dir: Path, databases: dict[str, list[str]],
                   mode: str) -> dict[str, int]:
    """Import into MongoDB using pymongo."""
    try:
        import pymongo
    except ImportError:
        print("ERROR: pymongo is required for MongoDB import. Install with: pip install pymongo")
        sys.exit(1)

    client = pymongo.MongoClient(uri)
    counts: dict[str, int] = {}

    for db_name, collections in databases.items():
        database = client[db_name]

        for collection in collections:
            key_label = f"{db_name}.{collection}"
            in_file = export_dir / db_name / f"{collection}.json"

            if not in_file.exists():
                print(f"  SKIP {key_label} (file not found)")
                continue

            doc_count = count_ndjson_lines(in_file)
            if doc_count == 0:
                print(f"  SKIP {key_label} (empty)")
                continue

            print(f"  Importing {key_label} ({doc_count:,} docs) ... ", end="", flush=True)

            coll = database[collection]
            imported = 0
            skipped = 0
            errors = 0

            for item in iter_ndjson(in_file):
                # Ensure a stable _id for MongoDB
                doc_id = item.get("_id") or item.get("id")
                if doc_id is None:
                    errors += 1
                    if errors <= 3:
                        print(f"\n    Error: document missing both '_id' and 'id'", end="")
                    continue
                if "_id" not in item:
                    item["_id"] = doc_id

                try:
                    if mode == "upsert":
                        coll.replace_one({"_id": doc_id}, item, upsert=True)
                        imported += 1
                    else:
                        try:
                            coll.insert_one(item)
                            imported += 1
                        except pymongo.errors.DuplicateKeyError:
                            skipped += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"\n    Error: {e}", end="")

            counts[key_label] = imported
            status = f"{imported:,} imported"
            if skipped:
                status += f", {skipped:,} skipped"
            if errors:
                status += f", {errors} errors"
            print(status)

    client.close()
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Import data into a CoPilot-for-Consensus deployment."
    )
    parser.add_argument("--dest-type", required=True, choices=["cosmos", "mongodb"],
                        help="Destination database type")
    parser.add_argument("--cosmos-endpoint", help="Azure Cosmos DB endpoint URL")
    parser.add_argument("--cosmos-key", help="Azure Cosmos DB account key")
    parser.add_argument("--use-rbac", action="store_true",
                        help="Use Azure AD / RBAC auth (DefaultAzureCredential)")
    parser.add_argument("--mongo-uri", help="MongoDB connection URI")
    parser.add_argument("--export-dir", required=True, help="Path to export directory")
    parser.add_argument("--collections", help="Comma-separated list of collections to import")
    parser.add_argument("--mode", choices=["upsert", "merge"], default="upsert",
                        help="Import mode: upsert (overwrite) or merge (skip duplicates)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Progress reporting batch size (default: 500)")

    args = parser.parse_args()
    export_dir = Path(args.export_dir)

    if not export_dir.exists():
        parser.error(f"Export directory not found: {export_dir}")

    # Resolve defaults from environment
    if args.dest_type == "cosmos":
        if not args.cosmos_endpoint:
            args.cosmos_endpoint = os.environ.get("DST_COSMOS_ENDPOINT") or os.environ.get("COSMOS_ENDPOINT")
        if not args.cosmos_key and not args.use_rbac:
            args.cosmos_key = os.environ.get("DST_COSMOS_KEY") or os.environ.get("COSMOS_KEY")
        if not args.cosmos_endpoint:
            parser.error("--cosmos-endpoint is required (or set DST_COSMOS_ENDPOINT)")
        if not args.cosmos_key and not args.use_rbac:
            parser.error("--cosmos-key or --use-rbac is required")
    elif args.dest_type == "mongodb":
        if not args.mongo_uri:
            args.mongo_uri = os.environ.get("DST_MONGO_URI") or "mongodb://localhost:27017/"

    # Discover collections from export directory
    databases: dict[str, list[str]] = {}
    for db_dir in export_dir.iterdir():
        if db_dir.is_dir():
            colls = [f.stem for f in db_dir.glob("*.json")]
            if colls:
                databases[db_dir.name] = colls

    # Filter if requested
    if args.collections:
        requested = [c.strip() for c in args.collections.split(",")]
        databases = {
            db: [c for c in colls if c in requested]
            for db, colls in databases.items()
        }
        databases = {db: colls for db, colls in databases.items() if colls}

    # Load manifest if present
    manifest_path = export_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        print(f"Loading export from {manifest.get('exported_at', '?')} (source: {manifest.get('source_type', '?')})")

    print()
    print("=== CoPilot-for-Consensus Data Import ===")
    print(f"  Destination: {args.dest_type}")
    print(f"  Export dir:  {export_dir}")
    print(f"  Mode:        {args.mode}")
    print()

    start = time.time()

    if args.dest_type == "cosmos":
        counts = import_cosmos(
            args.cosmos_endpoint, args.cosmos_key, args.use_rbac,
            export_dir, databases, args.mode, args.batch_size,
        )
    else:
        counts = import_mongodb(args.mongo_uri, export_dir, databases, args.mode)

    elapsed = time.time() - start
    total = sum(v for v in counts.values() if v > 0)
    error_count = sum(1 for v in counts.values() if v < 0)

    print()
    print("=== Import Complete ===")
    print(f"  Total imported: {total:,}")
    print(f"  Elapsed: {elapsed:.1f}s")
    if error_count:
        print(f"  Errors: {error_count} collection(s) failed")
    print()
    print("Next steps:")
    print("  1. Verify data: python scripts/get_data_counts.py")
    print("  2. Restart services if importing into a fresh deployment")
    print("  3. Delete export directory when no longer needed (may contain PII)")


if __name__ == "__main__":
    main()
