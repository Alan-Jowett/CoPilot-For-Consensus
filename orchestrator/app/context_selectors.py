# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Context selector implementations for orchestrator."""

import hashlib
from typing import Any

from copilot_logging import get_logger

from .context_selector import ContextSelection, ContextSelector, SelectedChunk

logger = get_logger(__name__)


class TopKRelevanceSelector(ContextSelector):
    """Select top-k chunks by relevance (similarity score).

    This is a classic RAG selection strategy that ranks chunks by vector
    similarity to a query and selects the top-k. Uses deterministic tie-breaking
    to ensure stable ordering.
    """

    VERSION = "1.0.0"

    def __init__(self, token_estimator: callable[[str], int] | None = None):
        """Initialize top-k relevance selector.

        Args:
            token_estimator: Optional function to estimate token count from text.
                           If None, uses simple word count * 1.3 heuristic.
        """
        self.token_estimator = token_estimator or self._default_token_estimator

    def select(
        self,
        thread_id: str,
        candidates: list[dict[str, Any]],
        top_k: int,
        context_window_tokens: int | None = None,
    ) -> ContextSelection:
        """Select top-k chunks by relevance score.

        Ranks candidates by similarity_score (descending) with deterministic
        tie-breaking by chunk_id. Optionally enforces token budget.

        Args:
            thread_id: Thread identifier
            candidates: List of candidate chunks with similarity_score
            top_k: Maximum number of chunks to select
            context_window_tokens: Optional token budget for context

        Returns:
            ContextSelection with ordered chunks and metadata
        """
        if not candidates:
            logger.warning(f"No candidates provided for thread {thread_id}")
            return ContextSelection(
                selected_chunks=[],
                selector_type=self.get_selector_type(),
                selector_version=self.get_version(),
                selection_params={"top_k": top_k, "context_window_tokens": context_window_tokens},
                total_candidates=0,
                total_tokens=0,
            )

        # Sort by score (descending), then by chunk_id (ascending) for determinism
        sorted_candidates = sorted(
            candidates, key=lambda c: (-c.get("similarity_score", 0.0), c.get("_id", ""))
        )

        # Select top-k with optional token budget
        selected = []
        total_tokens = 0

        for rank, chunk in enumerate(sorted_candidates[:top_k]):
            chunk_id = chunk.get("_id")
            if not chunk_id:
                logger.warning(f"Candidate chunk missing _id, skipping: {chunk}")
                continue

            # Estimate token count if budget is specified
            if context_window_tokens is not None:
                text = chunk.get("text", "")
                chunk_tokens = self.token_estimator(text)

                # Check if adding this chunk would exceed budget
                if total_tokens + chunk_tokens > context_window_tokens:
                    logger.debug(
                        f"Token budget exceeded at rank {rank} "
                        f"({total_tokens + chunk_tokens} > {context_window_tokens}), stopping selection"
                    )
                    break

                total_tokens += chunk_tokens

            # Create selected chunk
            selected_chunk = SelectedChunk(
                chunk_id=str(chunk_id),
                source=chunk.get("source_type", "thread_chunks"),
                score=chunk.get("similarity_score", 0.0),
                rank=rank,
                metadata={
                    "message_id": chunk.get("message_id", ""),
                    "message_doc_id": chunk.get("message_doc_id", ""),
                    "offset": chunk.get("offset", 0),
                    "thread_id": chunk.get("thread_id", thread_id),
                },
            )
            selected.append(selected_chunk)

        logger.info(
            f"Selected {len(selected)}/{len(candidates)} chunks for thread {thread_id} "
            f"(top_k={top_k}, tokens={total_tokens})"
        )

        return ContextSelection(
            selected_chunks=selected,
            selector_type=self.get_selector_type(),
            selector_version=self.get_version(),
            selection_params={"top_k": top_k, "context_window_tokens": context_window_tokens},
            total_candidates=len(candidates),
            total_tokens=total_tokens,
        )

    def get_selector_type(self) -> str:
        """Return the selector type identifier.

        Returns:
            "top_k_relevance"
        """
        return "top_k_relevance"

    def get_version(self) -> str:
        """Return the selector version.

        Returns:
            Version string
        """
        return self.VERSION

    @staticmethod
    def _default_token_estimator(text: str) -> int:
        """Default token estimator using word count heuristic.

        Uses a simple heuristic: word count * 1.3 (accounts for punctuation,
        subword tokens, etc.).

        Args:
            text: Text to estimate token count for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        word_count = len(text.split())
        return int(word_count * 1.3)


class TopKCohesiveSelector(ContextSelector):
    """Select top-k chunks that are most cohesive/interrelated.

    This strategy aims to select chunks that form a coherent subset, rather than
    just the most individually relevant chunks. Useful for selecting context that
    represents a discussion thread with multiple related points.

    Future implementation could use:
    - Clustering of embeddings and selecting from dense clusters
    - Graph-based selection (edges weighted by similarity)
    - MMR (Maximal Marginal Relevance) for diversity within relevance
    """

    VERSION = "1.0.0"

    def __init__(self, token_estimator: callable[[str], int] | None = None):
        """Initialize top-k cohesive selector.

        Args:
            token_estimator: Optional function to estimate token count from text.
        """
        self.token_estimator = token_estimator or TopKRelevanceSelector._default_token_estimator

    def select(
        self,
        thread_id: str,
        candidates: list[dict[str, Any]],
        top_k: int,
        context_window_tokens: int | None = None,
    ) -> ContextSelection:
        """Select top-k cohesive chunks.

        Placeholder implementation: currently falls back to relevance-based selection.
        Future implementations will add cohesion metrics.

        Args:
            thread_id: Thread identifier
            candidates: List of candidate chunks
            top_k: Maximum number of chunks to select
            context_window_tokens: Optional token budget

        Returns:
            ContextSelection with ordered chunks
        """
        logger.warning(
            f"TopKCohesiveSelector not fully implemented yet, falling back to relevance-based selection"
        )

        # For now, use same logic as TopKRelevanceSelector
        # In the future, this will compute cohesion scores and cluster-based selection
        selector = TopKRelevanceSelector(token_estimator=self.token_estimator)
        result = selector.select(thread_id, candidates, top_k, context_window_tokens)

        # Override selector type to indicate this was cohesive selection (even if placeholder)
        result.selector_type = self.get_selector_type()
        result.selector_version = self.get_version()

        return result

    def get_selector_type(self) -> str:
        """Return the selector type identifier.

        Returns:
            "top_k_cohesive"
        """
        return "top_k_cohesive"

    def get_version(self) -> str:
        """Return the selector version.

        Returns:
            Version string
        """
        return self.VERSION
