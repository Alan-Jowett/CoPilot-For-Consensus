#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Converter job to transform NDJSON diagnostic logs to CSV format.

This ACA Job processes Azure diagnostic logs stored as NDJSON in Blob Storage
and converts them to normalized CSV files in Azure Files for easier analysis.

Usage:
    python convert_ndjson_to_csv.py [--storage-account ACCOUNT] [--input-container CONTAINER] [--output-share SHARE]

Environment Variables:
    STORAGE_ACCOUNT_NAME: Azure Storage account name (required)
    INPUT_CONTAINER: Blob container with NDJSON logs (default: logs-raw)
    OUTPUT_SHARE: File share for CSV output (default: logs-csv)
    OUTPUT_MOUNT_PATH: Local mount path for file share (default: /mnt/logs)
    AZURE_CLIENT_ID: Managed identity client ID for authentication
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert NDJSON diagnostic logs to CSV format"
    )
    parser.add_argument(
        "--storage-account",
        default=os.getenv("STORAGE_ACCOUNT_NAME"),
        help="Azure Storage account name",
    )
    parser.add_argument(
        "--input-container",
        default=os.getenv("INPUT_CONTAINER", "logs-raw"),
        help="Blob container with NDJSON logs",
    )
    parser.add_argument(
        "--output-share",
        default=os.getenv("OUTPUT_SHARE", "logs-csv"),
        help="File share for CSV output",
    )
    parser.add_argument(
        "--output-mount",
        default=os.getenv("OUTPUT_MOUNT_PATH", "/mnt/logs"),
        help="Local mount path for Azure Files",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=int(os.getenv("LOOKBACK_HOURS", "1")),
        help="Process logs from the last N hours",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List blobs to process without converting",
    )
    return parser.parse_args()


def get_blob_service_client(storage_account: str) -> BlobServiceClient:
    """Create blob service client with managed identity authentication.

    Args:
        storage_account: Azure Storage account name

    Returns:
        BlobServiceClient instance
    """
    credential = DefaultAzureCredential()
    account_url = f"https://{storage_account}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


def list_new_blobs(
    blob_service: BlobServiceClient,
    container_name: str,
    since: datetime,
) -> List[str]:
    """List blobs created since a given time.

    Args:
        blob_service: Blob service client
        container_name: Container name
        since: Only list blobs created after this time

    Returns:
        List of blob names
    """
    container_client = blob_service.get_container_client(container_name)
    blobs = []

    for blob in container_client.list_blobs():
        if blob.last_modified and blob.last_modified >= since:
            blobs.append(blob.name)

    return blobs


def convert_ndjson_to_csv(
    ndjson_content: str,
    output_path: Path,
    blob_name: str,
) -> int:
    """Convert NDJSON content to CSV file.

    Args:
        ndjson_content: NDJSON log content
        output_path: Output CSV file path
        blob_name: Source blob name (for tracking)

    Returns:
        Number of records converted
    """
    # Parse NDJSON lines
    records = []
    for line in ndjson_content.strip().split("\n"):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping invalid JSON line in {blob_name}: {e}", file=sys.stderr)
            continue

    if not records:
        print(f"No valid records found in {blob_name}", file=sys.stderr)
        return 0

    # Define stable field set (extend as needed)
    known_fields = [
        "TimeGenerated",
        "Category",
        "Level",
        "ContainerName",
        "ContainerAppName",
        "RevisionName",
        "ReplicaName",
        "Message",
        "Stream",
        "_ResourceId",
    ]

    fieldnames = known_fields + ["_extras", "_source_blob"]

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            # Extract known fields
            row: Dict[str, Any] = {}
            for field in known_fields:
                row[field] = record.get(field, "")

            # Put remaining fields in _extras
            extras = {k: v for k, v in record.items() if k not in known_fields}
            row["_extras"] = json.dumps(extras, ensure_ascii=False) if extras else ""
            row["_source_blob"] = blob_name

            writer.writerow(row)

    return len(records)


def main() -> int:
    """Main converter job entry point."""
    args = parse_args()

    if not args.storage_account:
        print("Error: --storage-account or STORAGE_ACCOUNT_NAME required", file=sys.stderr)
        return 1

    # Create blob service client
    try:
        blob_service = get_blob_service_client(args.storage_account)
    except Exception as e:
        print(f"Error: Failed to authenticate to storage account: {e}", file=sys.stderr)
        return 1

    # Calculate lookback window
    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.lookback_hours)
    print(f"Processing blobs created since {since.isoformat()}")

    # List new blobs
    try:
        blobs = list_new_blobs(blob_service, args.input_container, since)
    except Exception as e:
        print(f"Error: Failed to list blobs: {e}", file=sys.stderr)
        return 1

    if not blobs:
        print("No new blobs to process")
        return 0

    print(f"Found {len(blobs)} blobs to process")

    if args.dry_run:
        for blob in blobs:
            print(f"  {blob}")
        return 0

    # Create output directory
    output_dir = Path(args.output_mount)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each blob
    total_records = 0
    for blob_name in blobs:
        print(f"Processing {blob_name}...")

        try:
            # Download blob content
            container_client = blob_service.get_container_client(args.input_container)
            blob_client = container_client.get_blob_client(blob_name)
            ndjson_content = blob_client.download_blob().readall().decode("utf-8")

            # Generate output CSV filename
            # Example: logs-raw/2025-01-20-12-00.json -> 2025-01-20-12-00.csv
            csv_filename = Path(blob_name).stem + ".csv"
            output_path = output_dir / csv_filename

            # Convert
            record_count = convert_ndjson_to_csv(ndjson_content, output_path, blob_name)
            total_records += record_count
            print(f"  -> {output_path} ({record_count} records)")

        except Exception as e:
            print(f"Error processing {blob_name}: {e}", file=sys.stderr)
            continue

    print(f"\nConversion complete: {total_records} total records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
