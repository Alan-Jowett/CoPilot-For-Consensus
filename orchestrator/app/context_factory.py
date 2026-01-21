# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating context selectors and sources."""

from copilot_logging import get_logger
from copilot_storage import DocumentStore
from copilot_vectorstore import VectorStore

from .context_selector import ContextSelector, ContextSource
from .context_selectors import TopKCohesiveSelector, TopKRelevanceSelector
from .context_sources import ThreadChunksSource

logger = get_logger(__name__)


def create_context_selector(selector_type: str = "top_k_relevance") -> ContextSelector:
    """Create a context selector based on type.

    Args:
        selector_type: Type of selector to create:
            - "top_k_relevance": Select by vector similarity (default)
            - "top_k_cohesive": Select cohesive/interrelated chunks (partial implementation)

    Returns:
        ContextSelector instance

    Raises:
        ValueError: If selector_type is not recognized

    Future Plans:
        Additional selector types planned for future implementation:
        - "hybrid_relevance_then_cohesion": Combine relevance and cohesion
        - "mmr": Maximal Marginal Relevance for diversity
    """
    selector_type = selector_type.lower()

    if selector_type == "top_k_relevance":
        return TopKRelevanceSelector()
    elif selector_type == "top_k_cohesive":
        return TopKCohesiveSelector()
    else:
        raise ValueError(
            f"Unknown selector type: {selector_type}. "
            f"Supported types: top_k_relevance, top_k_cohesive"
        )


def create_context_source(
    source_type: str, document_store: DocumentStore, vector_store: VectorStore | None = None
) -> ContextSource:
    """Create a context source based on type.

    Args:
        source_type: Type of source to create:
            - "thread_chunks": Thread chunks from vector store
            - "rfc_chunks": RFC chunks (future)
            - "draft_chunks": IETF draft chunks (future)
        document_store: Document store instance
        vector_store: Vector store instance (optional, required for some sources)

    Returns:
        ContextSource instance

    Raises:
        ValueError: If source_type is not recognized or required dependencies missing
    """
    source_type = source_type.lower()

    if source_type == "thread_chunks":
        if vector_store is None:
            raise ValueError("vector_store is required for thread_chunks source")
        return ThreadChunksSource(document_store=document_store, vector_store=vector_store)
    else:
        raise ValueError(
            f"Unknown source type: {source_type}. " f"Supported types: thread_chunks"
        )
