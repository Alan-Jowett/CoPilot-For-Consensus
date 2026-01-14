# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Thread chunking strategies for Copilot-for-Consensus.

This module provides an abstraction layer for different thread chunking strategies,
enabling flexible experimentation with different approaches to breaking up email
threads before embedding or summarization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Union

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.chunker import (
    AdapterConfig_Chunker,
    DriverConfig_Chunker_FixedSize,
    DriverConfig_Chunker_Semantic,
    DriverConfig_Chunker_TokenWindow,
)
from copilot_schema_validation import generate_chunk_id


ChunkerDriverConfig = Union[
    DriverConfig_Chunker_FixedSize,
    DriverConfig_Chunker_Semantic,
    DriverConfig_Chunker_TokenWindow,
]


@dataclass
class Chunk:
    """Represents a text chunk from a thread.

    Attributes:
        chunk_id: Unique identifier for the chunk (SHA256 hash)
        text: The actual text content of the chunk
        chunk_index: Sequential position within the source (0-based)
        token_count: Number of tokens in the chunk
        metadata: Additional context information (sender, date, subject, etc.)
        message_doc_id: Parent message document `_id`
        thread_id: Thread `_id` the chunk belongs to
        start_offset: Character offset in original text (optional)
        end_offset: End character offset in original text (optional)
    """
    chunk_id: str
    text: str
    chunk_index: int
    token_count: int
    metadata: dict[str, Any]
    message_doc_id: str
    thread_id: str
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass
class Thread:
    """Represents an email thread or message to be chunked.

    Attributes:
        thread_id: Unique identifier for the thread
        text: The text content to chunk (can be a single message or thread)
        metadata: Context information (sender, date, subject, etc.)
        message_doc_id: Message document `_id` for tracking, optional
        message_id: RFC 5322 Message-ID header, optional
        messages: Optional list of individual messages in the thread
    """
    thread_id: str
    text: str
    metadata: dict[str, Any]
    message_doc_id: str | None = None
    message_id: str | None = None
    messages: list[dict[str, Any]] | None = None


class ThreadChunker(ABC):
    """Abstract base class for thread chunking strategies.

    All chunking strategies must implement the chunk() method to break
    threads into smaller, semantically coherent chunks suitable for
    embedding or summarization.
    """

    @abstractmethod
    def chunk(self, thread: Thread) -> list[Chunk]:
        """Chunk a thread into smaller pieces.

        Args:
            thread: The thread to chunk

        Returns:
            List of chunks with metadata

        Raises:
            ValueError: If thread is invalid or empty
        """
        pass


