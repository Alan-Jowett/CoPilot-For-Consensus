#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Migration script to backfill 'source_type' field for legacy archives.

This script updates archives in the database that are missing the 'source_type'
field by setting it to 'local' (the default used by the parsing service).

Usage:
    python backfill_archive_source_type.py [--dry-run] [--limit N]

Options:
    --dry-run: Show what would be updated without making changes
    --limit N: Process at most N documents (default: no limit)
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from copilot_logging import create_stdout_logger

# Import pymongo - required for direct database access
try:
    from pymongo import MongoClient

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None  # type: ignore

logger = create_stdout_logger(level=os.getenv("LOG_LEVEL", "INFO"), name=__name__)


def _get_env_or_secret(env_var: str, secret_name: str) -> str | None:
    """Return env var if set, otherwise read from /run/secrets/<secret_name>."""
    if env_var in os.environ and os.environ[env_var]:
        return os.environ[env_var]
    secret_path = Path("/run/secrets") / secret_name
    try:
        return secret_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Failed to read secret %s: %s", secret_path, exc)
        return None


def _build_mongo_connection_string(
    host: str, port: int, database: str, username: str | None, password: str | None
) -> str:
    """Build MongoDB connection string.

    This is a separate function to isolate credential handling from logging code paths.
    """
    if username and password:
        return (
            f"mongodb://{username}:{password}@"
            f"{host}:{port}/{database}?authSource=admin"
        )
    return f"mongodb://{host}:{port}/{database}"


def backfill_archive_source_type(
    mongodb_host: str,
    mongodb_port: int,
    mongodb_database: str,
    mongodb_username: str | None = None,
    mongodb_password: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    """
    Backfill source_type field for legacy archives.

    Args:
        mongodb_host: MongoDB host
        mongodb_port: MongoDB port
        mongodb_database: Database name
        mongodb_username: Optional username for authentication
        mongodb_password: Optional password for authentication
        dry_run: If True, show what would be updated without making changes
        limit: Maximum number of documents to process (None for no limit)

    Returns:
        Dictionary with migration statistics
    """
    logger.info("Starting archive source_type backfill migration")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if limit:
        logger.info(f"Processing limit: {limit} documents")

    # Build connection string in separate function to isolate credentials from logging
    connection_string = _build_mongo_connection_string(
        mongodb_host, mongodb_port, mongodb_database, mongodb_username, mongodb_password
    )

    try:
        mongo_client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        db = mongo_client[mongodb_database]

        # Test connection
        mongo_client.admin.command("ping")
        logger.info(f"Connected to MongoDB at {mongodb_host}:{mongodb_port}")
    except Exception:
        # Log error without any exception details - connection errors may expose credentials
        logger.error(f"Failed to connect to MongoDB at {mongodb_host}:{mongodb_port}")
        return {"total_found": 0, "updated": 0, "errors": 1, "error_message": "ConnectionError"}

    try:
        # Find archives missing source_type field
        query = {"source_type": {"$exists": False}}

        # Count total documents needing migration
        total_count = db.archives.count_documents(query)
        logger.info(f"Found {total_count} archives missing 'source_type' field")

        if total_count == 0:
            logger.info("No archives need migration. Exiting.")
            return {"total_found": 0, "updated": 0, "errors": 0}

        # Apply limit if specified
        docs_to_process = min(limit, total_count) if limit else total_count
        logger.info(f"Will process {docs_to_process} documents")

        # Get sample of documents to show what will be updated
        sample_docs = list(db.archives.find(query).limit(min(5, docs_to_process)))
        if sample_docs:
            logger.info("Sample archives to be updated:")
            for doc in sample_docs:
                archive_id = doc.get("archive_id") or doc.get("_id")
                source = doc.get("source", "UNKNOWN")
                logger.info(f"  - Archive: {archive_id}, Source: {source}")

        if dry_run:
            logger.info(f"DRY RUN: Would update {docs_to_process} archives with source_type='local'")
            return {"total_found": total_count, "updated": 0, "errors": 0, "dry_run": True}

        # Perform the update
        logger.info("Executing update operation...")
        update_query = query.copy()
        if limit:
            # For limited updates, get specific document IDs
            limited_docs = list(db.archives.find(query).limit(limit))
            doc_ids = [doc["_id"] for doc in limited_docs]
            update_query = {"_id": {"$in": doc_ids}}

        update_result = db.archives.update_many(update_query, {"$set": {"source_type": "local"}})

        updated_count = update_result.modified_count
        logger.info(f"Successfully updated {updated_count} archives")

        return {
            "total_found": total_count,
            "updated": updated_count,
            "errors": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        # Preserve total_count if it was determined before the error
        found_count = locals().get('total_count', 0)
        return {
            "total_found": found_count,
            "updated": 0,
            "errors": 1,
            "error_message": str(e),
        }
    finally:
        mongo_client.close()
        logger.info("Disconnected from MongoDB")


def main():
    """Main entry point for the migration script."""
    if not PYMONGO_AVAILABLE:
        logger.error("pymongo is not installed. Install with: pip install pymongo")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Backfill source_type field for legacy archives")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N documents",
    )

    args = parser.parse_args()

    # Get MongoDB configuration from environment/secrets
    mongodb_host = _get_env_or_secret("DOCUMENT_DATABASE_HOST", "document_database_host") or "localhost"
    mongodb_port = int(_get_env_or_secret("DOCUMENT_DATABASE_PORT", "document_database_port") or "27017")
    mongodb_database = _get_env_or_secret("DOCUMENT_DATABASE_NAME", "document_database_name") or "copilot"
    mongodb_username = _get_env_or_secret("DOCUMENT_DATABASE_USER", "document_database_user")
    mongodb_password = _get_env_or_secret("DOCUMENT_DATABASE_PASSWORD", "document_database_password")

    logger.info(f"MongoDB configuration: {mongodb_host}:{mongodb_port}/{mongodb_database}")

    try:
        result = backfill_archive_source_type(
            mongodb_host=mongodb_host,
            mongodb_port=mongodb_port,
            mongodb_database=mongodb_database,
            mongodb_username=mongodb_username,
            mongodb_password=mongodb_password,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        logger.info("Migration complete!")
        logger.info(f"Summary: {result}")

        if result.get("errors", 0) > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
