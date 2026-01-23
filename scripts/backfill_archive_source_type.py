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
import sys
from datetime import datetime, timezone

from copilot_logging import get_logger
from copilot_storage import create_document_store

logger = get_logger(__name__)


def backfill_archive_source_type(dry_run: bool = False, limit: int | None = None) -> dict:
    """
    Backfill source_type field for legacy archives.

    Args:
        dry_run: If True, show what would be updated without making changes
        limit: Maximum number of documents to process (None for no limit)

    Returns:
        Dictionary with migration statistics
    """
    logger.info("Starting archive source_type backfill migration")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if limit:
        logger.info(f"Processing limit: {limit} documents")

    document_store = create_document_store()

    # Find archives missing source_type field
    query = {"source_type": {"$exists": False}}
    
    # Count total documents needing migration
    total_count = document_store.count("archives", query)
    logger.info(f"Found {total_count} archives missing 'source_type' field")

    if total_count == 0:
        logger.info("No archives need migration. Exiting.")
        return {"total_found": 0, "updated": 0, "errors": 0}

    # Apply limit if specified
    docs_to_process = min(limit, total_count) if limit else total_count
    logger.info(f"Will process {docs_to_process} documents")

    # Get sample of documents to show what will be updated
    sample_docs = list(document_store.find("archives", query, limit=min(5, docs_to_process)))
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
        limited_docs = list(document_store.find("archives", query, limit=limit))
        doc_ids = [doc["_id"] for doc in limited_docs]
        update_query = {"_id": {"$in": doc_ids}}

    try:
        update_result = document_store.update_many(
            "archives",
            update_query,
            {"$set": {"source_type": "local"}}
        )
        
        updated_count = getattr(update_result, 'modified_count', 0)
        logger.info(f"Successfully updated {updated_count} archives")
        
        return {
            "total_found": total_count,
            "updated": updated_count,
            "errors": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return {
            "total_found": total_count,
            "updated": 0,
            "errors": 1,
            "error_message": str(e),
        }


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Backfill source_type field for legacy archives"
    )
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

    try:
        result = backfill_archive_source_type(dry_run=args.dry_run, limit=args.limit)
        
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
