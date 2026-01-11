#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Example: Using DocumentStatus enum for forward progress tracking.

This example demonstrates how to use the DocumentStatus enum and new tracking
fields (lastUpdated, workerId) for managing document processing state across
the Copilot-for-Consensus system.
"""

from copilot_schema_validation import DocumentStatus
from datetime import datetime, timezone
from typing import Dict, Any


def should_retry_document(document: Dict[str, Any], max_attempts: int = 3) -> bool:
    """
    Determine if a document should be retried based on status and attempt count.

    Args:
        document: Document with status and attemptCount fields
        max_attempts: Maximum number of retry attempts allowed

    Returns:
        True if document should be retried, False otherwise
    """
    status = DocumentStatus(document.get("status", "pending"))
    attempt_count = document.get("attemptCount", 0)

    # Retry failed documents that haven't exceeded max attempts
    if status == DocumentStatus.FAILED and attempt_count < max_attempts:
        return True

    return False


def update_document_for_processing(
    document: Dict[str, Any],
    worker_id: str
) -> Dict[str, Any]:
    """
    Update document status and tracking fields when starting processing.

    Args:
        document: Document to update
        worker_id: Identifier of worker processing this document

    Returns:
        Updated document with new status and tracking fields
    """
    document["status"] = DocumentStatus.PROCESSING.value
    document["lastUpdated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    document["workerId"] = worker_id
    document["lastAttemptTime"] = document["lastUpdated"]
    document["attemptCount"] = document.get("attemptCount", 0) + 1

    return document


def mark_document_completed(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mark document as completed successfully.

    Args:
        document: Document to mark as completed

    Returns:
        Updated document with completed status
    """
    document["status"] = DocumentStatus.COMPLETED.value
    document["lastUpdated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # workerId remains set to show which worker completed it

    return document


def mark_document_failed(
    document: Dict[str, Any],
    max_attempts: int = 3
) -> Dict[str, Any]:
    """
    Mark document as failed and determine if max retries reached.

    Args:
        document: Document to mark as failed
        max_attempts: Maximum retry attempts allowed

    Returns:
        Updated document with failed status
    """
    attempt_count = document.get("attemptCount", 0)

    if attempt_count >= max_attempts:
        document["status"] = DocumentStatus.FAILED_MAX_RETRIES.value
    else:
        document["status"] = DocumentStatus.FAILED.value

    document["lastUpdated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # workerId remains set to show which worker encountered the failure

    return document


def build_query_for_stale_documents(stale_minutes: int = 30) -> Dict[str, Any]:
    """
    Build MongoDB query to find documents stuck in processing.

    Args:
        stale_minutes: Number of minutes before considering a document stale

    Returns:
        MongoDB query filter
    """
    from datetime import timedelta

    stale_threshold = (
        datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
    ).isoformat().replace("+00:00", "Z")

    return {
        "status": DocumentStatus.PROCESSING.value,
        "lastUpdated": {"$lt": stale_threshold}
    }


def query_documents_needing_work() -> Dict[str, Any]:
    """
    Build query to find documents that need processing.

    Returns:
        MongoDB query filter for documents needing work
    """
    return {
        "status": {
            "$in": [
                DocumentStatus.PENDING.value,
                DocumentStatus.FAILED.value
            ]
        }
    }


# Example usage
if __name__ == "__main__":
    print("Document Status Tracking Examples\n")
    print("=" * 60)

    # Example 1: Process a pending document
    print("\n1. Processing a pending document:")
    doc = {
        "_id": "abc123",
        "status": "pending",
        "attemptCount": 0
    }
    print(f"   Before: {doc}")

    doc = update_document_for_processing(doc, "worker-001")
    print(f"   After:  {doc}")

    # Simulate successful processing
    doc = mark_document_completed(doc)
    print(f"   Completed: status={doc['status']}, attemptCount={doc['attemptCount']}")

    # Example 2: Handle a failed document with retries
    print("\n2. Handling a failed document with retries:")
    doc = {
        "_id": "def456",
        "status": "failed",  # Start with failed status to demonstrate retry logic
        "attemptCount": 1
    }

    for i in range(3):
        if should_retry_document(doc, max_attempts=3):
            doc = update_document_for_processing(doc, f"worker-{i+2:03d}")
            print(f"   Attempt {doc['attemptCount']}: Processing on {doc['workerId']}")
            # Simulate failure
            doc = mark_document_failed(doc, max_attempts=3)
            print(f"   Result: status={doc['status']}")
        else:
            print(f"   Cannot retry: {doc['status']}, attempts={doc.get('attemptCount', 0)}")
            break

    # Example 3: Find documents needing work
    print("\n3. Query for documents needing work:")
    query = query_documents_needing_work()
    print(f"   Query: {query}")

    # Example 4: Find stale documents
    print("\n4. Query for stale documents (stuck in processing):")
    stale_query = build_query_for_stale_documents(stale_minutes=30)
    print(f"   Query: {stale_query}")

    # Example 5: All status values
    print("\n5. All DocumentStatus enum values:")
    for status in list(DocumentStatus):
        print(f"   - {status.name:20s} = {status.value}")

    print("\n" + "=" * 60)
    print("Examples completed successfully!")
