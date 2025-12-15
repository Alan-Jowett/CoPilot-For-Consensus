# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Deterministic message and chunk key generation for guaranteed uniqueness and audit trail."""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_message_key(
    archive_id: str,
    message_id: str,
    date: Optional[str] = None,
    sender_email: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Generate a deterministic message key from archive and message properties.
    
    Creates a SHA256 hash of the composite archive + message identity to ensure:
    - Global uniqueness across all archives
    - Deterministic reproducibility (same archive + message = same key)
    - Audit trail back to the source archive and mailbox
    
    Args:
        archive_id: SHA256 hash of the archive this message came from (first 16 chars)
        message_id: Original Message-ID header from email
        date: Email date (ISO 8601 format). Optional but recommended for better uniqueness.
        sender_email: Sender email address. Optional but recommended for better uniqueness.
        subject: Email subject. Optional but recommended for better uniqueness.
        
    Returns:
        16-character hex string representing the message (first 16 chars of SHA256)
    """
    # Build composite key with available fields
    # Use empty string for None values to maintain determinism
    composite = f"{archive_id}|{message_id}"
    
    if date:
        composite += f"|{date}"
    if sender_email:
        composite += f"|{sender_email}"
    if subject:
        composite += f"|{subject}"
    
    # Generate SHA256 hash
    hash_obj = hashlib.sha256(composite.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()
    
    # Return first 16 characters (64-bit identifier, sufficient for collision avoidance)
    return hash_hex[:16]


def generate_chunk_key(
    message_key: str,
    chunk_index: int,
) -> str:
    """Generate a deterministic chunk key from message key and chunk index.
    
    Creates a SHA256 hash of the message key + chunk index to ensure:
    - Each chunk in a message has a unique, deterministic key
    - Reproducibility (same message + chunk index = same key)
    - Idempotency (re-chunking same message produces same chunk keys)
    
    Args:
        message_key: Parent message's message_key
        chunk_index: Zero-based chunk index within the message
        
    Returns:
        16-character hex string representing the chunk
    """
    composite = f"{message_key}|{chunk_index}"
    
    # Generate SHA256 hash
    hash_obj = hashlib.sha256(composite.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()
    
    # Return first 16 characters
    return hash_hex[:16]
