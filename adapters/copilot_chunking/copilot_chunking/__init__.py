# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Chunking Adapter.

A shared library for thread chunking strategies that break up email threads
into smaller, semantically coherent chunks suitable for embedding or summarization.

This module provides an abstraction layer for different chunking strategies,
enabling flexible experimentation without modifying downstream services.

Example:
    >>> from copilot_chunking import Thread, create_chunker
    >>>
    >>> # Create a chunker with token window strategy
    >>> chunker = create_chunker("token_window", chunk_size=384, overlap=50)
    >>>
    >>> # Create a thread
    >>> thread = Thread(
    ...     thread_id="<msg@example.com>",
    ...     text="Email content here...",
    ...     metadata={"sender": "user@example.com"}
    ... )
    >>>
    >>> # Chunk the thread
    >>> chunks = chunker.chunk(thread)
    >>>
    >>> # Process chunks
    >>> for chunk in chunks:
    ...     print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
"""

__version__ = "0.1.0"

from .chunkers import (
    ThreadChunker,
    TokenWindowChunker,
    FixedSizeChunker,
    SemanticChunker,
    Chunk,
    Thread,
    create_chunker,
)

__all__ = [
    # Version
    "__version__",
    # Core interface
    "ThreadChunker",
    # Implementations
    "TokenWindowChunker",
    "FixedSizeChunker",
    "SemanticChunker",
    # Data classes
    "Chunk",
    "Thread",
    # Factory
    "create_chunker",
]
