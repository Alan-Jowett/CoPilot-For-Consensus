# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for context selector implementations."""

from unittest.mock import Mock

import pytest
from app.context_selectors import TopKCohesiveSelector, TopKRelevanceSelector


class TestTopKRelevanceSelector:
    """Tests for TopKRelevanceSelector."""

    def test_select_top_k_by_score(self):
        """Test that selector picks top-k by relevance score."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high relevance"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "medium relevance"},
            {"_id": "chunk3", "similarity_score": 0.8, "text": "good relevance"},
            {"_id": "chunk4", "similarity_score": 0.3, "text": "low relevance"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        assert len(result.selected_chunks) == 2
        # Should select chunk1 (0.9) and chunk3 (0.8)
        assert result.selected_chunks[0].chunk_id == "chunk1"
        assert result.selected_chunks[0].score == 0.9
        assert result.selected_chunks[0].rank == 0
        assert result.selected_chunks[1].chunk_id == "chunk3"
        assert result.selected_chunks[1].score == 0.8
        assert result.selected_chunks[1].rank == 1

    def test_deterministic_tie_breaking(self):
        """Test that ties are broken deterministically by chunk_id."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk_a", "similarity_score": 0.5, "text": "text a"},
            {"_id": "chunk_b", "similarity_score": 0.5, "text": "text b"},
            {"_id": "chunk_c", "similarity_score": 0.5, "text": "text c"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        assert len(result.selected_chunks) == 2
        # Should be ordered by chunk_id (alphabetically) when scores are equal
        assert result.selected_chunks[0].chunk_id == "chunk_a"
        assert result.selected_chunks[1].chunk_id == "chunk_b"

    def test_token_budget_enforcement(self):
        """Test that selector respects token budget."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "a" * 100},  # ~130 tokens
            {"_id": "chunk2", "similarity_score": 0.8, "text": "b" * 100},  # ~130 tokens
            {"_id": "chunk3", "similarity_score": 0.7, "text": "c" * 100},  # ~130 tokens
            {"_id": "chunk4", "similarity_score": 0.6, "text": "d" * 100},  # ~130 tokens
        ]

        # Budget should allow only ~2 chunks
        result = selector.select(
            thread_id="test-thread", candidates=candidates, top_k=4, context_window_tokens=300
        )

        # Should stop at 2 chunks due to token budget
        assert len(result.selected_chunks) <= 3
        assert result.total_tokens <= 300

    def test_empty_candidates(self):
        """Test behavior with empty candidates."""
        selector = TopKRelevanceSelector()

        result = selector.select(thread_id="test-thread", candidates=[], top_k=5)

        assert len(result.selected_chunks) == 0
        assert result.total_candidates == 0

    def test_fewer_candidates_than_top_k(self):
        """Test that selector returns all candidates if fewer than top_k."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "low"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=10)

        assert len(result.selected_chunks) == 2

    def test_selector_metadata(self):
        """Test that result includes correct selector metadata."""
        selector = TopKRelevanceSelector()

        candidates = [{"_id": "chunk1", "similarity_score": 0.9, "text": "test"}]

        result = selector.select(
            thread_id="test-thread", candidates=candidates, top_k=5, context_window_tokens=1000
        )

        assert result.selector_type == "top_k_relevance"
        assert result.selector_version == "1.0.0"
        assert result.selection_params["top_k"] == 5
        assert result.selection_params["context_window_tokens"] == 1000
        assert result.total_candidates == 1

    def test_chunk_metadata_preservation(self):
        """Test that chunk metadata is preserved in selected chunks."""
        selector = TopKRelevanceSelector()

        candidates = [
            {
                "_id": "chunk1",
                "similarity_score": 0.9,
                "text": "test",
                "message_id": "msg1",
                "message_doc_id": "doc1",
                "offset": 100,
                "thread_id": "thread1",
            }
        ]

        result = selector.select(thread_id="thread1", candidates=candidates, top_k=1)

        assert len(result.selected_chunks) == 1
        selected = result.selected_chunks[0]
        assert selected.metadata["message_id"] == "msg1"
        assert selected.metadata["message_doc_id"] == "doc1"
        assert selected.metadata["offset"] == 100
        assert selected.metadata["thread_id"] == "thread1"


class TestTopKCohesiveSelector:
    """Tests for TopKCohesiveSelector (placeholder implementation)."""

    def test_fallback_to_relevance(self):
        """Test that cohesive selector currently falls back to relevance-based selection."""
        selector = TopKCohesiveSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "low"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        # Should behave like relevance selector for now
        assert len(result.selected_chunks) == 2
        assert result.selector_type == "top_k_cohesive"
        assert result.selector_version == "1.0.0"


class TestContextSelectorFactory:
    """Tests for context selector factory."""

    def test_create_top_k_relevance_selector(self):
        """Test creating top-k relevance selector."""
        from app.context_factory import create_context_selector

        selector = create_context_selector("top_k_relevance")

        assert isinstance(selector, TopKRelevanceSelector)
        assert selector.get_selector_type() == "top_k_relevance"

    def test_create_top_k_cohesive_selector(self):
        """Test creating top-k cohesive selector."""
        from app.context_factory import create_context_selector

        selector = create_context_selector("top_k_cohesive")

        assert isinstance(selector, TopKCohesiveSelector)
        assert selector.get_selector_type() == "top_k_cohesive"

    def test_unknown_selector_type(self):
        """Test that unknown selector type raises error."""
        from app.context_factory import create_context_selector

        with pytest.raises(ValueError, match="Unknown selector type"):
            create_context_selector("invalid_selector")


class TestContextSourceFactory:
    """Tests for context source factory."""

    def test_create_thread_chunks_source(self):
        """Test creating thread chunks source."""
        from app.context_factory import create_context_source
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        source = create_context_source("thread_chunks", mock_doc_store, mock_vector_store)

        assert isinstance(source, ThreadChunksSource)
        assert source.get_source_type() == "thread_chunks"

    def test_missing_vector_store(self):
        """Test that thread_chunks source requires vector store."""
        from app.context_factory import create_context_source

        mock_doc_store = Mock()

        with pytest.raises(ValueError, match="vector_store is required"):
            create_context_source("thread_chunks", mock_doc_store, None)

    def test_unknown_source_type(self):
        """Test that unknown source type raises error."""
        from app.context_factory import create_context_source

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        with pytest.raises(ValueError, match="Unknown source type"):
            create_context_source("invalid_source", mock_doc_store, mock_vector_store)


class TestThreadChunksSource:
    """Tests for ThreadChunksSource.get_candidates method."""

    def test_get_candidates_with_query_vector(self):
        """Test get_candidates with query_vector (vector store path)."""
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        # Mock vector store query results
        mock_vector_store.query.return_value = [
            {"chunk_id": "chunk1", "similarity_score": 0.9},
            {"chunk_id": "chunk2", "similarity_score": 0.8},
            {"chunk_id": "chunk3", "similarity_score": 0.7},
        ]

        # Mock document store query for full chunk data
        mock_doc_store.query_documents.return_value = [
            {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
            {"_id": "chunk2", "text": "text2", "thread_id": "thread1"},
            {"_id": "chunk3", "text": "text3", "thread_id": "thread1"},
        ]

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        query_vector = [0.1, 0.2, 0.3]
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"query_vector": query_vector, "top_k": 3, "min_score": 0.0}
        )

        # Verify vector store was queried
        mock_vector_store.query.assert_called_once_with(query_vector=query_vector, top_k=3)
        
        # Verify document store was queried for chunks
        mock_doc_store.query_documents.assert_called_once()
        
        # Verify results
        assert len(candidates) == 3
        assert candidates[0]["_id"] == "chunk1"
        assert candidates[0]["similarity_score"] == 0.9
        assert candidates[1]["_id"] == "chunk2"
        assert candidates[1]["similarity_score"] == 0.8

    def test_get_candidates_filters_by_thread_id(self):
        """Test that get_candidates filters results by thread_id."""
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        # Mock vector store with mixed thread_ids
        mock_vector_store.query.return_value = [
            {"chunk_id": "chunk1", "similarity_score": 0.9},
            {"chunk_id": "chunk2", "similarity_score": 0.8},
        ]

        # Mock document store with mixed thread_ids
        mock_doc_store.query_documents.return_value = [
            {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
            {"_id": "chunk2", "text": "text2", "thread_id": "thread2"},  # Different thread
        ]

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"query_vector": [0.1, 0.2], "top_k": 2}
        )

        # Should only include chunk1 (thread1)
        assert len(candidates) == 1
        assert candidates[0]["_id"] == "chunk1"

    def test_get_candidates_filters_by_min_score(self):
        """Test that get_candidates filters by min_score threshold."""
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        mock_vector_store.query.return_value = [
            {"chunk_id": "chunk1", "similarity_score": 0.9},
            {"chunk_id": "chunk2", "similarity_score": 0.5},
            {"chunk_id": "chunk3", "similarity_score": 0.3},
        ]

        mock_doc_store.query_documents.return_value = [
            {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
            {"_id": "chunk2", "text": "text2", "thread_id": "thread1"},
            {"_id": "chunk3", "text": "text3", "thread_id": "thread1"},
        ]

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"query_vector": [0.1], "top_k": 10, "min_score": 0.6}
        )

        # Should only include chunk1 (score 0.9 >= 0.6)
        assert len(candidates) == 1
        assert candidates[0]["similarity_score"] == 0.9

    def test_get_candidates_without_query_vector_fallback(self):
        """Test get_candidates without query_vector (document store fallback)."""
        from app.context_sources import ThreadChunksSource, DEFAULT_FALLBACK_SIMILARITY_SCORE

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        # Mock document store query
        mock_doc_store.query_documents.return_value = [
            {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
            {"_id": "chunk2", "text": "text2", "thread_id": "thread1"},
        ]

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"top_k": 5}  # No query_vector
        )

        # Verify vector store was NOT queried
        mock_vector_store.query.assert_not_called()
        
        # Verify document store was queried
        mock_doc_store.query_documents.assert_called_once_with(
            collection="chunks",
            filter_dict={"thread_id": "thread1", "embedding_generated": True},
            limit=5
        )
        
        # Verify fallback scores assigned
        assert len(candidates) == 2
        assert candidates[0]["similarity_score"] == DEFAULT_FALLBACK_SIMILARITY_SCORE
        assert candidates[1]["similarity_score"] == DEFAULT_FALLBACK_SIMILARITY_SCORE

    def test_get_candidates_empty_results(self):
        """Test get_candidates with empty results."""
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        mock_vector_store.query.return_value = []
        mock_doc_store.query_documents.return_value = []

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"query_vector": [0.1], "top_k": 5}
        )

        assert len(candidates) == 0

    def test_get_candidates_vector_store_failure_fallback(self):
        """Test that get_candidates falls back to document store on vector store error."""
        from app.context_sources import ThreadChunksSource, DEFAULT_FALLBACK_SIMILARITY_SCORE

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        # Mock vector store to raise an exception
        mock_vector_store.query.side_effect = Exception("Vector store unavailable")

        # Mock document store fallback
        mock_doc_store.query_documents.return_value = [
            {"_id": "chunk1", "text": "text1", "thread_id": "thread1"},
        ]

        source = ThreadChunksSource(mock_doc_store, mock_vector_store)
        
        candidates = source.get_candidates(
            thread_id="thread1",
            query={"query_vector": [0.1], "top_k": 5}
        )

        # Should fall back to document store
        assert len(candidates) == 1
        assert candidates[0]["similarity_score"] == DEFAULT_FALLBACK_SIMILARITY_SCORE

