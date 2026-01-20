# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Context source implementations for orchestrator."""

from typing import Any

from copilot_logging import get_logger
from copilot_storage import DocumentStore
from copilot_vectorstore import VectorStore

from .context_selector import ContextSource

logger = get_logger(__name__)

# Default similarity score when vector store is unavailable or no query vector provided.
# This represents "unknown relevance" rather than "moderate relevance". The value 0.5
# is used as a neutral placeholder score that doesn't bias selection toward or away
# from these chunks (since all will have the same score, tie-breaking by chunk_id applies).
# In practice, when this fallback is used, chunks are effectively sorted alphabetically.
DEFAULT_FALLBACK_SIMILARITY_SCORE = 0.5


class ThreadChunksSource(ContextSource):
    """Context source that retrieves chunks for a thread from vector store.

    Uses vector similarity to find the most relevant chunks for the thread.
    """

    def __init__(self, document_store: DocumentStore, vector_store: VectorStore):
        """Initialize thread chunks source.

        Args:
            document_store: Document store for chunk metadata
            vector_store: Vector store for similarity search
        """
        self.document_store = document_store
        self.vector_store = vector_store

    def get_candidates(self, thread_id: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Retrieve candidate chunks for a thread.

        Queries the vector store for chunks with high similarity to the thread's
        mean embedding or a specific query embedding. Returns chunks with their
        similarity scores.

        Args:
            thread_id: Thread identifier
            query: Query parameters:
                - query_vector: Optional query embedding vector for similarity search
                - top_k: Number of candidates to retrieve (default: 50)
                - min_score: Optional minimum similarity score

        Returns:
            List of chunk documents with metadata including similarity scores

        Note:
            Currently, query_vector is not provided by the orchestrator, so this method
            falls back to document store retrieval with a neutral score. This means chunks
            are effectively sorted alphabetically (via deterministic tie-breaking) rather
            than by relevance. To enable true "top-k relevance" selection:
            1. Compute a query vector (e.g., mean of thread embeddings) in orchestrator
            2. Pass it in the query parameter when calling get_candidates
            3. Or retrieve pre-computed similarity scores from chunk metadata in document store
        """
        top_k = query.get("top_k", 50)
        query_vector = query.get("query_vector")
        min_score = query.get("min_score", 0.0)

        # If no query vector provided, retrieve chunks by thread_id from document store
        if query_vector is None:
            logger.debug(f"No query vector provided, retrieving all chunks for thread {thread_id}")
            chunks = self.document_store.query_documents(
                collection="chunks",
                filter_dict={"thread_id": thread_id, "embedding_generated": True},
                limit=top_k,
            )

            # Assign fallback score since we're not using vector similarity
            for chunk in chunks:
                chunk["similarity_score"] = DEFAULT_FALLBACK_SIMILARITY_SCORE

            return chunks

        # Query vector store for similar chunks
        try:
            results = self.vector_store.query(query_vector=query_vector, top_k=top_k)

            # Filter by thread_id and min_score
            filtered_results = []
            for result in results:
                # Check if chunk belongs to this thread
                chunk_metadata = result.metadata
                if chunk_metadata.get("thread_id") != thread_id:
                    continue

                # Check minimum score threshold
                if result.score < min_score:
                    continue

                filtered_results.append(result)

            # Retrieve full chunk documents from document store
            chunk_ids = [result.id for result in filtered_results]
            if not chunk_ids:
                logger.debug(f"No chunks found for thread {thread_id} after filtering")
                return []

            chunks = self.document_store.query_documents(
                collection="chunks", filter_dict={"_id": {"$in": chunk_ids}}, limit=len(chunk_ids)
            )

            # Create chunk_id -> score mapping
            score_map = {result.id: result.score for result in filtered_results}

            # Add similarity scores to chunks
            for chunk in chunks:
                chunk_id = chunk.get("_id")
                chunk["similarity_score"] = score_map.get(chunk_id, 0.0)

            return chunks

        except Exception as e:
            logger.error(f"Error querying vector store for thread {thread_id}: {e}", exc_info=True)
            # Fallback to document store query without vector similarity
            chunks = self.document_store.query_documents(
                collection="chunks",
                filter_dict={"thread_id": thread_id, "embedding_generated": True},
                limit=top_k,
            )

            # Assign fallback score
            for chunk in chunks:
                chunk["similarity_score"] = DEFAULT_FALLBACK_SIMILARITY_SCORE

            return chunks

    def get_source_type(self) -> str:
        """Return the source type identifier.

        Returns:
            "thread_chunks"
        """
        return "thread_chunks"
