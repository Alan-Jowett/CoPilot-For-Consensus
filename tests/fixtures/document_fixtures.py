# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test fixtures for creating schema-compliant document data.

This module provides helper functions to generate valid test data for documents
(messages, chunks, threads, etc.) that conform to the JSON schemas defined in
docs/schemas/documents/.

These fixtures ensure that tests use schema-validated data rather than bypassing
validation through mocks or incomplete test data.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any


def generate_doc_id(seed: str) -> str:
    """Generate a 16-character hex document ID from a seed string.
    
    This mimics the deterministic ID generation used in production code.
    
    Args:
        seed: String to hash for ID generation
        
    Returns:
        16-character hex string suitable for use as _id
    """
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def create_valid_message(
    message_id: str = "<test@example.com>",
    archive_id: str | None = None,
    thread_id: str | None = None,
    subject: str = "Test Subject",
    from_email: str = "sender@example.com",
    from_name: str = "Test Sender",
    body_normalized: str = "This is a test message body.",
    date: str | None = None,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a schema-compliant message document for testing.
    
    This function generates a valid message document that conforms to the
    messages.schema.json specification. All required fields are provided
    with sensible defaults.
    
    Args:
        message_id: RFC 5322 Message-ID (default: "<test@example.com>")
        archive_id: 16-char hex archive ID (auto-generated if None)
        thread_id: 16-char hex thread ID (auto-generated if None)
        subject: Message subject line
        from_email: Sender email address
        from_name: Sender display name
        body_normalized: Normalized message body text
        date: ISO 8601 timestamp (current time if None)
        **kwargs: Additional fields to include in the message
        
    Returns:
        Dictionary containing a valid message document
        
    Example:
        >>> msg = create_valid_message(
        ...     message_id="<test123@example.com>",
        ...     subject="Test Message",
        ...     body_normalized="Test content"
        ... )
        >>> assert msg["_id"]  # Has valid _id
        >>> assert msg["message_id"] == "<test123@example.com>"
    """
    # Generate deterministic IDs if not provided
    if archive_id is None:
        archive_id = generate_doc_id(f"archive-{message_id}")
    if thread_id is None:
        thread_id = generate_doc_id(f"thread-{message_id}")
    if date is None:
        date = datetime.now(timezone.utc).isoformat()
    
    # Generate deterministic _id from stable fields
    doc_id = generate_doc_id(f"{archive_id}|{message_id}|{date}|{from_email}|{subject}")
    
    message = {
        "_id": doc_id,
        "message_id": message_id,
        "archive_id": archive_id,
        "thread_id": thread_id,
        "in_reply_to": None,
        "references": [],
        "subject": subject,
        "from": {
            "email": from_email,
            "name": from_name,
        },
        "to": [],
        "cc": [],
        "date": date,
        "body_raw": body_normalized,  # Often same as normalized in tests
        "body_normalized": body_normalized,
        "body_html": None,
        "attachments": [],
        "draft_mentions": [],
        "created_at": date,
        "status": "completed",
        "attemptCount": 0,
        "lastAttemptTime": None,
        "lastUpdated": date,
    }
    
    # Merge any additional fields provided
    message.update(kwargs)
    
    return message


def create_valid_chunk(
    message_doc_id: str | None = None,
    message_id: str = "<test@example.com>",
    thread_id: str | None = None,
    chunk_index: int = 0,
    text: str = "This is chunk text.",
    token_count: int = 10,
    **kwargs: Any
) -> dict[str, Any]:
    """Create a schema-compliant chunk document for testing.
    
    This function generates a valid chunk document that conforms to the
    chunks.schema.json specification. All required fields are provided
    with sensible defaults.
    
    Args:
        message_doc_id: 16-char hex message document ID (auto-generated if None)
        message_id: RFC 5322 Message-ID
        thread_id: 16-char hex thread ID (auto-generated if None)
        chunk_index: Zero-based chunk index within the message
        text: Chunk text content
        token_count: Number of tokens in the chunk
        **kwargs: Additional fields to include in the chunk
        
    Returns:
        Dictionary containing a valid chunk document
        
    Example:
        >>> chunk = create_valid_chunk(
        ...     chunk_index=0,
        ...     text="First chunk of text",
        ...     token_count=5
        ... )
        >>> assert chunk["_id"]  # Has valid _id
        >>> assert chunk["chunk_index"] == 0
        >>> assert chunk["embedding_generated"] is False
    """
    # Generate deterministic IDs if not provided
    if message_doc_id is None:
        message_doc_id = generate_doc_id(f"message-{message_id}")
    if thread_id is None:
        thread_id = generate_doc_id(f"thread-{message_id}")
    
    # Generate deterministic _id for the chunk
    chunk_id = generate_doc_id(f"{message_doc_id}|{chunk_index}")
    
    created_at = datetime.now(timezone.utc).isoformat()
    
    chunk = {
        "_id": chunk_id,
        "message_doc_id": message_doc_id,
        "message_id": message_id,
        "thread_id": thread_id,
        "chunk_index": chunk_index,
        "text": text,
        "token_count": token_count,
        "start_offset": None,
        "end_offset": None,
        "overlap_with_previous": False,
        "metadata": {
            "sender": "sender@example.com",
            "date": created_at,
            "subject": "Test Subject",
        },
        "created_at": created_at,
        "embedding_generated": False,
        "status": "pending",
        "attemptCount": 0,
        "lastAttemptTime": None,
        "lastUpdated": created_at,
    }
    
    # Merge any additional fields provided
    chunk.update(kwargs)
    
    return chunk


def create_valid_thread(
    thread_id: str | None = None,
    root_message_id: str = "<root@example.com>",
    subject: str = "Test Thread Subject",
    **kwargs: Any
) -> dict[str, Any]:
    """Create a schema-compliant thread document for testing.
    
    Args:
        thread_id: 16-char hex thread ID (auto-generated if None)
        root_message_id: Message-ID of the thread's root message
        subject: Thread subject line
        **kwargs: Additional fields to include in the thread
        
    Returns:
        Dictionary containing a valid thread document
    """
    if thread_id is None:
        thread_id = generate_doc_id(f"thread-{root_message_id}")
    
    created_at = datetime.now(timezone.utc).isoformat()
    
    thread = {
        "_id": thread_id,
        "root_message_id": root_message_id,
        "subject": subject,
        "message_ids": [root_message_id],
        "participant_emails": ["sender@example.com"],
        "created_at": created_at,
        "updated_at": created_at,
        "message_count": 1,
        "status": "active",
        "lastUpdated": created_at,
    }
    
    thread.update(kwargs)
    return thread


def create_valid_archive(
    archive_id: str | None = None,
    source_name: str = "test-source",
    file_path: str = "/test/path/test.mbox",
    **kwargs: Any
) -> dict[str, Any]:
    """Create a schema-compliant archive document for testing.
    
    Args:
        archive_id: 16-char hex archive ID (auto-generated if None)
        source_name: Name of the archive source
        file_path: Path to the archive file
        **kwargs: Additional fields to include in the archive
        
    Returns:
        Dictionary containing a valid archive document
    """
    if archive_id is None:
        archive_id = generate_doc_id(f"archive-{source_name}-{file_path}")
    
    created_at = datetime.now(timezone.utc).isoformat()
    
    archive = {
        "_id": archive_id,
        "archive_id": archive_id,
        "source_name": source_name,
        "file_path": file_path,
        "file_size_bytes": 1024,
        "file_hash_sha256": hashlib.sha256(file_path.encode()).hexdigest(),
        "message_count": 0,
        "created_at": created_at,
        "status": "completed",
        "lastUpdated": created_at,
    }
    
    archive.update(kwargs)
    return archive
