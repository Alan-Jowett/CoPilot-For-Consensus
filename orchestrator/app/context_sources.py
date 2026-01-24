# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Context source implementations for orchestrator."""

from typing import Any

from copilot_logging import get_logger
from copilot_storage import DocumentStore
from copilot_vectorstore import VectorStore

from .context_selector import ContextSource

logger = get_logger(__name__)

# Neutral similarity score when vector store is unavailable or no query vector provided.
# This represents "unknown relevance" rather than "moderate relevance". The value 0.5
# is used as a neutral placeholder score that doesn't bias selection toward or away
# from these chunks (since all will have the same score, tie-breaking by chunk_id applies).
# In practice, when this fallback is used, chunks are effectively sorted alphabetically.
UNKNOWN_RELEVANCE_SCORE = 0.5


class ThreadChunksSource(ContextSource):
    """Context source that retrieves chunks for a thread from vector store.

    Uses vector similarity to find the most relevant chunks for the thread.
    """

    def __init__(self, document_store: DocumentStore, vector_store: VectorStore | None):
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
                chunk["similarity_score"] = UNKNOWN_RELEVANCE_SCORE

            return chunks

        # Query vector store for similar chunks
        if self.vector_store is None:
            logger.warning(
                f"Vector store unavailable, falling back to document store for thread {thread_id}"
            )
            chunks = self.document_store.query_documents(
                collection="chunks",
                filter_dict={"thread_id": thread_id, "embedding_generated": True},
                limit=top_k,
            )

            for chunk in chunks:
                chunk["similarity_score"] = UNKNOWN_RELEVANCE_SCORE

            return chunks

        try:
            results = self.vector_store.query(query_vector=query_vector, top_k=top_k)

            # Normalize results into (chunk_id, score, metadata)
            normalized: list[tuple[str, float, dict[str, Any]]] = []
            for result in results:
                if isinstance(result, dict):
                    result_chunk_id = result.get("chunk_id") or result.get("_id") or result.get("id")
                    result_score = result.get("similarity_score")
                    if result_score is None:
                        result_score = result.get("score")
                    result_metadata = result.get("metadata") or {}
                else:
                    result_chunk_id = getattr(result, "id", None)
                    result_score = getattr(result, "score", None)
                    result_metadata = getattr(result, "metadata", None) or {}

                if result_chunk_id is None:
                    continue
                if result_score is None:
                    continue

                normalized.append((str(result_chunk_id), float(result_score), result_metadata))

            # Filter by min_score (thread filtering happens after doc fetch if metadata missing)
            normalized = [(cid, score, meta) for (cid, score, meta) in normalized if score >= min_score]

            if not normalized:
                logger.debug(f"No chunks found for thread {thread_id} after score filtering")
                return []

            chunk_ids = [cid for (cid, _score, _meta) in normalized]

            chunks = self.document_store.query_documents(
                collection="chunks",
                filter_dict={"_id": {"$in": chunk_ids}},
                limit=len(chunk_ids),
            )

            # Build mappings for chunks and scores
            score_map = {cid: score for (cid, score, _meta) in normalized}
            chunk_map: dict[str, dict[str, Any]] = {}
            for chunk in chunks:
                chunk_identifier = chunk.get("_id")
                if chunk_identifier is None:
                    chunk_keys = list(chunk.keys()) if chunk else "empty"
                    logger.warning(
                        f"Chunk missing required _id field for thread {thread_id} (vector query path), skipping. Chunk keys: {chunk_keys}"
                    )
                    continue
                chunk_map[str(chunk_identifier)] = chunk

            # Preserve vector-store order and apply thread_id filtering
            ordered_chunks: list[dict[str, Any]] = []
            for cid, _score, meta in normalized:
                chunk = chunk_map.get(cid)
                if chunk is None:
                    continue

                # Filter by thread_id if possible
                meta_thread_id = meta.get("thread_id") if isinstance(meta, dict) else None
                chunk_thread_id = chunk.get("thread_id")
                if meta_thread_id is not None and meta_thread_id != thread_id:
                    continue
                if chunk_thread_id is not None and chunk_thread_id != thread_id:
                    continue

                chunk["similarity_score"] = score_map.get(cid, 0.0)
                ordered_chunks.append(chunk)

            return ordered_chunks

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
                chunk["similarity_score"] = UNKNOWN_RELEVANCE_SCORE

            return chunks

    def get_source_type(self) -> str:
        """Return the source type identifier.

        Returns:
            "thread_chunks"
        """
        return "thread_chunks"