class TokenWindowChunker(ThreadChunker):
    """Chunking strategy using a sliding token window.

    This chunker splits text based on a target token count with configurable
    overlap between consecutive chunks to preserve context.

    Attributes:
        chunk_size: Target size for each chunk in tokens
        overlap: Number of tokens to overlap between chunks
        min_chunk_size: Minimum acceptable chunk size (discard smaller)
        max_chunk_size: Maximum chunk size (hard limit)
    """

    def __init__(
        self,
        chunk_size: int = 384,
        overlap: int = 50,
        min_chunk_size: int = 100,
        max_chunk_size: int = 512
    ):
        """Initialize TokenWindowChunker.

        Args:
            chunk_size: Target chunk size in tokens (default: 384)
            overlap: Overlap between chunks in tokens (default: 50)
            min_chunk_size: Minimum chunk size in tokens (default: 100)
            max_chunk_size: Maximum chunk size in tokens (default: 512)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    @classmethod
    def from_config(cls, driver_config: DriverConfig_Chunker_TokenWindow) -> "TokenWindowChunker":
        """Create TokenWindowChunker from driver configuration.

        Expected keys in driver_config:
        - chunk_size (int)
        - overlap (int)
        - min_chunk_size (int)
        - max_chunk_size (int)
        """
        chunk_size = driver_config.chunk_size
        overlap = driver_config.overlap
        min_chunk_size = driver_config.min_chunk_size
        max_chunk_size = driver_config.max_chunk_size

        return cls(
            chunk_size=int(chunk_size if chunk_size is not None else 384),
            overlap=int(overlap if overlap is not None else 50),
            min_chunk_size=int(min_chunk_size if min_chunk_size is not None else 100),
            max_chunk_size=int(max_chunk_size if max_chunk_size is not None else 512),
        )

    def chunk(self, thread: Thread) -> list[Chunk]:
        """Chunk a thread using a sliding token window.

        Args:
            thread: The thread to chunk

        Returns:
            List of chunks with metadata

        Raises:
            ValueError: If thread text is empty or message_doc_id is not provided
        """
        if not thread.text or not thread.text.strip():
            raise ValueError("Thread text cannot be empty")
        if thread.message_doc_id is None:
            raise ValueError("Thread message_doc_id must be provided before chunking")

        # Simple word-based approximation for token counting
        # In a real implementation, use tiktoken or similar
        words = thread.text.split()
        chunks = []

        start_idx = 0
        chunk_index = 0

        while start_idx < len(words):
            # Calculate end index for this chunk
            end_idx = min(start_idx + self.chunk_size, len(words))

            # Get the chunk text
            chunk_words = words[start_idx:end_idx]
            chunk_text = " ".join(chunk_words)

            # Only create chunk if it meets minimum size
            if len(chunk_words) >= self.min_chunk_size or end_idx == len(words):
                chunk = Chunk(
                    chunk_id=generate_chunk_id(thread.message_doc_id, chunk_index),
                    message_doc_id=thread.message_doc_id,
                    thread_id=thread.thread_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    token_count=len(chunk_words),
                    metadata=thread.metadata.copy(),
                    start_offset=None,  # Could calculate character offsets if needed
                    end_offset=None
                )
                chunks.append(chunk)
                chunk_index += 1

            # Move to next window with overlap
            if end_idx == len(words):
                break

            prev_start_idx = start_idx
            start_idx = end_idx - self.overlap

            # Ensure we make progress (avoid infinite loops)
            if start_idx <= prev_start_idx:
                start_idx = end_idx

        return chunks


class FixedSizeChunker(ThreadChunker):
    """Chunking strategy with fixed number of messages per chunk.

    This chunker groups N consecutive messages together, useful for
    preserving conversation flow in threaded discussions.

    Attributes:
        messages_per_chunk: Number of messages to include in each chunk
    """

    def __init__(self, messages_per_chunk: int = 5):
        """Initialize FixedSizeChunker.

        Args:
            messages_per_chunk: Number of messages per chunk (default: 5)
        """
        if messages_per_chunk < 1:
            raise ValueError("messages_per_chunk must be at least 1")
        self.messages_per_chunk = messages_per_chunk

    @classmethod
    def from_config(cls, driver_config: DriverConfig_Chunker_FixedSize) -> "FixedSizeChunker":
        """Create FixedSizeChunker from driver configuration.

        Expected keys:
        - messages_per_chunk (int)
        """
        messages_per_chunk = driver_config.messages_per_chunk
        return cls(messages_per_chunk=int(messages_per_chunk if messages_per_chunk is not None else 5))

    def chunk(self, thread: Thread) -> list[Chunk]:
        """Chunk a thread by grouping N messages together.

        Args:
            thread: The thread to chunk

        Returns:
            List of chunks with metadata

        Raises:
            ValueError: If thread has no messages or text is empty, or message_doc_id is not provided
        """
        if thread.message_doc_id is None:
            raise ValueError("Thread message_doc_id must be provided before chunking")

        # If thread has explicit messages, use those
        if thread.messages:
            return self._chunk_messages(thread)

        # Otherwise, fall back to text-based chunking
        if not thread.text or not thread.text.strip():
            raise ValueError("Thread must have either messages or text")

        # Split by double newlines as a simple message separator heuristic
        message_blocks = [block.strip() for block in thread.text.split("\n\n") if block.strip()]

        chunks = []
        for i in range(0, len(message_blocks), self.messages_per_chunk):
            chunk_blocks = message_blocks[i:i + self.messages_per_chunk]
            chunk_text = "\n\n".join(chunk_blocks)

            # Simple word count as token approximation
            token_count = len(chunk_text.split())

            chunk_idx = i // self.messages_per_chunk
            chunk = Chunk(
                chunk_id=generate_chunk_id(thread.message_doc_id, chunk_idx),
                message_doc_id=thread.message_doc_id,
                thread_id=thread.thread_id,
                text=chunk_text,
                chunk_index=chunk_idx,
                token_count=token_count,
                metadata=thread.metadata.copy()
            )
            chunks.append(chunk)

        return chunks

    def _chunk_messages(self, thread: Thread) -> list[Chunk]:
        """Chunk using explicit message list.

        Args:
            thread: Thread with messages list

        Returns:
            List of chunks
        """
        chunks = []
        messages = thread.messages or []

        for i in range(0, len(messages), self.messages_per_chunk):
            chunk_messages = messages[i:i + self.messages_per_chunk]

            # Combine message texts
            chunk_text = "\n\n".join(
                msg.get("text", msg.get("body", ""))
                for msg in chunk_messages
            )

            # Require message_doc_id on each message; fail fast if missing to avoid ambiguous IDs
            missing_info = [
                f"index {idx} (message_id: {msg.get('message_id', 'unknown')})"
                for idx, msg in enumerate(chunk_messages) if not msg.get("message_doc_id")
            ]
            if missing_info:
                max_display = 5
                display_info = missing_info[:max_display]
                more_count = len(missing_info) - max_display
                extra_msg = f", ... and {more_count} more" if more_count > 0 else ""
                raise ValueError(
                    f"message_doc_id is required for each message when chunking explicit messages "
                    f"({len(missing_info)} message(s) missing identifiers): {display_info}{extra_msg}"
                )

            # Combine metadata from all messages
            combined_metadata = thread.metadata.copy()
            combined_metadata["message_doc_ids"] = [msg["message_doc_id"] for msg in chunk_messages]
            combined_metadata["message_count"] = len(chunk_messages)

            token_count = len(chunk_text.split())

            chunk_idx = i // self.messages_per_chunk
            chunk = Chunk(
                chunk_id=generate_chunk_id(thread.message_doc_id, chunk_idx),
                message_doc_id=thread.message_doc_id,
                thread_id=thread.thread_id,
                text=chunk_text,
                chunk_index=chunk_idx,
                token_count=token_count,
                metadata=combined_metadata
            )
            chunks.append(chunk)

        return chunks


class SemanticChunker(ThreadChunker):
    """Chunking strategy using semantic boundaries (sentences, speaker turns).

    This is a scaffold implementation that splits on sentence boundaries.
    Future enhancements could use embeddings for semantic similarity or
    detect speaker turn boundaries in conversations.

    Attributes:
        target_chunk_size: Target size for chunks in tokens
        split_on_speaker: Whether to split on speaker changes (not yet implemented)
    """

    def __init__(
        self,
        target_chunk_size: int = 400,
        split_on_speaker: bool = False
    ):
        """Initialize SemanticChunker.

        Args:
            target_chunk_size: Target chunk size in tokens (default: 400)
            split_on_speaker: Split on speaker changes (not yet implemented)
        """
        self.target_chunk_size = target_chunk_size
        self.split_on_speaker = split_on_speaker

    @classmethod
    def from_config(cls, driver_config: DriverConfig_Chunker_Semantic) -> "SemanticChunker":
        """Create SemanticChunker from driver configuration.

        Expected keys:
        - target_chunk_size (int)
        - split_on_speaker (bool)
        """
        target_chunk_size = driver_config.target_chunk_size
        split_on_speaker = driver_config.split_on_speaker
        return cls(
            target_chunk_size=int(target_chunk_size if target_chunk_size is not None else 400),
            split_on_speaker=bool(split_on_speaker if split_on_speaker is not None else False),
        )

    def chunk(self, thread: Thread) -> list[Chunk]:
        """Chunk a thread on sentence boundaries.

        This is a basic implementation that splits on sentence boundaries
        and groups sentences until the target chunk size is reached.

        Args:
            thread: The thread to chunk

        Returns:
            List of chunks with metadata

        Raises:
            ValueError: If thread text is empty or message_doc_id is not provided
        """
        if not thread.text or not thread.text.strip():
            raise ValueError("Thread text cannot be empty")
        if thread.message_doc_id is None:
            raise ValueError("Thread message_doc_id must be provided before chunking")

        # Simple sentence splitting on common terminators
        # A more robust implementation would use NLTK or spaCy
        sentences = self._split_sentences(thread.text)

        chunks = []
        current_chunk_sentences = []
        current_token_count = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = len(sentence.split())

            # If adding this sentence would exceed target, create a chunk
            if current_chunk_sentences and current_token_count + sentence_tokens > self.target_chunk_size:
                chunk_text = " ".join(current_chunk_sentences)
                chunk = Chunk(
                    chunk_id=generate_chunk_id(thread.message_doc_id, chunk_index),
                    message_doc_id=thread.message_doc_id,
                    thread_id=thread.thread_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_token_count,
                    metadata=thread.metadata.copy()
                )
                chunks.append(chunk)
                chunk_index += 1

                # Start new chunk
                current_chunk_sentences = []
                current_token_count = 0

            current_chunk_sentences.append(sentence)
            current_token_count += sentence_tokens

        # Add final chunk if there are remaining sentences
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunk = Chunk(
                chunk_id=generate_chunk_id(thread.message_doc_id, chunk_index),
                message_doc_id=thread.message_doc_id,
                thread_id=thread.thread_id,
                text=chunk_text,
                chunk_index=chunk_index,
                token_count=current_token_count,
                metadata=thread.metadata.copy()
            )
            chunks.append(chunk)

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        This is a simple implementation. A production version would use
        a proper sentence tokenizer like NLTK or spaCy.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        import re

        # Split on sentence terminators followed by whitespace
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]


def create_chunker(
    config: AdapterConfig_Chunker,
) -> ThreadChunker:
    """Create a chunker from typed configuration.

    Args:
        config: Typed adapter configuration for chunker.

    Returns:
        ThreadChunker instance.

    Raises:
        ValueError: If config is missing or chunking_strategy is not recognized.
    """
    return create_adapter(
        config,
        adapter_name="chunker",
        get_driver_type=lambda c: c.chunking_strategy,
        get_driver_config=lambda c: c.driver,
        drivers={
            "token_window": TokenWindowChunker.from_config,
            "fixed_size": FixedSizeChunker.from_config,
            "semantic": SemanticChunker.from_config,
        },
    )

