# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Context selection abstractions for orchestrator.

This module defines interfaces and implementations for selecting chunks
to include in summarization context. It enables pluggable selection
strategies and extensible context sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SelectedChunk:
    """A selected chunk with metadata for summarization context.

    Attributes:
        chunk_id: Unique identifier for the chunk (_id from chunks collection)
        source: Source type (e.g., "thread_chunks", "rfc_chunks", "draft_chunks")
        score: Relevance score (higher is more relevant)
        rank: Position in final ordered selection (0-indexed)
        metadata: Additional metadata (message_id, offset, etc.)
    """

    chunk_id: str
    source: str
    score: float
    rank: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextSelection:
    """Result of context selection with audit metadata.

    Attributes:
        selected_chunks: Ordered list of selected chunks
        selector_type: Strategy type used (e.g., "top_k_relevance")
        selector_version: Version of the selector implementation
        selection_params: Parameters used for selection (top_k, threshold, etc.)
        total_candidates: Total number of candidate chunks considered
        total_tokens: Estimated token count of selected context
    """

    selected_chunks: list[SelectedChunk]
    selector_type: str
    selector_version: str
    selection_params: dict[str, Any]
    total_candidates: int = 0
    total_tokens: int = 0


class ContextSource(ABC):
    """Abstract interface for context sources.

    A context source provides candidate chunks for a given thread or topic.
    Examples: thread chunks, RFC chunks, draft chunks, related threads.
    """

    @abstractmethod
    def get_candidates(self, thread_id: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Retrieve candidate chunks for selection.

        Args:
            thread_id: Thread identifier
            query: Query parameters (may include embeddings, filters, etc.)

        Returns:
            List of candidate chunk documents with metadata
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type identifier.

        Returns:
            Source type string (e.g., "thread_chunks", "rfc_chunks")
        """
        pass


class ContextSelector(ABC):
    """Abstract interface for context selection strategies.

    A context selector takes candidate chunks and selects the top-k most
    relevant ones for summarization, with deterministic ordering and
    optional token budget enforcement.
    """

    @abstractmethod
    def select(
        self,
        thread_id: str,
        candidates: list[dict[str, Any]],
        top_k: int,
        context_window_tokens: int | None = None,
    ) -> ContextSelection:
        """Select top-k chunks from candidates.

        Args:
            thread_id: Thread identifier
            candidates: List of candidate chunks with metadata
            top_k: Maximum number of chunks to select
            context_window_tokens: Optional token budget for context

        Returns:
            ContextSelection with ordered chunks and metadata
        """
        pass

    @abstractmethod
    def get_selector_type(self) -> str:
        """Return the selector type identifier.

        Returns:
            Selector type string (e.g., "top_k_relevance", "top_k_cohesive")
        """
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Return the selector version.

        Returns:
            Version string (e.g., "1.0.0")
        """
        pass
