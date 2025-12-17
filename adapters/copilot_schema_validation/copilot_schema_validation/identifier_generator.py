# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Deterministic ID generators used across collections.

Functions in this module produce short, deterministic identifiers that
align with the canonical `_id` rules in documents/SCHEMA.md.

Provided generators:
- generate_archive_id_from_bytes: `_id` for archives (SHA256_16 of content)
- generate_message_doc_id: `_id` for messages (composite hash)
- generate_chunk_id: `_id` for chunks (message_id|chunk_index)
- generate_thread_id: `_id` for threads (hash of source|root_message_id|normalized_subject)
- generate_summary_id: `_id` for summaries (thread_id|content|generated_at)
"""

from __future__ import annotations

import hashlib
from typing import Optional


def _sha256_16(s: str) -> str:
    """Return first 16 hex chars of SHA256 digest of the input string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def generate_archive_id_from_bytes(data: bytes) -> str:
    """Generate `_id` for an archive from its raw bytes.

    Per SCHEMA.md, archives `_id` is the first 16 hex chars of the SHA256
    of the mbox file contents.
    """
    return hashlib.sha256(data).hexdigest()[:16]


def generate_message_doc_id(
    archive_id: str,
    message_id: str,
    date: Optional[str] = None,
    sender_email: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Generate the canonical `_id` for a message document.

    Composite fields mirror documents/schemas/documents/messages.schema.json
    description: archive_id|message_id|date|sender_email|subject.
    Missing optional fields are treated as empty strings.
    """
    parts = [archive_id or "", message_id or ""]
    if date:
        parts.append(date)
    if sender_email:
        parts.append(sender_email)
    if subject:
        parts.append(subject)
    composite = "|".join(parts)
    return _sha256_16(composite)


def generate_chunk_id(message_doc_id: str, chunk_index: int) -> str:
    """Generate the canonical `_id` for a chunk document.

    Per design, `_id = SHA256_16(message_doc_id | chunk_index)`.
    """
    composite = f"{message_doc_id}|{chunk_index}"
    return _sha256_16(composite)


def generate_thread_id(
    source: str,
    root_message_id: Optional[str] = None,
    normalized_subject: Optional[str] = None,
) -> str:
    """Generate the canonical `_id` for a thread document.

    To avoid cross-mailing-list collisions, scope by source (e.g., "ietf-quic").
    Uses a deterministic SHA256_16 hash over `source|root_message_id|normalized_subject`.
    Missing optional fields are treated as empty strings.
    """
    parts = [source or ""]
    if root_message_id:
        parts.append(root_message_id)
    if normalized_subject:
        parts.append(normalized_subject)
    composite = "|".join(parts)
    return _sha256_16(composite)


def generate_summary_id(thread_id: str, content_markdown: str, generated_at_iso: str) -> str:
    """Generate the canonical `_id` for a summary document.

    Derivation follows SCHEMA.md guidance: combine thread_id, content,
    and generated_at timestamp, then hash to SHA256_16.
    """
    composite = f"{thread_id}|{content_markdown}|{generated_at_iso}"
    return _sha256_16(composite)
